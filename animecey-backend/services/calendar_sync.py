"""Calendrier des sorties : copie de franime.fr/calendrier + alertes aux admins.

Ce que fait ce module :
  1. une fois par semaine (CALENDAR_SYNC_INTERVAL_MIN, 10080 min par défaut pour FRAnime ; la date de
     la dernière lecture est gardée en base, un redémarrage ne relance rien), télécharge la page
     https://franime.fr/calendrier, lit les sorties de la semaine et les enregistre dans
     la table calendar_entries (heure convertie en UTC) ;
  2. relie chaque sortie à un animé du site quand le titre correspond exactement
     (titre, titre japonais ou autre nom enregistré avec /alias) ;
  3. CALENDAR_NOTIFY_DELAY_MIN minutes (30 par défaut) après l'heure de sortie, envoie en
     message privé à chaque admin du bot (TELEGRAM_ADMIN_IDS) une alerte ÉPINGLÉE :
     animé, langue (VF/VOSTFR), saison, épisode, n° de l'animé et la commande /anime à
     taper pour l'ajouter ;
  4. retire l'épinglage après CALENDAR_UNPIN_AFTER_H heures (24 par défaut), ou dès que
     l'épisode est vu comme publié (bouton « Vérifier »), pour ne pas remplir la liste
     des messages épinglés.

Source par défaut : FRAnime (CALENDAR_SOURCE=franime), avec un proxy sortant si FIXIE_URL est
défini. La lecture AniList (CALENDAR_SOURCE=anilist + commande /vf) reste dans le code, au repos.

Les heures affichées par FRAnime sont en heure française : on les convertit en UTC
(Lomé/Togo = UTC+0). Le passage heure d'été/hiver est géré tout seul.

Variables d'environnement (toutes optionnelles) :
  CALENDAR_SYNC_ENABLED       true / false                        (défaut : true)
  CALENDAR_SYNC_INTERVAL_MIN  minutes entre 2 lectures de la page (défaut : 10080 = 1 semaine pour
                              FRAnime, 30 pour AniList)
  CALENDAR_RETRY_MIN          minutes avant de réessayer après un échec (défaut : 360 = 6 h)
  CALENDAR_NOTIFY_DELAY_MIN   minutes après la sortie             (défaut : 30)
  CALENDAR_NOTIFY_MAX_AGE_H   au-delà, une sortie découverte trop tard est ignorée
                              sans message (défaut : 12)
  CALENDAR_UNPIN_AFTER_H      heures avant de désépingler          (défaut : 24)
  CALENDAR_SOURCE_URL         page à lire (défaut : https://franime.fr/calendrier)
  CALENDAR_SOURCE             franime (défaut) / anilist
  ZENROWS_API_KEY             clé ZenRows : sert de secours si le proxy Fixie échoue (ou de méthode
                              principale s'il n'y a pas de proxy)
  CALENDAR_ZENROWS_PARAMS     options ZenRows au format URL (sinon ZENROWS_PARAMS, sinon
                              premium_proxy=true&proxy_country=fr). Ajoute &js_render=true si la
                              page revient vide.
  CALENDAR_PROXY_URL          proxy HTTP pour lire FRAnime (sinon FIXIE_URL, fourni par Fixie)
  CALENDAR_FETCH_MODE         auto (défaut : Fixie d'abord, ZenRows en secours) / fixie / zenrows / direct
  CALENDAR_SOURCE_TZ          fuseau des heures de la page          (défaut : Europe/Paris)

Mettre ce fichier dans services/calendar_sync.py.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import delete, select

from config import settings
from database import async_session
from models import Anime, Episode, LanguageEnum
from models_calendar import CalendarEntry, CalendarState, CalendarVfSlot
from models_catalog import EpisodeServer
from services import anilist, search_fuzzy

logger = logging.getLogger(__name__)

ENABLED = os.getenv("CALENDAR_SYNC_ENABLED", "true").lower() in ("true", "1", "yes")
# « franime » (défaut) : lecture de la page franime.fr/calendrier (VF et VOSTFR comme sur FRAnime).
# « anilist » : sorties VO lues sur AniList, en VOSTFR ; la VF s'ajoute avec /vf.
SOURCE = os.getenv("CALENDAR_SOURCE", "franime").lower()
PROXY_URL = os.getenv("CALENDAR_PROXY_URL") or os.getenv("FIXIE_URL") or None
ZENROWS_KEY = os.getenv("ZENROWS_API_KEY", "").strip()
ZENROWS_PARAMS = (
    os.getenv("CALENDAR_ZENROWS_PARAMS") or os.getenv("ZENROWS_PARAMS") or "premium_proxy=true&proxy_country=fr"
).strip()
FETCH_MODE = os.getenv("CALENDAR_FETCH_MODE", "auto").strip().lower()
SOURCE_URL = os.getenv("CALENDAR_SOURCE_URL", "https://franime.fr/calendrier")
SOURCE_TZ = os.getenv("CALENDAR_SOURCE_TZ", "Europe/Paris")
SYNC_INTERVAL_MIN = max(5, int(os.getenv("CALENDAR_SYNC_INTERVAL_MIN") or (10080 if SOURCE == "franime" else 30)))
RETRY_MIN = max(5, int(os.getenv("CALENDAR_RETRY_MIN", "360")))
NOTIFY_DELAY_MIN = max(0, int(os.getenv("CALENDAR_NOTIFY_DELAY_MIN", "30")))
NOTIFY_MAX_AGE_H = max(1, int(os.getenv("CALENDAR_NOTIFY_MAX_AGE_H", "12")))
UNPIN_AFTER_H = max(1, int(os.getenv("CALENDAR_UNPIN_AFTER_H", "24")))
KEEP_DAYS = 21

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]

_sync_lock = asyncio.Lock()
_task: asyncio.Task | None = None


# ── Lecture de la page FRAnime ─────────────────────────────────────────


class _CalendarParser(HTMLParser):
    """Repère les titres de jour (« LUNDI 12/10 ») et les liens d'épisode qui suivent."""

    _HEADINGS = {"h1", "h2", "h3", "h4"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.entries: list[dict] = []
        self._day: tuple[int, int] | None = None
        self._in_heading = False
        self._heading: list[str] = []
        self._cur: dict | None = None

    def handle_starttag(self, tag, attrs):
        if tag in self._HEADINGS:
            self._in_heading = True
            self._heading = []
        elif tag == "a":
            href = dict(attrs).get("href") or ""
            if "/anime/" in href and "anime_id=" in href:
                self._cur = {"href": href, "texts": [], "day": self._day}

    def handle_endtag(self, tag):
        if tag in self._HEADINGS and self._in_heading:
            self._in_heading = False
            text = " ".join("".join(self._heading).split())
            m = re.search(r"(\d{1,2})\s*/\s*(\d{1,2})\s*$", text)
            if m:
                self._day = (int(m.group(1)), int(m.group(2)))
        elif tag == "a" and self._cur is not None:
            self.entries.append(self._cur)
            self._cur = None

    def handle_data(self, data):
        if self._in_heading:
            self._heading.append(data)
        text = data.strip()
        if text and self._cur is not None:
            self._cur["texts"].append(text)


def _guess_date(day: int, month: int, today) -> datetime | None:
    """Les titres de jour n'ont pas d'année : on prend celle qui tombe le plus près d'aujourd'hui."""
    best = None
    for year in (today.year - 1, today.year, today.year + 1):
        try:
            cand = datetime(year, month, day)
        except ValueError:
            continue
        if best is None or abs((cand.date() - today).days) < abs((best.date() - today).days):
            best = cand
    return best


def _slug_title(slug: str) -> str:
    return slug.replace("-", " ").strip().title() or "?"


def parse_calendar(page: str) -> list[dict]:
    """Page HTML -> sorties {franime_id, slug, title, season_raw, episode_number, language, release_at (UTC)}."""
    parser = _CalendarParser()
    parser.feed(page)
    tz = ZoneInfo(SOURCE_TZ)
    today = datetime.now(tz).date()

    found: dict[tuple, dict] = {}
    for raw in parser.entries:
        try:
            url = urlparse(raw["href"])
            q = parse_qs(url.query)
            franime_id = int(q["anime_id"][0])
            if not (0 < franime_id <= 2_147_483_647):  # colonne INTEGER Postgres (ex. The Simpsons : 45666666666)
                logger.warning("Calendrier : anime_id hors limites ignoré : %s (%s)", franime_id, raw["href"][:120])
                continue
            lang_code = (q.get("lang") or ["vo"])[0].lower()
            season_raw = (q.get("s") or ["1"])[0].strip() or "1"
            slug = url.path.rstrip("/").split("/")[-1]
        except (KeyError, ValueError, IndexError):
            continue

        episode = hour = minute = None
        titles: list[str] = []
        for text in raw["texts"]:
            m = re.fullmatch(r"E\s?(\d{1,4})", text)
            if m and episode is None:
                episode = int(m.group(1))
                continue
            m = re.fullmatch(r"(\d{1,2})\s*h\s*(\d{2})", text)
            if m and hour is None:
                hour, minute = int(m.group(1)), int(m.group(2))
                continue
            titles.append(text)
        if episode is None or hour is None:  # textes collés dans un seul bloc
            m = re.match(r"E\s?(\d{1,4})(?!\d)(.*?)(\d{1,2})\s*h\s*(\d{2})", "".join(raw["texts"]))
            if m:
                episode, hour, minute = int(m.group(1)), int(m.group(3)), int(m.group(4))
                titles = [m.group(2).strip()] if m.group(2).strip() else []
        if episode is None or hour is None or raw["day"] is None:
            if episode is not None or hour is not None:
                logger.warning("Calendrier : sortie ignorée (lecture incomplète) : %r", raw["texts"][:6])
            continue
        if not (0 < episode <= 9999):  # garde-fou : la colonne est un INTEGER Postgres
            logger.warning("Calendrier : épisode aberrant %s ignoré : %r", episode, raw["texts"][:6])
            continue

        day, month = raw["day"]
        base = _guess_date(day, month, today)
        if base is None or not (0 <= hour < 24 and 0 <= minute < 60):
            continue
        local = datetime(base.year, base.month, base.day, hour, minute, tzinfo=tz)

        title = (titles[0] if titles else _slug_title(slug)).strip()
        language = "VF" if lang_code == "vf" else "VOSTFR"
        key = (franime_id, season_raw, episode, language)
        found[key] = {
            "franime_id": franime_id,
            "slug": slug[:255],
            "title": title[:500],
            "season_raw": season_raw[:16],
            "episode_number": episode,
            "language": language,
            "release_at": local.astimezone(timezone.utc),
        }
    return list(found.values())


def _hide_credentials(text: str) -> str:
    """Retire user:mot_de_passe@ d'un message d'erreur (le proxy Fixie contient des identifiants)."""
    return re.sub(r"://[^/@\s]+@", "://***@", text)


async def _download_zenrows(headers: dict) -> str:
    from urllib.parse import parse_qsl

    params = {"apikey": ZENROWS_KEY, "url": SOURCE_URL}
    params.update(dict(parse_qsl(ZENROWS_PARAMS)))
    async with httpx.AsyncClient(follow_redirects=True, timeout=90.0) as client:
        resp = await client.get("https://api.zenrows.com/v1/", params=params)
    if resp.status_code != 200:
        raise RuntimeError(f"ZenRows HTTP {resp.status_code} : {resp.text[:200]}")
    return resp.text


async def _download_http(headers: dict, proxy: str | None) -> str:
    """Lecture directe, ou via le proxy HTTP (Fixie) quand `proxy` est donné."""
    label = "Fixie" if proxy else "direct"
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=45.0, headers=headers, proxy=proxy) as client:
            resp = await client.get(SOURCE_URL)
    except httpx.HTTPError as exc:
        raise RuntimeError(f"{label} : {_hide_credentials(f'{type(exc).__name__}: {exc}')}") from exc
    if resp.status_code != 200:
        raise RuntimeError(f"{label} HTTP {resp.status_code} : {resp.text[:150]!r}")
    return resp.text


