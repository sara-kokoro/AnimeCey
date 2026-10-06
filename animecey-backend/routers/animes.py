from __future__ import annotations

import logging
import random
import math
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import String, case, cast, distinct, func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from services import search_fuzzy
from models import Anime, Episode, LanguageEnum, WatchHistory
from schemas import AnimePublic
from services import anilist
from services.caption_parser import norm

logger = logging.getLogger(__name__)

TOP_LIMIT = 10  # chaque rangée de l'accueil : 10 animés au maximum

# Genre affiché sur le site -> morceaux de texte à chercher dans les genres enregistrés
# (TMDB en français : « Action & Adventure », AniList en anglais : « Adventure »...).
GENRE_FRAGMENTS: dict[str, list[str]] = {
    "action": ["action"],
    "aventure": ["aventure", "adventure"],
    "comédie": ["comédie", "comedie", "comedy"],
    "drame": ["drame", "drama"],
    "fantasy": ["fantasy", "fantastique"],
    "horreur": ["horreur", "horror"],
    "mystère": ["mystère", "mystere", "mystery"],
    "romance": ["romance", "romantique"],
    "sci-fi": ["sci-fi", "science-fiction", "science fiction"],
    "shonen": ["shonen", "shōnen"],
    "seinen": ["seinen"],
    "slice of life": ["slice of life", "tranche de vie"],
    "sports": ["sport"],
    "surnaturel": ["surnaturel", "supernatural"],
    "thriller": ["thriller", "suspense"],
    "mecha": ["mecha"],
    "isekai": ["isekai"],
    "musique": ["musique", "music"],
    "psychologique": ["psychologique", "psychological"],
    "ecchi": ["ecchi"],
}

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
        select(Episode.anime_id, func.array_agg(distinct(cast(Episode.language, String))))
        .where(Episode.anime_id.in_(ids))
        .group_by(Episode.anime_id)
    )
    lang_map: dict[int, list[str]] = {}
    for row in lang_q.all():
        raw = row[1]
        if isinstance(raw, list):
            lang_map[row[0]] = [str(v) for v in raw if v]
        elif isinstance(raw, str):
            lang_map[row[0]] = [l.strip() for l in raw.split(",") if l.strip()]
        else:
            lang_map[row[0]] = []

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
    category: Optional[str] = None,  # « anime » ou « live » (films et séries live-action)
    db: AsyncSession = Depends(get_db),
):
    query = select(Anime)
    if category in ("anime", "live"):
        query = query.where(Anime.category == category)

    ranked: list[int] | None = None
    if q:
        # Recherche floue : accents, fautes de frappe, autres noms (« Shingeki no Kyojin »...)
        ranked = await search_fuzzy.ranked_anime_ids(db, q)
        query = query.where(Anime.id.in_(ranked or [-1]))
    if type:
        query = query.where(Anime.type == type)
    if status:
        query = query.where(Anime.status == status)
    if genre:
        fragments = GENRE_FRAGMENTS.get(genre.lower(), [genre.lower()])
        genres_text = cast(Anime.genres, String)
        query = query.where(or_(*[genres_text.ilike(f"%{f}%") for f in fragments]))
    if year:
        query = query.where(Anime.year == year)

    if language and language in ("VF", "VOSTFR"):
        sub = select(distinct(Episode.anime_id)).where(Episode.language == language)
        query = query.where(Anime.id.in_(sub))
    elif language == "BOTH":
        sub_vf = select(distinct(Episode.anime_id)).where(Episode.language == LanguageEnum.VF)
        sub_vo = select(distinct(Episode.anime_id)).where(Episode.language == LanguageEnum.VOSTFR)
        query = query.where(Anime.id.in_(sub_vf)).where(Anime.id.in_(sub_vo))

    if ranked is not None and not sort:
        # Classés par pertinence, paginés en mémoire (peu de résultats)
        rows = {a.id: a for a in (await db.execute(query)).scalars().all()}
        ordered = [rows[i] for i in ranked if i in rows]
        total = len(ordered)
        pages = max(1, math.ceil(total / limit))
        items = await _enrich_animes(db, ordered[(page - 1) * limit : page * limit])
        return {"items": items, "total": total, "page": page, "pages": pages}

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
    """Grand bandeau de l'accueil : 6 animés qui changent chaque jour (24 h).

    Le choix est mélangé avec une graine = la date du jour (UTC) : tout le monde voit la même
    sélection pendant la journée, et elle change à minuit. Les animés « en vedette » choisis dans
    l'admin passent en premier ; sinon on pioche parmi les animés du site (les tendances de la
    saison sont ajoutées en priorité).
    """
    rng = random.Random(datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    flagged = (
        await db.execute(select(Anime).where(Anime.is_featured == True, Anime.category == "anime"))  # noqa: E712
    ).scalars().all()
    pool = list(flagged)
    if len(pool) < 6:
        taken = {a.id for a in pool}
        seasonal = await _seasonal_animes(db, "TRENDING_DESC") or []
        extra = [a for a in seasonal if a.id not in taken and (a.banner_url or a.poster_url)]
        taken |= {a.id for a in extra}
        others = (
            await db.execute(
                select(Anime)
                .where(Anime.id.in_(select(distinct(Episode.anime_id))), Anime.id.notin_(list(taken) or [0]))
                .where(Anime.category == "anime")
                .where((Anime.banner_url.isnot(None)) | (Anime.poster_url.isnot(None)))
                .limit(60)
            )
        ).scalars().all()
        rest = extra + list(others)
        rest.sort(key=lambda a: a.id)       # ordre stable avant le mélange du jour
        rng.shuffle(rest)
        pool.extend(rest)
    else:
        rng.shuffle(pool)
    return await _enrich_animes(db, pool[:6])


async def _top_week_by_views(db: AsyncSession):
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    sub = (
        select(Episode.anime_id, func.count().label("cnt"))
        .join(WatchHistory, WatchHistory.episode_id == Episode.id)
        .where(WatchHistory.watched_at >= week_ago)
        .group_by(Episode.anime_id)
        .order_by(func.count().desc())
        .limit(TOP_LIMIT)
        .subquery()
    )
    result = await db.execute(select(Anime).join(sub, Anime.id == sub.c.anime_id))
    animes = list(result.scalars().all())
    return await _enrich_animes(db, animes)


@router.get("/top-rated")
async def top_rated(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Anime).where(Anime.category == "anime").order_by(Anime.score.desc()).limit(TOP_LIMIT)
    )
    return await _enrich_animes(db, list(result.scalars().all()))


