"""Sorties de films et de séries lues sur TMDB, avec alerte aux admins le jour de la sortie.

Ce que fait ce module :
  1. tous les 3 jours (TMDB_RELEASES_INTERVAL_DAYS), lit sur TMDB, en quelques appels seulement :
       • les films qui sortent dans les 60 prochains jours (les plus populaires),
       • les nouvelles séries qui démarrent dans les 60 prochains jours,
       • le prochain épisode de chaque série live-action DÉJÀ au catalogue (1 appel par série) ;
     et les enregistre dans la table tmdb_releases. La date de la dernière lecture est gardée en base :
     un redémarrage du serveur ne relance rien.
  2. le jour de la sortie (à partir de TMDB_ALERT_HOUR_UTC, 7 h UTC par défaut), envoie à chaque admin
     du bot (TELEGRAM_ADMIN_IDS) une alerte avec l'affiche : titre, type, date, synopsis, et la commande
     pour l'ajouter (/add ou /ajouter) ou le n° s'il est déjà au catalogue. Une seule alerte par sortie.

Limites de TMDB : il donne la DATE de sortie, pas l'heure (et la date du premier pays qui sort le film).
Les animés ne sont pas concernés par les épisodes : le calendrier FRAnime s'en charge (calendar_sync.py).

Variables d'environnement (toutes facultatives) :
  TMDB_RELEASES_ENABLED         true / false                                      (défaut : true)
  TMDB_RELEASES_INTERVAL_DAYS   jours entre 2 lectures                            (défaut : 3)
  TMDB_RELEASES_WINDOW_DAYS     combien de jours à l'avance on regarde            (défaut : 60)
  TMDB_RELEASES_MIN_POPULARITY  popularité TMDB minimale pour être retenu         (défaut : 10)
  TMDB_RELEASES_MAX_PAGES       pages de résultats par lecture (20 titres/page)   (défaut : 3)
  TMDB_RELEASES_MAX_TRACKED     séries du catalogue suivies pour leurs épisodes   (défaut : 150)
  TMDB_ALERT_HOUR_UTC           heure (UTC) à partir de laquelle on alerte le jour J (défaut : 7)
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import date, datetime, timedelta, timezone

import httpx
from sqlalchemy import delete, select

from config import settings
from database import async_session
from models import Anime, AnimeType
from models_calendar import CalendarState, TmdbRelease

logger = logging.getLogger(__name__)

ENABLED = os.getenv("TMDB_RELEASES_ENABLED", "true").lower() in ("true", "1", "yes")
INTERVAL_DAYS = max(1, int(os.getenv("TMDB_RELEASES_INTERVAL_DAYS", "3")))
WINDOW_DAYS = max(7, int(os.getenv("TMDB_RELEASES_WINDOW_DAYS", "60")))
MIN_POPULARITY = float(os.getenv("TMDB_RELEASES_MIN_POPULARITY", "10"))
MAX_PAGES = max(1, int(os.getenv("TMDB_RELEASES_MAX_PAGES", "3")))
MAX_TRACKED = max(0, int(os.getenv("TMDB_RELEASES_MAX_TRACKED", "150")))
ALERT_HOUR_UTC = min(23, max(0, int(os.getenv("TMDB_ALERT_HOUR_UTC", "7"))))
TICK_SEC = int(os.getenv("TMDB_RELEASES_TICK_SEC", "900"))
RETRY_HOURS = 6          # après un échec : on attend avant de réessayer (on ne martèle pas TMDB)
KEEP_DAYS = 30           # les sorties plus vieilles sont effacées
LATE_DAYS = 2            # une sortie découverte avec plus de 2 jours de retard n'est plus alertée
MAX_ALERTS_PER_CYCLE = 15
IMG = "https://image.tmdb.org/t/p/w500"
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
KIND_LABEL = {"movie": "Film", "premiere": "Nouvelle série", "episode": "Épisode"}

_sync_lock = asyncio.Lock()
_task: asyncio.Task | None = None


# ── Mémoire de la dernière lecture ─────────────────────────────────────


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
    now = datetime.now(timezone.utc)
    last_ok, last_fail = await _get_state("tmdb_rel_ok"), await _get_state("tmdb_rel_fail")
    due = (last_ok + timedelta(days=INTERVAL_DAYS)) if last_ok else now
    if last_fail and (last_ok is None or last_fail > last_ok):
        due = max(due, last_fail + timedelta(hours=RETRY_HOURS)) if last_ok else last_fail + timedelta(hours=RETRY_HOURS)
    return due


# ── Lecture TMDB ───────────────────────────────────────────────────────


def _parse_date(value: str | None) -> date | None:
    try:
        return date.fromisoformat((value or "")[:10])
    except ValueError:
        return None


async def _get(client: httpx.AsyncClient, path: str, **params) -> dict:
    resp = await client.get(
        f"{settings.TMDB_BASE_URL}{path}",
        params={"api_key": settings.TMDB_API_KEY, "language": "fr-FR", **params},
    )
    resp.raise_for_status()
    await asyncio.sleep(0.25)  # TMDB tolère ~50 appels/s ; on reste très en dessous
    return resp.json()


def _is_anime(r: dict) -> bool:
    return 16 in (r.get("genre_ids") or []) and r.get("original_language") == "ja"


async def _discover(client: httpx.AsyncClient, media: str, today: date, until: date) -> list[dict]:
    """Films (ou séries) qui sortent entre today et until, les plus populaires d'abord."""
    if media == "movie":
        path, gte, lte, dkey = "/discover/movie", "primary_release_date.gte", "primary_release_date.lte", "release_date"
    else:
        path, gte, lte, dkey = "/discover/tv", "first_air_date.gte", "first_air_date.lte", "first_air_date"
    out: list[dict] = []
    for page in range(1, MAX_PAGES + 1):
        data = await _get(
            client, path, sort_by="popularity.desc", include_adult="false", page=page,
            **{gte: today.isoformat(), lte: until.isoformat()},
        )
        results = data.get("results") or []
        for r in results:
            released = _parse_date(r.get(dkey))
            if released is None or (r.get("popularity") or 0) < MIN_POPULARITY:
                continue
            out.append(
                {
                    "tmdb_id": int(r["id"]),
                    "media": media,
                    "kind": "movie" if media == "movie" else "premiere",
                    "season_number": 0,
                    "episode_number": 0,
                    "title": (r.get("title") or r.get("name") or "?")[:500],
                    "original_title": (r.get("original_title") or r.get("original_name") or None),
                    "overview": r.get("overview") or None,
                    "poster_path": r.get("poster_path"),
                    "popularity": float(r.get("popularity") or 0),
                    "is_anime": _is_anime(r),
                    "release_date": released,
                }
            )
        # triés par popularité décroissante : dès qu'une page passe sous le seuil, la suite aussi
        if not results or page >= (data.get("total_pages") or 1) or (results[-1].get("popularity") or 0) < MIN_POPULARITY:
            break
    return out