async def _download() -> str:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "fr-FR,fr;q=0.9",
    }
    # Ordre des méthodes : Fixie d'abord (gratuit/peu cher), ZenRows seulement en secours.
    methods: list[tuple[str, object]] = []
    if FETCH_MODE in ("auto", "fixie") and PROXY_URL:
        methods.append(("Fixie", lambda: _download_http(headers, PROXY_URL)))
    if FETCH_MODE in ("auto", "zenrows") and ZENROWS_KEY:
        methods.append(("ZenRows", lambda: _download_zenrows(headers)))
    if FETCH_MODE == "direct" or not methods:
        methods.append(("direct", lambda: _download_http(headers, None)))

    errors: list[str] = []
    for name, fn in methods:
        try:
            page = await fn()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Calendrier : lecture %s en échec : %s", name, _hide_credentials(str(exc)))
            errors.append(_hide_credentials(str(exc)))
            continue
        logger.info("Calendrier : page lue via %s (%d octets)", name, len(page))
        return page
    raise RuntimeError(" | ".join(errors))


# ── Lien avec les animés du site ───────────────────────────────────────


async def find_anime(db, title: str) -> tuple[int | None, list[int]]:
    """(n° sûr, candidats probables).

    « Sûr » = le titre FRAnime est exactement un nom de l'animé (titre, titre japonais ou alias).
    Sinon on propose jusqu'à 3 candidats, sans rien affirmer.
    """
    q = search_fuzzy.norm(title)
    if len(q) < 2:
        return None, []
    tokens = q.split()
    scores: dict[int, float] = {}
    for aid, names in await search_fuzzy._load_index(db):
        best = max((search_fuzzy.score_name(q, tokens, n) for n in names), default=0.0)
        if best > 0:
            scores[aid] = best
    sure = sorted(aid for aid, s in scores.items() if s >= 100)
    if sure:
        return sure[0], []
    cands = sorted(((s, aid) for aid, s in scores.items() if s >= 80), key=lambda x: (-x[0], x[1]))
    return None, [aid for _, aid in cands[:3]]


