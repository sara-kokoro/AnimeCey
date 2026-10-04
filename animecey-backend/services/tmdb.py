"""TMDB API service with caching in the ``tmdb_cache`` table."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models import TmdbCache

logger = logging.getLogger(__name__)

CACHE_SEARCH_TTL = timedelta(hours=24)
CACHE_DETAILS_TTL = timedelta(days=7)


async def _get_cache(db: AsyncSession, key: str, ttl: timedelta):
    result = await db.execute(select(TmdbCache).where(TmdbCache.cache_key == key))
    entry = result.scalar_one_or_none()
    if entry is None:
        return None
    if datetime.now(timezone.utc) - entry.cached_at.replace(tzinfo=timezone.utc) > ttl:
        await db.execute(delete(TmdbCache).where(TmdbCache.id == entry.id))
        await db.commit()
        return None
    return json.loads(entry.data_json)


async def _set_cache(db: AsyncSession, key: str, data):
    result = await db.execute(select(TmdbCache).where(TmdbCache.cache_key == key))
    entry = result.scalar_one_or_none()
    payload = json.dumps(data, ensure_ascii=False)
    if entry:
        entry.data_json = payload
        entry.cached_at = datetime.now(timezone.utc)
    else:
        db.add(TmdbCache(cache_key=key, data_json=payload, cached_at=datetime.now(timezone.utc)))
    await db.commit()


async def search(query: str, db: AsyncSession, language: str = "fr-FR") -> list[dict]:
    cache_key = f"tmdb:search:{query}:{language}"
    cached = await _get_cache(db, cache_key, CACHE_SEARCH_TTL)
    if cached is not None:
        return cached

    url = f"{settings.TMDB_BASE_URL}/search/multi"
    params = {"api_key": settings.TMDB_API_KEY, "query": query, "language": language}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    results = [
        r for r in data.get("results", []) if r.get("media_type") in ("tv", "movie")
    ]
    await _set_cache(db, cache_key, results)
    return results


async def get_details(tmdb_id: int, media_type: str, db: AsyncSession, language: str = "fr-FR") -> dict:
    cache_key = f"tmdb:details:{media_type}:{tmdb_id}:{language}"
    cached = await _get_cache(db, cache_key, CACHE_DETAILS_TTL)
    if cached is not None:
        return cached

    base = settings.TMDB_BASE_URL
    api_key = settings.TMDB_API_KEY
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{base}/{media_type}/{tmdb_id}",
            params={"api_key": api_key, "language": language},
        )
        resp.raise_for_status()
        details = resp.json()

        videos_resp = await client.get(
            f"{base}/{media_type}/{tmdb_id}/videos",
            params={"api_key": api_key, "language": language},
        )
        if videos_resp.is_success:
            videos = videos_resp.json().get("results", [])
            trailer = next(
                (v for v in videos if v.get("type") == "Trailer" and v.get("site") == "YouTube"),
                None,
            )
            if trailer:
                details["trailer_url"] = f"https://www.youtube.com/embed/{trailer['key']}"

    await _set_cache(db, cache_key, details)
    return details


async def get_season(tmdb_id: int, season_number: int, db: AsyncSession, language: str = "fr-FR") -> dict:
    """Détail d'une saison TMDB : liste des épisodes (titre, vignette, résumé)."""
    cache_key = f"tmdb:season:{tmdb_id}:{season_number}:{language}"
    cached = await _get_cache(db, cache_key, CACHE_DETAILS_TTL)
    if cached is not None:
        return cached
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{settings.TMDB_BASE_URL}/tv/{tmdb_id}/season/{season_number}",
            params={"api_key": settings.TMDB_API_KEY, "language": language},
        )
        resp.raise_for_status()
        data = resp.json()
    await _set_cache(db, cache_key, data)
    return data