async def _tracked_episodes(client: httpx.AsyncClient, today: date) -> list[dict]:
    """Prochain épisode (et dernier épisode récent) des séries live-action du catalogue."""
    if MAX_TRACKED == 0:
        return []
    async with async_session() as db:
        rows = (
            await db.execute(
                select(Anime.id, Anime.tmdb_id)
                .where(Anime.category == "live", Anime.type == AnimeType.serie, Anime.tmdb_id.is_not(None))
                .order_by(Anime.id.desc())
                .limit(MAX_TRACKED)
            )
        ).all()
    out: list[dict] = []
    for row in rows:
        try:
            tv = await _get(client, f"/tv/{row.tmdb_id}")
        except httpx.HTTPStatusError:
            continue  # fiche disparue chez TMDB : on passe
        for key in ("next_episode_to_air", "last_episode_to_air"):
            ep = tv.get(key) or {}
            released = _parse_date(ep.get("air_date"))
            if released is None or not ep.get("episode_number"):
                continue
            if key == "last_episode_to_air" and released < today - timedelta(days=LATE_DAYS):
                continue  # dernier épisode déjà ancien : inutile
            out.append(
                {
                    "tmdb_id": int(row.tmdb_id),
                    "media": "tv",
                    "kind": "episode",
                    "season_number": int(ep.get("season_number") or 0),
                    "episode_number": int(ep["episode_number"]),
                    "title": (tv.get("name") or "?")[:500],
                    "original_title": tv.get("original_name"),
                    "episode_title": (ep.get("name") or None),
                    "overview": ep.get("overview") or tv.get("overview") or None,
                    "poster_path": tv.get("poster_path"),
                    "popularity": float(tv.get("popularity") or 0),
                    "is_anime": False,
                    "release_date": released,
                }
            )
    return out