def season_main(season_raw: str) -> int | None:
    head = season_raw.split(".")[0]
    return int(head) if head.isdigit() else None


def season_label(season_raw: str) -> str:
    head, _, part = season_raw.partition(".")
    if not head.isdigit():
        return season_raw.title()
    return f"Saison {int(head)}" + (f" Partie {part}" if part else "")


async def episode_status(db, anime_id: int, season_raw: str, episode: int, language: str) -> dict:
    """Cet épisode est-il en ligne chez nous ? -> {"state": ..., "seasons": [...]}.

    state : published | offline | other_season | missing
    """
    try:
        lang = LanguageEnum(language)
    except ValueError:
        return {"state": "missing", "seasons": []}
    rows = (
        await db.execute(
            select(Episode).where(
                Episode.anime_id == anime_id,
                Episode.language == lang,
                Episode.episode_number == episode,
            )
        )
    ).scalars().all()
    with_servers: set[int] = set()
    if rows:
        ids = [r.id for r in rows]
        with_servers = set(
            (await db.execute(select(EpisodeServer.episode_id).where(EpisodeServer.episode_id.in_(ids)))).scalars()
        )
    main = season_main(season_raw)
    found = [
        (r.season_number, bool(r.servcey1_available or r.servcey2_available or r.stream_url or r.id in with_servers))
        for r in rows
    ]
    same = [online for number, online in found if number == main]
    if any(same):
        state = "published"
    elif same:
        state = "offline"
    elif any(online for _, online in found):
        state = "other_season"
    elif found:
        state = "offline"
    else:
        state = "missing"
    return {"state": state, "seasons": sorted({n for n, online in found if online})}


