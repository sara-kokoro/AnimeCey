"""Catalogue : recherche, ouverture d'un titre, saisons et serveurs.

  GET  /api/catalog/search?q=...                  recherche dans la base (aucun appel TMCooper)
  GET  /api/catalog/latest                        dernières nouveautés ajoutées
  POST /api/catalog/{id}/open                     crée l'animé (métadonnées TMDB + AniList,
                                                  saisons/sagas de TMCooper) et renvoie son id
  POST /api/catalog/anime/{id}/ensure             prépare les épisodes d'une saison à la demande
  GET  /api/catalog/anime/{id}/seasons            noms des saisons / sagas
  GET  /api/catalog/episodes/{id}/servers         TOUS les serveurs d'un épisode

Économie de requêtes proxy : ouvrir un titre déjà ouvert ne coûte rien ; créer un
nouveau titre demande d'être connecté ; seule la 1re saison est préparée à
l'ouverture, les autres le sont au moment où quelqu'un les consulte.

Mettre ce fichier dans routers/catalog.py.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user_optional
from database import get_db
from models import Anime, AnimeStatus, AnimeType, Episode, TmcooperSource, User
from models_catalog import AnimeSeason, CatalogTitle, EpisodeServer
from services import catalog_episodes, catalog_meta, catalog_sync, tmcooper, tmcooper_sync

logger = logging.getLogger(__name__)

router = APIRouter()

OPEN_VERSIONS = [
    v.strip().lower() for v in os.getenv("CATALOG_OPEN_VERSIONS", "vostfr,vf").split(",") if v.strip()
] or ["vostfr"]

_open_lock = asyncio.Lock()
_inflight: set[int] = set()
_background: set[asyncio.Task] = set()


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _item(row: CatalogTitle) -> dict:
    return {
        "id": str(row.id),
        "title": row.title,
        "title_jp": row.title_jp,
        "type": row.type,
        "year": row.year,
        "source": row.source,
        "external_id": row.external_id,
        "poster_url": row.poster_url,
        "is_ongoing": row.is_ongoing,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


# ── Recherche ──────────────────────────────────────────────────────────


@router.get("/search")
async def search_catalog(
    q: str = Query(..., min_length=1, max_length=100),
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    pattern = f"%{_escape_like(q.strip())}%"
    cond = or_(
        CatalogTitle.title.ilike(pattern, escape="\\"),
        CatalogTitle.title_jp.ilike(pattern, escape="\\"),
    )

    total = (await db.execute(select(func.count()).select_from(CatalogTitle).where(cond))).scalar() or 0
    rows = (
        await db.execute(
            select(CatalogTitle)
            .where(cond)
            .order_by(CatalogTitle.title.asc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
    ).scalars().all()

    return {
        "items": [_item(r) for r in rows],
        "total": total,
        "page": page,
        "pages": max(1, math.ceil(total / limit)),
    }


@router.get("/latest")
async def latest_titles(
    limit: int = Query(24, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Dernières nouveautés ajoutées au catalogue."""
    rows = (
        await db.execute(select(CatalogTitle).order_by(CatalogTitle.created_at.desc()).limit(limit))
    ).scalars().all()
    return [_item(r) for r in rows]


# ── Synchronisation en arrière-plan ────────────────────────────────────


async def _run_sync(source_ids: list[int]) -> None:
    for sid in source_ids:
        try:
            async with tmcooper_sync._sync_lock:
                await catalog_episodes.sync_source(sid, force=True)
        except Exception:  # noqa: BLE001
            logger.exception("Catalogue: synchro de la source %s en échec", sid)
        finally:
            _inflight.discard(sid)


def _schedule(source_ids: list[int]) -> None:
    ids = [s for s in source_ids if s not in _inflight]
    if not ids:
        return
    _inflight.update(ids)
    task = asyncio.create_task(_run_sync(ids))
    _background.add(task)
    task.add_done_callback(_background.discard)


# ── Ouverture d'un titre ───────────────────────────────────────────────


def _season_key(name: str) -> str:
    """'Saga 1 (East Blue)' -> 'saga1(eastblue)' (forme attendue par TMCooper pour s=)."""
    return re.sub(r"\s+", "", (name or "").strip().lower())