async def _save(items: list[dict]) -> dict:
    """Enregistre les sorties (nouvelles ou mises à jour) et les relie au catalogue."""
    new = updated = 0
    today = datetime.now(timezone.utc).date()
    async with async_session() as db:
        catalog = {
            tid: aid
            for tid, aid in (await db.execute(select(Anime.tmdb_id, Anime.id).where(Anime.tmdb_id.is_not(None)))).all()
        }
        for it in items:
            row = (
                await db.execute(
                    select(TmdbRelease).where(
                        TmdbRelease.tmdb_id == it["tmdb_id"],
                        TmdbRelease.media == it["media"],
                        TmdbRelease.kind == it["kind"],
                        TmdbRelease.season_number == it["season_number"],
                        TmdbRelease.episode_number == it["episode_number"],
                    )
                )
            ).scalars().first()
            anime_id = catalog.get(it["tmdb_id"])
            if row is None:
                db.add(TmdbRelease(anime_id=anime_id, **it))
                new += 1
                continue
            moved_later = it["release_date"] > row.release_date and it["release_date"] >= today
            for field, value in it.items():
                if value is not None:
                    setattr(row, field, value)
            row.anime_id = anime_id
            if moved_later:
                row.notified_at = None  # sortie repoussée : on prévient de nouveau à la nouvelle date
            updated += 1
        await db.execute(delete(TmdbRelease).where(TmdbRelease.release_date < today - timedelta(days=KEEP_DAYS)))
        await db.commit()
    return {"new": new, "updated": updated}


async def sync_releases() -> dict:
    """Lit TMDB et enregistre les sorties. Ne lève jamais d'exception : renvoie {"ok": False, "error": ...}."""
    if _sync_lock.locked():
        return {"ok": False, "error": "une lecture est déjà en cours"}
    async with _sync_lock:
        try:
            today = datetime.now(timezone.utc).date()
            until = today + timedelta(days=WINDOW_DAYS)
            async with httpx.AsyncClient(timeout=20) as client:
                movies = await _discover(client, "movie", today, until)
                premieres = await _discover(client, "tv", today, until)
                episodes = await _tracked_episodes(client, today)
            result = await _save(movies + premieres + episodes)
            await _set_state("tmdb_rel_ok", datetime.now(timezone.utc).isoformat())
            return {"ok": True, "movies": len(movies), "premieres": len(premieres), "episodes": len(episodes), **result}
        except Exception as exc:  # noqa: BLE001
            logger.warning("Sorties TMDB : lecture impossible : %s", exc)
            await _set_state("tmdb_rel_fail", datetime.now(timezone.utc).isoformat())
            return {"ok": False, "error": str(exc)[:200]}


# ── Alertes aux admins ─────────────────────────────────────────────────


def _bot_ready():
    try:
        from bot.client import bot
    except Exception:  # noqa: BLE001
        return None
    return bot if getattr(bot, "is_connected", False) else None


def build_alert(r: TmdbRelease, today: date) -> str:
    late = (today - r.release_date).days
    when = "AUJOURD'HUI" if late <= 0 else ("HIER" if late == 1 else f"IL Y A {late} JOURS")
    head = {
        "movie": f"🎬 FILM : SORTIE {when}",
        "premiere": f"📺 NOUVELLE SÉRIE : SORTIE {when}",
        "episode": f"🔔 NOUVEL ÉPISODE : SORTIE {when}",
    }[r.kind]
    year = f" ({r.release_date.year})" if r.kind != "episode" else ""
    lines = [head, "", f"{r.title}{year}"]
    if r.kind == "episode":
        ep = f"S{r.season_number:02d}E{r.episode_number:02d}" + (f" « {r.episode_title} »" if r.episode_title else "")
        lines.append(f"Série — {ep}")
    else:
        lines.append(KIND_LABEL[r.kind] + (" d'animation japonaise" if r.is_anime else ""))
    lines.append(f"📅 {JOURS[r.release_date.weekday()].capitalize()} {r.release_date:%d/%m/%Y} (date TMDB)")
    over = (r.overview or "").strip().replace("\n", " ")
    if over:
        lines += ["", over[:300] + ("…" if len(over) > 300 else "")]
    lines.append("")
    if r.anime_id:
        lines.append(f"✅ Déjà au catalogue : n°{r.anime_id}")
        lines.append(f"➡️ /movie {r.anime_id} VF (ou VOSTFR), puis envoie le fichier")
    else:
        cmd = "/ajouter" if r.is_anime else "/add"
        lines.append(f"➕ Pas encore au catalogue : {cmd} {'movie' if r.media == 'movie' else 'tv'}:{r.tmdb_id}")
    return "\n".join(lines)[:1000]  # légende de photo : 1024 caractères maximum