def state_text(status: dict) -> str:
    state = status["state"]
    if state == "published":
        return "✅ publié"
    if state == "offline":
        return "⏳ ajouté mais pas encore lisible"
    if state == "other_season":
        seasons = ", ".join(f"S{n}" for n in status["seasons"])
        return f"⚠️ trouvé dans une autre saison ({seasons}) : vérifie la saison"
    return "❌ pas encore publié"


# ── Synchronisation ────────────────────────────────────────────────────


async def sync_calendar() -> dict:
    """Met le calendrier à jour depuis la source choisie (CALENDAR_SOURCE)."""
    await _purge_other_source()
    result = await (_sync_franime() if SOURCE == "franime" else sync_anilist())
    await _set_state("last_ok" if result.get("ok") else "last_fail", datetime.now(timezone.utc).isoformat())
    return result


async def _get_state(key: str) -> datetime | None:
    async with async_session() as db:
        row = await db.get(CalendarState, key)
    if row is None:
        return None
    try:
        return datetime.fromisoformat(row.value)
    except ValueError:
        return None


async def _set_state(key: str, value: str) -> None:
    async with async_session() as db:
        row = await db.get(CalendarState, key)
        if row is None:
            db.add(CalendarState(key=key, value=value))
        else:
            row.value = value
        await db.commit()