@router.post("/{title_id}/open")
async def open_title(
    title_id: uuid.UUID,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    title = await db.get(CatalogTitle, title_id)
    if title is None:
        raise HTTPException(status_code=404, detail="Titre introuvable")

    async with _open_lock:  # évite deux animés créés pour deux clics simultanés
        anime = (
            await db.execute(select(Anime).where(func.lower(Anime.title) == title.title.lower()))
        ).scalars().first()

        if anime is not None:
            ep_count = (
                await db.execute(select(func.count()).select_from(Episode).where(Episode.anime_id == anime.id))
            ).scalar() or 0
            return {"anime_id": anime.id, "preparing": ep_count == 0}

        if user is None:
            raise HTTPException(status_code=401, detail="Connecte-toi pour ajouter ce titre au catalogue")

        source_down = False
        try:
            raw = await tmcooper.seasons(title.title)
            if not raw and await catalog_sync.ensure_local_index():
                # le fichier de recherche de TMCooper venait de disparaître (redémarrage)
                raw = await tmcooper.seasons(title.title)
        except tmcooper.TmcooperError as exc:
            # La source externe est en panne : on crée quand même l'animé (tes envois Telegram
            # n'en ont pas besoin) avec une saison par défaut.
            logger.warning("Catalogue: source indisponible pour « %s » : %s", title.title, exc)
            raw, source_down = [], True

        # Toutes les saisons / sagas, dans l'ordre d'Anime-Sama (hors scans de manga).
        seasons: list[tuple[str, str]] = []
        seen: set[str] = set()
        for item in raw:
            label = str(item.get("Saison") or "").strip() if isinstance(item, dict) else ""
            key = _season_key(label)
            if not key or key.startswith("scan") or len(key) > 50 or key in seen:
                continue
            seen.add(key)
            seasons.append((key, label[:255]))
        external = bool(seasons)  # des saisons venues de la source externe ?

        # Métadonnées : TMDB (français) + AniList, comme à la création manuelle.
        meta = await catalog_meta.find_metadata(title.title, title.poster_url, db)
        for field in ("tmdb_id", "anilist_id"):  # colonnes uniques : pas de doublon
            value = meta.get(field)
            if value and (await db.execute(select(Anime.id).where(getattr(Anime, field) == value))).first():
                meta[field] = None

        if not seasons:
            # Aucune saison connue (source en panne ou titre absent) : un emplacement par défaut.
            seasons = [("film1", "Film 1")] if meta.get("is_film") else [("saison1", "Saison 1")]
        all_film = all(k.startswith("film") for k, _ in seasons)
        anime = Anime(
            title=title.title[:255],
            title_jp=meta.get("title_jp"),
            type=AnimeType.film if (all_film or (meta.get("is_film") and len(seasons) == 1)) else AnimeType.serie,
            status=AnimeStatus(meta.get("status") or "completed"),
            synopsis=meta.get("synopsis"),
            poster_url=meta.get("poster_url"),
            banner_url=meta.get("banner_url"),
            genres=meta.get("genres") or [],
            score=meta.get("score") or 0.0,
            year=meta.get("year") or title.year,
            tmdb_id=meta.get("tmdb_id"),
            anilist_id=meta.get("anilist_id"),
            trailer_url=meta.get("trailer_url"),
        )
        db.add(anime)
        await db.flush()
        for number, (key, label) in enumerate(seasons, start=1):
            db.add(
                AnimeSeason(
                    anime_id=anime.id, season_number=number, api_season=key, label=label,
                    kind=next((k for k in ("saison", "saga", "film", "oav", "special") if key.startswith(k)), "autre"),
                )
            )
            if external:
                for version in OPEN_VERSIONS:
                    db.add(TmcooperSource(anime_id=anime.id, api_name=title.title, season=key, version=version))
        await db.commit()

        first_key = seasons[0][0]
        first_ids = (
            await db.execute(
                select(TmcooperSource.id).where(
                    TmcooperSource.anime_id == anime.id, TmcooperSource.season == first_key
                )
            )
        ).scalars().all()

    if external:
        _schedule(list(first_ids))
    return {
        "anime_id": anime.id,
        "preparing": external,
        "seasons": [label for _, label in seasons],
        "source_down": source_down,
    }


# ── Saisons et serveurs ────────────────────────────────────────────────


@router.get("/anime/{anime_id}/seasons")
async def anime_seasons(anime_id: int, db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            select(AnimeSeason).where(AnimeSeason.anime_id == anime_id).order_by(AnimeSeason.season_number)
        )
    ).scalars().all()
    return [{"number": r.season_number, "label": r.label} for r in rows]


@router.post("/anime/{anime_id}/ensure")
async def ensure_season(
    anime_id: int,
    language: str = Query(..., max_length=10),
    season: int = Query(..., ge=1),
    db: AsyncSession = Depends(get_db),
):
    """Prépare une saison à la demande (elle n'est pas récupérée avant qu'on la consulte)."""
    version = "vf" if language.upper() == "VF" else "vostfr"
    row = (
        await db.execute(
            select(AnimeSeason).where(AnimeSeason.anime_id == anime_id, AnimeSeason.season_number == season)
        )
    ).scalars().first()
    if row is None:
        return {"preparing": False}
    src = (
        await db.execute(
            select(TmcooperSource).where(
                TmcooperSource.anime_id == anime_id,
                TmcooperSource.season == row.api_season,
                TmcooperSource.version == version,
            )
        )
    ).scalars().first()
    if src is None:
        return {"preparing": False}
    if src.id in _inflight:
        return {"preparing": True}
    failed = src.last_sync_at is not None and not src.last_count and (src.last_status or "").startswith("erreur")
    if src.last_sync_at is not None and not failed:
        return {"preparing": False}
    _schedule([src.id])
    return {"preparing": True}


@router.get("/episodes/{episode_id}/servers")
async def episode_servers(episode_id: int, db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            select(EpisodeServer).where(EpisodeServer.episode_id == episode_id).order_by(EpisodeServer.position)
        )
    ).scalars().all()
    return [{"id": r.id, "label": r.label, "url": r.url, "type": r.type} for r in rows]