async def _send_alert(bot, r: TmdbRelease, text: str) -> int:
    """Envoie l'alerte à chaque admin. Renvoie le nombre d'admins atteints."""
    reached = 0
    for admin_id in settings.TELEGRAM_ADMIN_IDS:
        try:
            if r.poster_path:
                try:
                    await bot.send_photo(admin_id, f"{IMG}{r.poster_path}", caption=text)
                except Exception:  # noqa: BLE001 — affiche illisible : l'alerte part sans image
                    await bot.send_message(admin_id, text)
            else:
                await bot.send_message(admin_id, text)
            reached += 1
        except Exception as exc:  # noqa: BLE001 — ex. l'admin n'a jamais écrit au bot
            logger.warning("Sorties TMDB : envoi impossible à %s : %s", admin_id, exc)
        await asyncio.sleep(0.4)
    return reached


async def notify_due() -> int:
    """Envoie les alertes du jour. Renvoie le nombre de sorties notifiées."""
    now = datetime.now(timezone.utc)
    today = now.date()
    sent = 0
    async with async_session() as db:
        due = (
            await db.execute(
                select(TmdbRelease)
                .where(TmdbRelease.notified_at.is_(None), TmdbRelease.release_date <= today)
                .order_by(TmdbRelease.popularity.desc())
            )
        ).scalars().all()
        bot = _bot_ready()
        for r in due:
            if (today - r.release_date).days > LATE_DAYS:
                r.notified_at = now  # découverte trop tard (serveur éteint, titre ajouté après coup) : pas de spam
                continue
            if r.release_date == today and now.hour < ALERT_HOUR_UTC:
                continue  # le jour J, mais pas encore l'heure d'alerte
            if bot is None or sent >= MAX_ALERTS_PER_CYCLE:
                continue
            if await _send_alert(bot, r, build_alert(r, today)):
                r.notified_at = now
                sent += 1
        await db.commit()
    return sent


# ── Boucle de fond ─────────────────────────────────────────────────────


async def _loop() -> None:
    await asyncio.sleep(45)  # laisse l'API et le bot finir de démarrer
    while True:
        try:
            if datetime.now(timezone.utc) >= await next_sync_at():
                res = await sync_releases()
                if res.get("ok"):
                    logger.info(
                        "Sorties TMDB : %s films, %s séries, %s épisodes lus (%s nouvelles).",
                        res["movies"], res["premieres"], res["episodes"], res["new"],
                    )
            sent = await notify_due()
            if sent:
                logger.info("Sorties TMDB : %s alerte(s) envoyée(s) aux admins.", sent)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — la boucle ne doit jamais mourir
            logger.exception("Sorties TMDB : cycle interrompu par une erreur")
        await asyncio.sleep(TICK_SEC)


def start_loop() -> None:
    global _task
    if not ENABLED:
        logger.info("Sorties TMDB désactivées (TMDB_RELEASES_ENABLED=false).")
        return
    if _task is None or _task.done():
        _task = asyncio.create_task(_loop(), name="tmdb-releases")
        logger.info("Sorties TMDB démarrées (lecture tous les %s jours, alerte dès %s h UTC).", INTERVAL_DAYS, ALERT_HOUR_UTC)


async def stop_loop() -> None:
    global _task
    if _task is not None and not _task.done():
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
    _task = None
