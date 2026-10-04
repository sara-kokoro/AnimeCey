"""AniList GraphQL API service with caching."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models import TmdbCache  # reuse same cache table

logger = logging.getLogger(__name__)

CACHE_SEARCH_TTL = timedelta(hours=24)
CACHE_DETAILS_TTL = timedelta(days=7)

SEARCH_QUERY = """
query ($search: String) {
  Page {
    media(search: $search, type: ANIME) {
      id
      title { romaji english native }
      description(asHtml: false)
      startDate { year }
      coverImage { extraLarge }
      bannerImage
      averageScore
      genres
      episodes
      status
    }
  }
}
"""

DETAILS_QUERY = """
query ($id: Int) {
  Media(id: $id, type: ANIME) {
    id
    title { romaji english native }
    description(asHtml: false)
    startDate { year month day }
    endDate { year month day }
    coverImage { extraLarge large }
    bannerImage
    averageScore
    genres
    episodes
    duration
    status
    season
    studios { nodes { name isAnimationStudio } }
    trailer { id site }
  }
}
"""


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


async def _graphql(query: str, variables: dict) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            settings.ANILIST_BASE_URL,
            json={"query": query, "variables": variables},
        )
        resp.raise_for_status()
        return resp.json()


async def search(query: str, db: AsyncSession) -> list[dict]:
    cache_key = f"anilist:search:{query}"
    cached = await _get_cache(db, cache_key, CACHE_SEARCH_TTL)
    if cached is not None:
        return cached

    data = await _graphql(SEARCH_QUERY, {"search": query})
    results = data.get("data", {}).get("Page", {}).get("media", [])
    await _set_cache(db, cache_key, results)
    return results


async def get_details(anilist_id: int, db: AsyncSession) -> dict:
    cache_key = f"anilist:details:{anilist_id}"
    cached = await _get_cache(db, cache_key, CACHE_DETAILS_TTL)
    if cached is not None:
        return cached

    data = await _graphql(DETAILS_QUERY, {"id": anilist_id})
    result = data.get("data", {}).get("Media", {})
    await _set_cache(db, cache_key, result)
    return result


# ── Animés de la saison en cours (hiver, printemps, été, automne) ──────────

SEASON_QUERY = """
query ($season: MediaSeason, $year: Int, $sort: [MediaSort]) {
  Page(perPage: 50) {
    media(season: $season, seasonYear: $year, type: ANIME, sort: $sort, isAdult: false) {
      id
      title { romaji english native }
      synonyms
    }
  }
}
"""

_SEASON_TTL = 6 * 3600
_season_cache: dict[tuple, tuple[float, list[dict]]] = {}


def current_season(now: datetime | None = None) -> tuple[str, int]:
    """('FALL', 2026) pour le 4 octobre 2026."""
    now = now or datetime.now(timezone.utc)
    m = now.month
    season = "WINTER" if m <= 3 else "SPRING" if m <= 6 else "SUMMER" if m <= 9 else "FALL"
    return season, now.year


async def seasonal(sort: str = "TRENDING_DESC") -> list[dict]:
    """Animés de la saison en cours, du plus tendance (ou populaire) au moins.

    Mis en cache 6 h. Si AniList est injoignable, renvoie la dernière liste connue (même
    périmée) ; lève une exception seulement s'il n'y en a aucune.
    """
    season, year = current_season()
    key = (season, year, sort)
    hit = _season_cache.get(key)
    if hit and time.time() - hit[0] < _SEASON_TTL:
        return hit[1]
    try:
        data = await _graphql(SEASON_QUERY, {"season": season, "year": year, "sort": [sort]})
        media = data.get("data", {}).get("Page", {}).get("media", []) or []
    except Exception:
        if hit:
            logger.warning("AniList saison injoignable, liste en cache utilisée")
            return hit[1]
        raise
    _season_cache[key] = (time.time(), media)
    return media
