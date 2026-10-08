"""Calendrier des sorties (public).

  GET /api/calendar?week=0     sorties de la semaine (0 = cette semaine, -1 = précédente, 1 = suivante)

Les heures sont renvoyées en UTC : c'est le navigateur qui les affiche dans l'heure locale
du visiteur. `available` = l'épisode est déjà en ligne sur le site.

Mettre ce fichier dans routers/calendar.py.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Anime, Episode
from models_calendar import CalendarEntry
from models_catalog import EpisodeServer
from services import calendar_sync

router = APIRouter()


@router.get("")
async def get_calendar(week: int = Query(0, ge=-4, le=4), db: AsyncSession = Depends(get_db)):
    tz = ZoneInfo(calendar_sync.SOURCE_TZ)
    today = datetime.now(tz).date()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=week)
    # marge d'un jour de chaque côté : le navigateur range les sorties selon son fuseau
    start = datetime(monday.year, monday.month, monday.day, tzinfo=tz).astimezone(timezone.utc) - timedelta(days=1)
    end = start + timedelta(days=9)

    entries = (
        await db.execute(
            select(CalendarEntry)
            .where(CalendarEntry.release_at >= start, CalendarEntry.release_at < end)
            .order_by(CalendarEntry.release_at, CalendarEntry.title)
        )
    ).scalars().all()

    anime_ids = {e.anime_id for e in entries if e.anime_id}
    posters: dict[int, str | None] = {}
    online: set[tuple[int, str, int, int]] = set()
    if anime_ids:
        posters = dict((await db.execute(select(Anime.id, Anime.poster_url).where(Anime.id.in_(anime_ids)))).all())
        rows = (
            await db.execute(
                select(Episode).where(
                    Episode.anime_id.in_(anime_ids),
                    Episode.episode_number.in_({e.episode_number for e in entries}),
                )
            )
        ).scalars().all()
        with_servers: set[int] = set()
        if rows:
            with_servers = set(
                (
                    await db.execute(
                        select(EpisodeServer.episode_id).where(EpisodeServer.episode_id.in_([r.id for r in rows]))
                    )
                ).scalars()
            )
        for r in rows:
            if r.servcey1_available or r.servcey2_available or r.stream_url or r.id in with_servers:
                online.add((r.anime_id, r.language.value, r.episode_number, r.season_number))

    items = []
    for e in entries:
        main = calendar_sync.season_main(e.season_raw)
        items.append(
            {
                "id": e.id,
                "title": e.title,
                "anime_id": e.anime_id,
                "poster_url": posters.get(e.anime_id) if e.anime_id else None,
                "season": calendar_sync.season_label(e.season_raw),
                "episode": e.episode_number,
                "language": e.language,
                "release_at": e.release_at.astimezone(timezone.utc).isoformat(),
                "available": bool(e.anime_id and main is not None and (e.anime_id, e.language, e.episode_number, main) in online),
            }
        )
    return {"week_start": monday.isoformat(), "entries": items}
