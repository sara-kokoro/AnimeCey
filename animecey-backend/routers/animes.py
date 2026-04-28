from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Anime, Episode, LanguageEnum, WatchHistory
from schemas import AnimePublic

router = APIRouter()


def _anime_to_public(anime: Anime, languages: list[str], seasons: int, ep_count: int) -> dict:
    d = AnimePublic.model_validate(anime).model_dump()
    d["languages_available"] = languages
    d["seasons_count"] = seasons
    d["episodes_count"] = ep_count
    return d


async def _enrich_animes(db: AsyncSession, animes: list[Anime]) -> list[dict]:
    if not animes:
        return []
    ids = [a.id for a in animes]

    lang_q = await db.execute(
        select(Episode.anime_id, func.string_agg(distinct(Episode.language), ','))
        .where(Episode.anime_id.in_(ids))
        .group_by(Episode.anime_id)
    )
    lang_map: dict[int, list[str]] = {}
    for row in lang_q.all():
        lang_map[row[0]] = [l.strip() for l in (row[1] or "").split(",") if l.strip()]

    season_q = await db.execute(
        select(Episode.anime_id, func.count(distinct(Episode.season_number)))
        .where(Episode.anime_id.in_(ids))
        .group_by(Episode.anime_id)
    )
    season_map = dict(season_q.all())

    ep_q = await db.execute(
        select(Episode.anime_id, func.count())
        .where(Episode.anime_id.in_(ids))
        .group_by(Episode.anime_id)
    )
    ep_map = dict(ep_q.all())

    return [
        _anime_to_public(
            a,
            lang_map.get(a.id, []),
            season_map.get(a.id, 0),
            ep_map.get(a.id, 0),
        )
        for a in animes
    ]


@router.get("")
async def list_animes(
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=100),
    sort: Optional[str] = None,
    type: Optional[str] = None,
    status: Optional[str] = None,
    genre: Optional[str] = None,
    language: Optional[str] = None,
    year: Optional[int] = None,
    q: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Anime)

    if q:
        query = query.where(Anime.title.ilike(f"%{q}%") | Anime.title_jp.ilike(f"%{q}%"))
    if type:
        query = query.where(Anime.type == type)
    if status:
        query = query.where(Anime.status == status)
    if genre:
        query = query.where(Anime.genres.ilike(f'%"{genre}"%'))
    if year:
        query = query.where(Anime.year == year)

    if language and language in ("VF", "VOSTFR"):
        sub = select(distinct(Episode.anime_id)).where(Episode.language == language)
        query = query.where(Anime.id.in_(sub))
    elif language == "BOTH":
        sub_vf = select(distinct(Episode.anime_id)).where(Episode.language == LanguageEnum.VF)
        sub_vo = select(distinct(Episode.anime_id)).where(Episode.language == LanguageEnum.VOSTFR)
        query = query.where(Anime.id.in_(sub_vf)).where(Anime.id.in_(sub_vo))

    if sort == "za":
        query = query.order_by(Anime.title.desc())
    elif sort == "score":
        query = query.order_by(Anime.score.desc())
    elif sort == "recent":
        query = query.order_by(Anime.created_at.desc())
    else:
        query = query.order_by(Anime.title.asc())

    total_q = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_q.scalar() or 0
    pages = max(1, math.ceil(total / limit))

    result = await db.execute(query.offset((page - 1) * limit).limit(limit))
    animes = list(result.scalars().all())
    items = await _enrich_animes(db, animes)
    return {"items": items, "total": total, "page": page, "pages": pages}


@router.get("/featured")
async def featured(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Anime).where(Anime.is_featured == True).order_by(func.random()).limit(8)
    )
    animes = list(result.scalars().all())
    return await _enrich_animes(db, animes)


@router.get("/top-week")
async def top_week(db: AsyncSession = Depends(get_db)):
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    sub = (
        select(Episode.anime_id, func.count().label("cnt"))
        .join(WatchHistory, WatchHistory.episode_id == Episode.id)
        .where(WatchHistory.watched_at >= week_ago)
        .group_by(Episode.anime_id)
        .order_by(func.count().desc())
        .limit(12)
        .subquery()
    )
    result = await db.execute(select(Anime).join(sub, Anime.id == sub.c.anime_id))
    animes = list(result.scalars().all())
    return await _enrich_animes(db, animes)


@router.get("/top-rated")
async def top_rated(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Anime).order_by(Anime.score.desc()).limit(12))
    return await _enrich_animes(db, list(result.scalars().all()))


@router.get("/latest")
async def latest(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Anime).order_by(Anime.created_at.desc()).limit(12))
    return await _enrich_animes(db, list(result.scalars().all()))


@router.get("/trending")
async def trending(db: AsyncSession = Depends(get_db)):
    month_ago = datetime.now(timezone.utc) - timedelta(days=30)
    sub = (
        select(Episode.anime_id, func.count().label("cnt"))
        .join(WatchHistory, WatchHistory.episode_id == Episode.id)
        .where(WatchHistory.watched_at >= month_ago)
        .group_by(Episode.anime_id)
        .order_by(func.count().desc())
        .limit(12)
        .subquery()
    )
    result = await db.execute(select(Anime).join(sub, Anime.id == sub.c.anime_id))
    animes = list(result.scalars().all())
    return await _enrich_animes(db, animes)


@router.get("/{anime_id}")
async def get_anime(anime_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Anime).where(Anime.id == anime_id))
    anime = result.scalar_one_or_none()
    if not anime:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Animé introuvable")
    items = await _enrich_animes(db, [anime])
    return items[0]
