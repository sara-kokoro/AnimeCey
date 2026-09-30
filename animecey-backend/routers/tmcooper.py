"""Routes admin TMCooper : recherche, sources suivies, synchronisation manuelle."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_admin
from config import settings
from database import get_db
from models import Anime, TmcooperSource, User
from services import tmcooper, tmcooper_sync

router = APIRouter()

_background: set[asyncio.Task] = set()


class SourceCreate(BaseModel):
    anime_id: int
    api_name: str = Field(..., min_length=1, max_length=255, description="Nom de l'animé tel que compris par l'API (paramètre n=)")
    season: str = Field("saison1", pattern=r"^[A-Za-z]+\d*$", description="saison1, saison2, film1, oav...")
    version: str = Field("vostfr", pattern=r"^(?i:vostfr|vf)\d*$")


class SourceUpdate(BaseModel):
    is_active: bool


def _source_dict(src: TmcooperSource, anime_title: str | None = None) -> dict:
    return {
        "id": src.id,
        "anime_id": src.anime_id,
        "anime_title": anime_title,
        "api_name": src.api_name,
        "season": src.season,
        "version": src.version,
        "is_active": src.is_active,
        "last_sync_at": src.last_sync_at.isoformat() if src.last_sync_at else None,
        "last_status": src.last_status,
        "last_count": src.last_count,
    }


def _api_error(exc: tmcooper.TmcooperError) -> HTTPException:
    if isinstance(exc, tmcooper.TmcooperCatalogNotReady):
        return HTTPException(status_code=503, detail="Catalogue TMCooper en cours d'indexation, réessaie dans quelques minutes")
    return HTTPException(status_code=502, detail=f"API TMCooper: {exc}")


@router.get("/health")
async def health(admin: User = Depends(require_admin)):
    try:
        domain = await tmcooper.active_domain()
    except tmcooper.TmcooperError as exc:
        return {"reachable": False, "api_url": settings.TMCOOPER_API_URL, "error": str(exc)}
    return {"reachable": True, "api_url": settings.TMCOOPER_API_URL, "anime_sama_domain": domain}


@router.get("/search")
async def search(
    q: str = Query(..., min_length=1),
    limit: int = Query(5, ge=1, le=20),
    admin: User = Depends(require_admin),
):
    try:
        return await tmcooper.search(q, limit)
    except tmcooper.TmcooperError as exc:
        raise _api_error(exc)


@router.get("/seasons")
async def seasons(q: str = Query(..., min_length=1), admin: User = Depends(require_admin)):
    try:
        return await tmcooper.seasons(q)
    except tmcooper.TmcooperError as exc:
        raise _api_error(exc)


@router.get("/sources")
async def list_sources(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    rows = await db.execute(
        select(TmcooperSource, Anime.title)
        .join(Anime, Anime.id == TmcooperSource.anime_id)
        .order_by(Anime.title, TmcooperSource.season, TmcooperSource.version)
    )
    return [_source_dict(src, title) for src, title in rows.all()]


@router.post("/sources", status_code=201)
async def create_source(
    body: SourceCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    anime = await db.get(Anime, body.anime_id)
    if anime is None:
        raise HTTPException(status_code=404, detail="Animé introuvable")

    src = TmcooperSource(
        anime_id=body.anime_id,
        api_name=body.api_name.strip(),
        season=body.season.lower(),
        version=body.version.lower(),
    )
    db.add(src)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Cette source (animé + saison + version) existe déjà")
    await db.refresh(src)
    return _source_dict(src, anime.title)


@router.patch("/sources/{source_id}")
async def update_source(
    source_id: int,
    body: SourceUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    src = await db.get(TmcooperSource, source_id)
    if src is None:
        raise HTTPException(status_code=404, detail="Source introuvable")
    src.is_active = body.is_active
    await db.commit()
    await db.refresh(src)
    return _source_dict(src)


@router.delete("/sources/{source_id}", status_code=204)
async def delete_source(
    source_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Retire la source de la synchro. Les épisodes déjà créés sont conservés."""
    src = await db.get(TmcooperSource, source_id)
    if src is None:
        raise HTTPException(status_code=404, detail="Source introuvable")
    await db.delete(src)
    await db.commit()


@router.post("/sources/{source_id}/sync")
async def sync_source_now(source_id: int, admin: User = Depends(require_admin)):
    """Synchronise une source tout de suite et renvoie le détail."""
    return await tmcooper_sync.sync_one(source_id)


@router.post("/sync", status_code=202)
async def sync_all_now(admin: User = Depends(require_admin)):
    """Lance un cycle complet en arrière-plan."""
    task = asyncio.create_task(tmcooper_sync.sync_all())
    _background.add(task)
    task.add_done_callback(_background.discard)
    return {"status": "started"}