async def next_sync_at() -> datetime:
    """Prochaine lecture automatique : 1 intervalle après la dernière réussite ; après un échec,
    on attend RETRY_MIN (jamais toutes les minutes : chaque lecture coûte des crédits)."""
    now = datetime.now(timezone.utc)
    last_ok, last_fail = await _get_state("last_ok"), await _get_state("last_fail")
    due = (last_ok + timedelta(minutes=SYNC_INTERVAL_MIN)) if last_ok else now
    if last_fail and (last_ok is None or last_fail > last_ok):
        due = max(due, last_fail + timedelta(minutes=RETRY_MIN)) if last_ok else last_fail + timedelta(minutes=RETRY_MIN)
    return due


async def _purge_other_source() -> None:
    """Supprime les sorties de l'autre source (FRAnime = n° > 0, AniList = n° < 0).

    Sans ça, après un changement de CALENDAR_SOURCE, les anciennes lignes resteraient affichées
    (et déclencheraient encore des alertes) tant que la nouvelle source n'a pas répondu.
    """
    async with async_session() as db:
        other = CalendarEntry.franime_id < 0 if SOURCE == "franime" else CalendarEntry.franime_id > 0
        await db.execute(delete(CalendarEntry).where(other))
        await db.commit()


async def _sync_franime() -> dict:
    """Lit la page FRAnime et met la base à jour. Ne supprime rien en cas de panne."""
    async with _sync_lock:
        try:
            page = await _download()
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"page injoignable : {exc}"}
        parsed = parse_calendar(page)
        if not parsed:
            return {
                "ok": False,
                "error": "aucune sortie reconnue dans la page",
                "page_size": len(page),
                "has_anime_links": "anime_id=" in page,
            }

        created = updated = linked = 0
        async with async_session() as db:
            lo = min(p["release_at"] for p in parsed) - timedelta(days=1)
            existing = {
                (e.franime_id, e.season_raw, e.episode_number, e.language): e
                for e in (
                    await db.execute(select(CalendarEntry).where(CalendarEntry.release_at >= lo))
                ).scalars()
            }
            matches: dict[str, int | None] = {}
            for p in parsed:
                if p["title"] not in matches:
                    matches[p["title"]] = (await find_anime(db, p["title"]))[0]
                sure = matches[p["title"]]
                entry = existing.get((p["franime_id"], p["season_raw"], p["episode_number"], p["language"]))
                if entry is None:
                    db.add(CalendarEntry(anime_id=sure, **p))
                    created += 1
                    continue
                changed = False
                if entry.notified_at is None and entry.release_at != p["release_at"]:
                    entry.release_at = p["release_at"]
                    changed = True
                if entry.title != p["title"]:
                    entry.title = p["title"]
                    changed = True
                if entry.anime_id is None and sure:
                    entry.anime_id = sure
                    linked += 1
                    changed = True
                updated += int(changed)
            await db.execute(
                delete(CalendarEntry).where(
                    CalendarEntry.release_at < datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)
                )
            )
            await db.commit()
        return {"ok": True, "total": len(parsed), "new": created, "updated": updated, "linked": linked}


# ── Source AniList (VO en VOSTFR + créneaux VF) ───────────────────────

_SEASON_RES = (
    re.compile(r"(?:season|saison)\s*(\d+)", re.I),
    re.compile(r"(\d+)(?:st|nd|rd|th)\s+season", re.I),
    re.compile(r"\bS(\d+)\b"),
)
_SEASON_STRIP = re.compile(
    r"\s*[:\-–]?\s*(?:(?:season|saison)\s*\d+|\d+(?:st|nd|rd|th)\s+season|\bS\d+\b)\s*(?:part\s*\d+)?\s*$", re.I
)


def _anilist_season(titles: list[str]) -> str:
    """« Frieren Season 2 » -> « 2 » (1 si aucun numéro de saison dans les noms)."""
    for name in titles:
        for rx in _SEASON_RES:
            m = rx.search(name)
            if m and 1 <= int(m.group(1)) <= 30:
                return str(int(m.group(1)))
    return "1"


def _without_season(name: str) -> str:
    return _SEASON_STRIP.sub("", name).strip()


