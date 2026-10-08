"""Calendrier des sorties : copie de franime.fr/calendrier + alertes aux admins.

Ce que fait ce module :
  1. toutes les CALENDAR_SYNC_INTERVAL_MIN minutes (30 par défaut), télécharge la page
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

Les heures affichées par FRAnime sont en heure française : on les convertit en UTC
(Lomé/Togo = UTC+0). Le passage heure d'été/hiver est géré tout seul.

Variables d'environnement (toutes optionnelles) :
  CALENDAR_SYNC_ENABLED       true / false                        (défaut : true)
  CALENDAR_SYNC_INTERVAL_MIN  minutes entre 2 lectures de la page (défaut : 30)
  CALENDAR_NOTIFY_DELAY_MIN   minutes après la sortie             (défaut : 30)
  CALENDAR_NOTIFY_MAX_AGE_H   au-delà, une sortie découverte trop tard est ignorée
                              sans message (défaut : 12)
  CALENDAR_UNPIN_AFTER_H      heures avant de désépingler          (défaut : 24)
  CALENDAR_SOURCE_URL         page à lire (défaut : https://franime.fr/calendrier)
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
from models_calendar import CalendarEntry
from models_catalog import EpisodeServer
from services import search_fuzzy

logger = logging.getLogger(__name__)

ENABLED = os.getenv("CALENDAR_SYNC_ENABLED", "true").lower() in ("true", "1", "yes")
SOURCE_URL = os.getenv("CALENDAR_SOURCE_URL", "https://franime.fr/calendrier")
SOURCE_TZ = os.getenv("CALENDAR_SOURCE_TZ", "Europe/Paris")
SYNC_INTERVAL_MIN = max(5, int(os.getenv("CALENDAR_SYNC_INTERVAL_MIN", "30")))
NOTIFY_DELAY_MIN = max(0, int(os.getenv("CALENDAR_NOTIFY_DELAY_MIN", "30")))
NOTIFY_MAX_AGE_H = max(1, int(os.getenv("CALENDAR_NOTIFY_MAX_AGE_H", "12")))
UNPIN_AFTER_H = max(1, int(os.getenv("CALENDAR_UNPIN_AFTER_H", "24")))
KEEP_DAYS = 21
RETRY_SEC = 300

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
            lang_code = (q.get("lang") or ["vo"])[0].lower()
            season_raw = (q.get("s") or ["1"])[0].strip() or "1"
            slug = url.path.rstrip("/").split("/")[-1]
        except (KeyError, ValueError, IndexError):
            continue

        episode = hour = minute = None
        titles: list[str] = []
        for text in raw["texts"]:
            m = re.fullmatch(r"E\s?(\d+)", text)
            if m and episode is None:
                episode = int(m.group(1))
                continue
            m = re.fullmatch(r"(\d{1,2})\s*h\s*(\d{2})", text)
            if m and hour is None:
                hour, minute = int(m.group(1)), int(m.group(2))
                continue
            titles.append(text)
        if episode is None or hour is None:  # textes collés dans un seul bloc
            m = re.match(r"E\s?(\d+)(.*?)(\d{1,2})\s*h\s*(\d{2})", "".join(raw["texts"]))
            if m:
                episode, hour, minute = int(m.group(1)), int(m.group(3)), int(m.group(4))
                titles = [m.group(2).strip()] if m.group(2).strip() else []
        if episode is None or hour is None or raw["day"] is None:
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


async def _download() -> str:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "fr-FR,fr;q=0.9",
    }
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0, headers=headers) as client:
        resp = await client.get(SOURCE_URL)
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}")
    return resp.text


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
    next_sync = 0.0
    while True:
        try:
            if time.monotonic() >= next_sync:
                result = await sync_calendar()
                if result.get("ok"):
                    logger.info(
                        "Calendrier: %s sorties lues, %s nouvelles, %s mises à jour.",
                        result["total"], result["new"], result["updated"],
                    )
                    next_sync = time.monotonic() + SYNC_INTERVAL_MIN * 60
                else:
                    logger.warning("Calendrier: %s. Nouvel essai dans 5 min.", result.get("error"))
                    next_sync = time.monotonic() + RETRY_SEC
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