@router.get("/latest")
async def latest(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Anime).where(Anime.category == "anime").order_by(Anime.created_at.desc()).limit(TOP_LIMIT)
    )
    return await _enrich_animes(db, list(result.scalars().all()))


async def _trending_by_views(db: AsyncSession):
    month_ago = datetime.now(timezone.utc) - timedelta(days=30)
    sub = (
        select(Episode.anime_id, func.count().label("cnt"))
        .join(WatchHistory, WatchHistory.episode_id == Episode.id)
        .where(WatchHistory.watched_at >= month_ago)
        .group_by(Episode.anime_id)
        .order_by(func.count().desc())
        .limit(TOP_LIMIT)
        .subquery()
    )
    result = await db.execute(
        select(Anime).join(sub, Anime.id == sub.c.anime_id).where(Anime.category == "anime")
    )
    animes = list(result.scalars().all())
    return await _enrich_animes(db, animes)


async def _seasonal_animes(db: AsyncSession, sort: str) -> list[Anime] | None:
    """Animés tendance de la saison en cours qui sont DÉJÀ sur le site (avec au moins un épisode),
    du plus tendance au moins tendance. None si AniList est injoignable.

    Ceux qui ne sont pas encore sur AnimeCey n'apparaissent pas : ils s'afficheront dès leur ajout.
    """
    try:
        media = await anilist.seasonal(sort)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Tendances de saison indisponibles: %s", exc)
        return None

    by_id: dict[int, int] = {}      # id AniList -> rang
    by_title: dict[str, int] = {}   # titre normalisé -> rang
    for rank, m in enumerate(media):
        by_id.setdefault(m["id"], rank)
        t = m.get("title") or {}
        for name in [t.get("romaji"), t.get("english"), t.get("native"), *(m.get("synonyms") or [])]:
            key = norm(name)
            if key:
                by_title.setdefault(key, rank)

    on_site = (
        await db.execute(
            select(Anime).where(Anime.id.in_(select(distinct(Episode.anime_id))), Anime.category == "anime")
        )
    ).scalars().all()

    ranked: list[tuple[int, Anime]] = []
    for a in on_site:
        rank = by_id.get(a.anilist_id) if a.anilist_id else None
        if rank is None:
            for key in {norm(a.title), norm(a.title_jp)} - {""}:
                if key in by_title:
                    rank = by_title[key]
                    break
                if len(key) >= 6:  # « demonslayer » ⊂ « demonslayerkimetsunoyaiba »
                    cands = [r for k, r in by_title.items() if k.startswith(key)]
                    if cands:
                        rank = min(cands)
                        break
        if rank is not None:
            ranked.append((rank, a))
    ranked.sort(key=lambda x: x[0])
    return [a for _, a in ranked]