def _vf_time(vo_at: datetime, hour: int, minute: int) -> datetime:
    """Même jour que la VO (jour UTC), à l'heure VF (UTC)."""
    d = vo_at.astimezone(timezone.utc)
    return datetime(d.year, d.month, d.day, hour, minute, tzinfo=timezone.utc)


async def _match_anilist_anime(db, anilist_id: int, titles: list[str]) -> int | None:
    row = (await db.execute(select(Anime.id).where(Anime.anilist_id == anilist_id))).first()
    if row:
        return row[0]
    seen: set[str] = set()
    for name in [*titles[:3], *(_without_season(t) for t in titles[:3])]:
        if not name or name in seen:
            continue
        seen.add(name)
        sure = (await find_anime(db, name))[0]
        if sure:
            return sure
    return None


async def ensure_vf_entries(db, anilist_id: int, hour: int, minute: int, existing: dict | None = None) -> int:
    """Crée / déplace les sorties VF d'un animé d'après ses sorties VO déjà connues. Renvoie le nombre touché."""
    key_id = -anilist_id
    since = datetime.now(timezone.utc) - timedelta(days=2)
    vos = (
        await db.execute(
            select(CalendarEntry).where(
                CalendarEntry.franime_id == key_id,
                CalendarEntry.language == "VOSTFR",
                CalendarEntry.release_at >= since,
            )
        )
    ).scalars().all()
    if existing is None:
        existing = {
            (e.season_raw, e.episode_number): e
            for e in (
                await db.execute(
                    select(CalendarEntry).where(
                        CalendarEntry.franime_id == key_id,
                        CalendarEntry.language == "VF",
                        CalendarEntry.release_at >= since - timedelta(days=1),
                    )
                )
            ).scalars()
        }
    touched = 0
    for vo in vos:
        when = _vf_time(vo.release_at, hour, minute)
        vf = existing.get((vo.season_raw, vo.episode_number))
        if vf is None:
            db.add(
                CalendarEntry(
                    franime_id=key_id, slug=vo.slug, title=vo.title, season_raw=vo.season_raw,
                    episode_number=vo.episode_number, language="VF", release_at=when, anime_id=vo.anime_id,
                )
            )
            touched += 1
        elif vf.release_at != when and vf.notified_at is None:
            vf.release_at = when
            touched += 1
    return touched


async def set_vf_slot(anilist_id: int, hour: int, minute: int) -> int:
    """Enregistre l'heure VF d'un animé et met le calendrier à jour tout de suite."""
    async with async_session() as db:
        slot = await db.get(CalendarVfSlot, anilist_id)
        if slot is None:
            db.add(CalendarVfSlot(anilist_id=anilist_id, hour=hour, minute=minute))
        else:
            slot.hour, slot.minute = hour, minute
        await db.flush()
        n = await ensure_vf_entries(db, anilist_id, hour, minute)
        await db.commit()
        return n


async def remove_vf_slot(anilist_id: int) -> int:
    """Supprime l'heure VF : les sorties VF à venir (non encore alertées) disparaissent du calendrier."""
    async with async_session() as db:
        slot = await db.get(CalendarVfSlot, anilist_id)
        if slot is not None:
            await db.delete(slot)
        res = await db.execute(
            delete(CalendarEntry).where(
                CalendarEntry.franime_id == -anilist_id,
                CalendarEntry.language == "VF",
                CalendarEntry.notified_at.is_(None),
                CalendarEntry.release_at > datetime.now(timezone.utc),
            )
        )
        await db.commit()
        return res.rowcount or 0


