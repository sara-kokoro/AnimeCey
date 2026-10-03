"""Recherche dans le catalogue importé + ouverture d'un titre.

  GET  /api/catalog/search?q=...        recherche dans la base (aucun appel à TMCooper)
  GET  /api/catalog/latest              dernières nouveautés ajoutées
  POST /api/catalog/{id}/open           crée l'animé (si besoin), détecte ses saisons,
                                        lance la récupération des épisodes en arrière-plan
                                        et renvoie l'id de l'animé pour la page de lecture

Économie de requêtes proxy : ouvrir un titre déjà ouvert ne coûte rien. Créer un
nouveau titre demande d'être connecté, et seule la version VOSTFR est récupérée
par défaut (variable CATALOG_OPEN_VERSIONS="vostfr,vf" pour ajouter la VF).

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
from models_catalog import CatalogTitle
from services import catalog_sync, tmcooper, tmcooper_sync

logger = logging.getLogger(__name__)

router = APIRouter()

OPEN_VERSIONS = [
    v.strip().lower() for v in os.getenv("CATALOG_OPEN_VERSIONS", "vostfr").split(",") if v.strip()
] or ["vostfr"]
_SEASON_RE = re.compile(r"^[a-z]+\d*$")

_open_lock = asyncio.Lock()
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


# ── Ouverture d'un titre ───────────────────────────────────────────────


def _season_key(name: str) -> str:
    """'Saison 2' -> 'saison2' (forme attendue par TMCooper pour le paramètre s=)."""
    return re.sub(r"\s+", "", (name or "").strip().lower())


async def _sync_in_background(source_ids: list[int]) -> None:
    for source_id in source_ids:
        try:
            await tmcooper_sync.sync_one(source_id)
        except Exception:  # noqa: BLE001
            logger.exception("Catalogue: synchro de la source %s en échec", source_id)


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

        try:
            raw = await tmcooper.seasons(title.title)
            if not raw and await catalog_sync.ensure_local_index():
                # le fichier de recherche de TMCooper venait de disparaître (redémarrage)
                raw = await tmcooper.seasons(title.title)
        except tmcooper.TmcooperError as exc:
            raise HTTPException(status_code=502, detail=f"Source indisponible: {exc}")

        seasons: list[str] = []
        for item in raw:
            key = _season_key(item.get("Saison", "")) if isinstance(item, dict) else ""
            if key and _SEASON_RE.match(key) and key not in seasons:
                seasons.append(key)
        if not seasons:
            raise HTTPException(status_code=404, detail="Aucune saison trouvée pour ce titre")

        poster = title.poster_url if title.poster_url and len(title.poster_url) <= 500 else None
        anime = Anime(
            title=title.title[:255],
            title_jp=title.title_jp[:255] if title.title_jp else None,
            type=AnimeType.film if all(s.startswith("film") for s in seasons) else AnimeType.serie,
            status=AnimeStatus.completed,
            synopsis=None,
            poster_url=poster,
            genres=[],
            score=0.0,
            year=title.year,
        )
        db.add(anime)
        await db.flush()
        for season in seasons:
            for version in OPEN_VERSIONS:
                db.add(TmcooperSource(anime_id=anime.id, api_name=title.title, season=season, version=version))
        await db.commit()

        source_ids = (
            await db.execute(
                select(TmcooperSource.id).where(TmcooperSource.anime_id == anime.id).order_by(TmcooperSource.id)
            )
        ).scalars().all()

    task = asyncio.create_task(_sync_in_background(list(source_ids)))
    _background.add(task)
    task.add_done_callback(_background.discard)
    return {"anime_id": anime.id, "preparing": True, "seasons": seasons}