async def _seasonal_on_site(db: AsyncSession, sort: str) -> list[dict] | None:
    animes = await _seasonal_animes(db, sort)
    if animes is None:
        return None
    return await _enrich_animes(db, animes[:TOP_LIMIT])


async def _top_week_combined(db: AsyncSession) -> list[dict]:
    """Les plus regardés sur AnimeCey cette semaine ; complétés (jusqu'à 10) par les plus tendance
    de la saison ailleurs (AniList) qui sont déjà sur le site."""
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    rows = (
        await db.execute(
            select(Episode.anime_id, func.count().label("cnt"))
            .join(WatchHistory, WatchHistory.episode_id == Episode.id)
            .where(WatchHistory.watched_at >= week_ago)
            .group_by(Episode.anime_id)
            .order_by(func.count().desc())
            .limit(TOP_LIMIT)
        )
    ).all()
    ids = [r[0] for r in rows]
    animes: list[Anime] = []
    if ids:
        by_id = {
            a.id: a
            for a in (
                await db.execute(select(Anime).where(Anime.id.in_(ids), Anime.category == "anime"))
            ).scalars().all()
        }
        animes = [by_id[i] for i in ids if i in by_id]

    if len(animes) < TOP_LIMIT:
        seasonal = await _seasonal_animes(db, "TRENDING_DESC")
        taken = {a.id for a in animes}
        for a in seasonal or []:
            if a.id not in taken:
                animes.append(a)
                taken.add(a.id)
            if len(animes) >= TOP_LIMIT:
                break
        if seasonal is None and len(animes) < TOP_LIMIT:  # AniList en panne : on complète avec les mieux notés
            more = (
                await db.execute(
                    select(Anime)
                    .where(Anime.id.in_(select(distinct(Episode.anime_id))), Anime.id.notin_(list(taken) or [0]))
                    .where(Anime.category == "anime")
                    .order_by(Anime.score.desc())
                    .limit(TOP_LIMIT - len(animes))
                )
            ).scalars().all()
            animes.extend(more)
    return await _enrich_animes(db, animes[:TOP_LIMIT])


@router.get("/top-week")
async def top_week(db: AsyncSession = Depends(get_db)):
    """Top 10 de la semaine : d'abord les plus vus sur AnimeCey, puis les plus tendance ailleurs."""
    return await _top_week_combined(db)


@router.get("/trending")
async def trending(db: AsyncSession = Depends(get_db)):
    """Tendances = les plus populaires de la saison en cours qui sont sur le site (10 max)."""
    found = await _seasonal_on_site(db, "POPULARITY_DESC")
    return found if found is not None else (await _trending_by_views(db))[:TOP_LIMIT]