async def sync_anilist() -> dict:
    """Lit les sorties de la semaine sur AniList (VO, en UTC) et met la base à jour."""
    async with _sync_lock:
        now = datetime.now(timezone.utc)
        try:
            airings = await anilist.airing_schedule(now - timedelta(days=2), now + timedelta(days=9))
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"AniList injoignable : {exc}"}
        if not airings:
            return {"ok": False, "error": "AniList n'a renvoyé aucune sortie"}

        created = updated = linked = 0
        async with async_session() as db:
            slots = {s.anilist_id: (s.hour, s.minute) for s in (await db.execute(select(CalendarVfSlot))).scalars()}
            lo = min(a["airing_at"] for a in airings) - timedelta(days=2)
            existing = {
                (e.franime_id, e.season_raw, e.episode_number, e.language): e
                for e in (
                    await db.execute(
                        select(CalendarEntry).where(CalendarEntry.franime_id < 0, CalendarEntry.release_at >= lo)
                    )
                ).scalars()
            }
            matches: dict[int, int | None] = {}

            def upsert(fid, season, ep, lang, title, at, anime_id):
                nonlocal created, updated, linked
                entry = existing.get((fid, season, ep, lang))
                if entry is None:
                    entry = CalendarEntry(
                        franime_id=fid, slug="", title=title[:500], season_raw=season, episode_number=ep,
                        language=lang, release_at=at, anime_id=anime_id,
                    )
                    db.add(entry)
                    existing[(fid, season, ep, lang)] = entry
                    created += 1
                    return
                changed = False
                if entry.notified_at is None and entry.release_at != at:
                    entry.release_at = at
                    changed = True
                if entry.title != title[:500]:
                    entry.title = title[:500]
                    changed = True
                if entry.anime_id is None and anime_id:
                    entry.anime_id = anime_id
                    linked += 1
                    changed = True
                updated += int(changed)

            for a in airings:
                al_id = a["anilist_id"]
                if al_id not in matches:
                    matches[al_id] = await _match_anilist_anime(db, al_id, a["titles"])
                anime_id = matches[al_id]
                season = _anilist_season(a["titles"])
                fid = -al_id
                upsert(fid, season, a["episode"], "VOSTFR", a["title"], a["airing_at"], anime_id)
                if al_id in slots:
                    h, m = slots[al_id]
                    upsert(fid, season, a["episode"], "VF", a["title"], _vf_time(a["airing_at"], h, m), anime_id)

            await db.execute(
                delete(CalendarEntry).where(
                    CalendarEntry.release_at < datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)
                )
            )
            await db.commit()
        return {"ok": True, "total": len(airings), "new": created, "updated": updated, "linked": linked}


# ── Alertes aux admins ─────────────────────────────────────────────────


def _bot_ready():
    try:
        from bot.client import bot
    except Exception:  # noqa: BLE001
        return None
    return bot if getattr(bot, "is_connected", False) else None


async def build_alert(db, entry: CalendarEntry) -> str:
    release = entry.release_at.astimezone(timezone.utc)
    lines = [
        "🔔 NOUVEL ÉPISODE SORTI",
        "",
        f"📺 {entry.title}",
        f"🌐 Langue : {entry.language}",
        f"📅 {season_label(entry.season_raw)} · Épisode {entry.episode_number}",
        f"🕐 Sortie : {JOURS[release.weekday()]} {release:%d/%m} à {release:%H:%M} UTC (Lomé/Togo)",
    ]
    main = season_main(entry.season_raw)
    opt = f"{entry.language} S{main:02d}" if main is not None else entry.language

    anime_id, cands = (entry.anime_id, [])
    if anime_id is None:
        anime_id, cands = await find_anime(db, entry.title)
    if anime_id is not None:
        anime = await db.get(Anime, anime_id)
        status = await episode_status(db, anime_id, entry.season_raw, entry.episode_number, entry.language)
        lines += [
            f"📌 État : {state_text(status)}",
            "",
            f"🆔 n°{anime_id} — {anime.title if anime else '?'}",
            f"➡️ /anime {anime_id} {opt}",
            "puis envoie l'épisode.",
        ]
    elif cands:
        names = {a.id: a.title for a in (await db.execute(select(Anime).where(Anime.id.in_(cands)))).scalars()}
        lines += [
            "",
            "🆔 Pas de correspondance exacte. Candidats : "
            + " · ".join(f"n°{c} {names.get(c, '?')}" for c in cands),
            f"➡️ /anime <n°> {opt}  — ou /ajouter {entry.title}",
        ]
    else:
        lines += ["", "🆔 Absent du catalogue.", f"➡️ /ajouter {entry.title}"]
    return "\n".join(lines)


async def _send_alert(bot, entry: CalendarEntry, text: str) -> dict[str, int]:
    from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔎 Vérifier si publié", callback_data=f"cal:chk:{entry.id}")]]
    )
    pins: dict[str, int] = {}
    for admin_id in settings.TELEGRAM_ADMIN_IDS:
        try:
            msg = await bot.send_message(admin_id, text, reply_markup=markup)
        except Exception as exc:  # noqa: BLE001 — ex. l'admin n'a jamais écrit au bot
            logger.warning("Calendrier: envoi impossible à %s : %s", admin_id, exc)
            continue
        pins[str(admin_id)] = msg.id
        try:
            await bot.pin_chat_message(admin_id, msg.id, disable_notification=False, both_sides=True)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Calendrier: épinglage impossible chez %s : %s", admin_id, exc)
        await asyncio.sleep(0.4)
    return pins


