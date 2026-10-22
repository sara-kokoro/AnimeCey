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
      synonyms
      format
      description(asHtml: false)
      startDate { year }
      seasonYear
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
    synonyms
    format
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


# ── Personnages / staff (fiche d'un animé) ─────────────────────────────────

CREDITS_QUERY = """
query ($id: Int) {
  Media(id: $id, type: ANIME) {
    characters(sort: [ROLE, RELEVANCE, ID], perPage: 14) {
      edges {
        role
        node { id name { full native } image { large } }
        voiceActors(language: JAPANESE, sort: [RELEVANCE, ID]) { id name { full } image { large } }
      }
    }
    staff(sort: [RELEVANCE, ID], perPage: 14) {
      edges { role node { id name { full } image { large } } }
    }
  }
}
"""

RECS_QUERY = """
query ($id: Int) {
  Media(id: $id, type: ANIME) {
    recommendations(sort: RATING_DESC, perPage: 25) {
      nodes {
        rating
        mediaRecommendation {
          id
          title { romaji english native }
          coverImage { extraLarge large }
          format
          averageScore
          seasonYear
        }
      }
    }
  }
}
"""


async def get_credits(anilist_id: int, db: AsyncSession) -> dict:
    """{"characters": [{name, role, image, voice_actor, voice_actor_image}], "staff": [{name, role, image}]}."""
    cache_key = f"anilist:credits:{anilist_id}"
    cached = await _get_cache(db, cache_key, CACHE_DETAILS_TTL)
    if cached is not None:
        return cached

    data = await _graphql(CREDITS_QUERY, {"id": anilist_id})
    media = (data.get("data") or {}).get("Media") or {}
    characters = []
    for edge in (media.get("characters") or {}).get("edges") or []:
        node = edge.get("node") or {}
        name = (node.get("name") or {}).get("full")
        if not name:
            continue
        va = (edge.get("voiceActors") or [None])[0] or {}
        characters.append(
            {
                "name": name,
                "role": {"MAIN": "Principal", "SUPPORTING": "Secondaire", "BACKGROUND": "Figurant"}.get(
                    edge.get("role"), None
                ),
                "image": (node.get("image") or {}).get("large"),
                "voice_actor": (va.get("name") or {}).get("full"),
                "voice_actor_image": (va.get("image") or {}).get("large"),
            }
        )
    staff = []
    for edge in (media.get("staff") or {}).get("edges") or []:
        node = edge.get("node") or {}
        name = (node.get("name") or {}).get("full")
        if name:
            staff.append({"name": name, "role": edge.get("role"), "image": (node.get("image") or {}).get("large")})
    result = {"characters": characters, "staff": staff}
    if characters or staff:  # on ne garde pas une réponse vide (AniList peut être en panne)
        await _set_cache(db, cache_key, result)
    return result


async def get_recommendations(anilist_id: int, db: AsyncSession) -> list[dict]:
    """Animés recommandés par les utilisateurs d'AniList, du mieux noté au moins bien noté."""
    cache_key = f"anilist:recs:{anilist_id}"
    cached = await _get_cache(db, cache_key, CACHE_DETAILS_TTL)
    if cached is not None:
        return cached

    data = await _graphql(RECS_QUERY, {"id": anilist_id})
    nodes = (((data.get("data") or {}).get("Media") or {}).get("recommendations") or {}).get("nodes") or []
    result = [n["mediaRecommendation"] for n in nodes if (n.get("rating") or 0) > 0 and n.get("mediaRecommendation")]
    await _set_cache(db, cache_key, result)
    return result


# ── Calendrier des sorties (heure de la VO, en UTC) ───────────────────────

AIRING_QUERY = """
query ($from: Int, $to: Int, $page: Int) {
  Page(page: $page, perPage: 50) {
    pageInfo { hasNextPage }
    airingSchedules(airingAt_greater: $from, airingAt_lesser: $to, sort: TIME) {
      episode
      airingAt
      media {
        id
        title { romaji english native }
        synonyms
        format
        isAdult
        countryOfOrigin
      }
    }
  }
}
"""

_AIRING_FORMATS = {"TV", "TV_SHORT", "ONA", "OVA", "SPECIAL"}
_AIRING_MAX_PAGES = 8


async def airing_schedule(start: datetime, end: datetime) -> list[dict]:
    """Sorties d'épisodes entre deux dates : [{anilist_id, title, titles, episode, airing_at (UTC)}].

    Seulement les animés japonais non adultes, en série / ONA / OAV (pas les films, qui n'ont pas
    d'« épisode » à la semaine). Lève une exception si AniList est injoignable.
    """
    out: list[dict] = []
    page = 1
    while page <= _AIRING_MAX_PAGES:
        data = await _graphql(
            AIRING_QUERY, {"from": int(start.timestamp()), "to": int(end.timestamp()), "page": page}
        )
        block = (data.get("data") or {}).get("Page") or {}
        for row in block.get("airingSchedules") or []:
            media = row.get("media") or {}
            if media.get("isAdult") or media.get("countryOfOrigin") not in (None, "JP"):
                continue
            if media.get("format") not in _AIRING_FORMATS:
                continue
            t = media.get("title") or {}
            title = t.get("english") or t.get("romaji") or t.get("native")
            if not title or not row.get("episode") or not row.get("airingAt"):
                continue
            names = [n for n in (t.get("english"), t.get("romaji"), t.get("native"), *(media.get("synonyms") or [])) if n]
            out.append(
                {
                    "anilist_id": int(media["id"]),
                    "title": title,
                    "titles": names,
                    "episode": int(row["episode"]),
                    "airing_at": datetime.fromtimestamp(int(row["airingAt"]), tz=timezone.utc),
                }
            )
        if not (block.get("pageInfo") or {}).get("hasNextPage"):
            break
        page += 1
    return out