LIVE_ROW = 12  # titres par rangée « Films & Séries »


@router.get("/live-home")
async def live_home(db: AsyncSession = Depends(get_db)):
    """Tout l'accueil « Films & Séries » (live-action) en une seule requête.

    Seuls les titres qui ont au moins un épisode envoyé apparaissent (pas de fiches vides).
    """
    now = datetime.now(timezone.utc)
    with_eps = Anime.id.in_(select(distinct(Episode.anime_id)))
    live = (Anime.category == "live", with_eps)

    async def rows(*conds, order, limit: int = LIVE_ROW) -> list[dict]:
        stmt = select(Anime).where(*live, *conds).order_by(*order).limit(limit)
        return await _enrich_animes(db, list((await db.execute(stmt)).scalars().all()))

    # Grand bandeau : 6 titres qui changent chaque jour (même sélection pour tout le monde)
    pool = list(
        (
            await db.execute(
                select(Anime).where(*live, Anime.banner_url.isnot(None)).order_by(Anime.id).limit(60)
            )
        ).scalars().all()
    )
    random.Random(now.strftime("%Y-%m-%d") + "live").shuffle(pool)
    pool.sort(key=lambda a: not a.is_featured)  # les « en vedette » de l'admin d'abord
    featured = await _enrich_animes(db, pool[:6])

    # Top 10 de la semaine : les plus regardés, complétés par les mieux notés
    week_ago = now - timedelta(days=7)
    viewed = (
        await db.execute(
            select(Episode.anime_id, func.count().label("cnt"))
            .join(WatchHistory, WatchHistory.episode_id == Episode.id)
            .where(WatchHistory.watched_at >= week_ago)
            .group_by(Episode.anime_id)
            .order_by(func.count().desc())
            .limit(40)
        )
    ).all()
    view_ids = [r[0] for r in viewed]
    by_id: dict[int, Anime] = {}
    if view_ids:
        by_id = {
            a.id: a
            for a in (await db.execute(select(Anime).where(Anime.id.in_(view_ids), *live))).scalars().all()
        }
    top = [by_id[i] for i in view_ids if i in by_id][:TOP_LIMIT]
    if len(top) < TOP_LIMIT:
        more = (
            await db.execute(
                select(Anime)
                .where(*live, Anime.id.notin_([a.id for a in top] or [0]))
                .order_by(Anime.score.desc(), Anime.created_at.desc())
                .limit(TOP_LIMIT - len(top))
            )
        ).scalars().all()
        top += list(more)
    top_week = await _enrich_animes(db, top)

    # Genres les plus fournis -> une rangée par genre
    all_live = list((await db.execute(select(Anime).where(*live).limit(400))).scalars().all())
    counts: dict[str, int] = {}
    for a in all_live:
        for g in a.genres or []:
            counts[g] = counts.get(g, 0) + 1
    genres = []
    for g, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        if n < 3 or len(genres) >= 4:
            continue
        members = sorted((a for a in all_live if g in (a.genres or [])), key=lambda a: -(a.score or 0))[:LIVE_ROW]
        genres.append({"genre": g, "items": await _enrich_animes(db, members)})

    return {
        "featured": featured,
        "top_week": top_week,
        "new_releases": await rows(
            Anime.year >= now.year - 1, order=(Anime.year.desc(), Anime.created_at.desc())
        ),
        "top_rated": await rows(Anime.score > 0, order=(Anime.score.desc(),)),
        "latest": await rows(order=(Anime.created_at.desc(),)),
        "films": await rows(Anime.type == "film", order=(Anime.created_at.desc(),)),
        "series": await rows(Anime.type == "serie", order=(Anime.created_at.desc(),)),
        "genres": genres,
    }


@router.get("/{anime_id}")
async def get_anime(anime_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Anime).where(Anime.id == anime_id))
    anime = result.scalar_one_or_none()
    if not anime:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Animé introuvable")
    items = await _enrich_animes(db, [anime])
    return items[0]