async def unpin_entry(entry: CalendarEntry) -> None:
    """Désépingle les messages de cette sortie (l'appelant fait le commit)."""
    bot = _bot_ready()
    if bot is None or not entry.pins or entry.unpinned_at is not None:
        return
    for admin_id, msg_id in entry.pins.items():
        try:
            await bot.unpin_chat_message(int(admin_id), int(msg_id))
        except Exception as exc:  # noqa: BLE001
            logger.info("Calendrier: désépinglage impossible chez %s : %s", admin_id, exc)
    entry.unpinned_at = datetime.now(timezone.utc)


async def notify_due() -> int:
    """Envoie les alertes arrivées à échéance. Renvoie le nombre de sorties notifiées."""
    now = datetime.now(timezone.utc)
    sent = 0
    async with async_session() as db:
        due = (
            await db.execute(
                select(CalendarEntry)
                .where(
                    CalendarEntry.notified_at.is_(None),
                    CalendarEntry.release_at <= now - timedelta(minutes=NOTIFY_DELAY_MIN),
                )
                .order_by(CalendarEntry.release_at)
            )
        ).scalars().all()
        bot = _bot_ready()
        for entry in due:
            if entry.release_at < now - timedelta(hours=NOTIFY_MAX_AGE_H):
                entry.notified_at = now  # découverte trop tard (ex. serveur éteint) : on ne spamme pas
                continue
            if bot is None:
                continue
            if entry.franime_id < 0 and entry.anime_id is None:
                entry.notified_at = now  # source AniList : on n'alerte que pour les animés du catalogue
                continue
            pins = await _send_alert(bot, entry, await build_alert(db, entry))
            if pins:
                entry.notified_at = now
                entry.pins = pins
                sent += 1
        await db.commit()
    return sent


async def cleanup_pins() -> None:
    now = datetime.now(timezone.utc)
    async with async_session() as db:
        rows = (
            await db.execute(
                select(CalendarEntry).where(
                    CalendarEntry.notified_at.isnot(None),
                    CalendarEntry.unpinned_at.is_(None),
                    CalendarEntry.release_at < now - timedelta(hours=UNPIN_AFTER_H),
                )
            )
        ).scalars().all()
        for entry in rows:
            if not entry.pins:
                entry.unpinned_at = now
            else:
                await unpin_entry(entry)
        await db.commit()


# ── Boucle de fond ─────────────────────────────────────────────────────


async def _loop() -> None:
    await asyncio.sleep(30)  # laisse l'API et le bot finir de démarrer
    while True:
        try:
            if datetime.now(timezone.utc) >= await next_sync_at():
                result = await sync_calendar()  # enregistre lui-même la date de réussite / d'échec
                if result.get("ok"):
                    logger.info(
                        "Calendrier: %s sorties lues, %s nouvelles, %s mises à jour.",
                        result["total"], result["new"], result["updated"],
                    )
                else:
                    logger.warning("Calendrier: %s. Nouvel essai dans %s min.", result.get("error"), RETRY_MIN)
            sent = await notify_due()
            if sent:
                logger.info("Calendrier: %s alerte(s) envoyée(s) aux admins.", sent)
            await cleanup_pins()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — la boucle ne doit jamais mourir
            logger.exception("Calendrier: cycle interrompu par une erreur")
        await asyncio.sleep(60)


def start_loop() -> None:
    global _task
    if not ENABLED:
        logger.info("Calendrier désactivé (CALENDAR_SYNC_ENABLED=false).")
        return
    if _task is None or _task.done():
        _task = asyncio.create_task(_loop(), name="calendar-sync")
        logger.info(
            "Calendrier démarré (lecture toutes les %s min, alerte +%s min).", SYNC_INTERVAL_MIN, NOTIFY_DELAY_MIN
        )


async def stop_loop() -> None:
    global _task
    if _task is not None and not _task.done():
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
    _task = None
