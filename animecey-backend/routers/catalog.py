"""Recherche dans le catalogue importé (base de données uniquement).

Mettre ce fichier dans routers/catalog.py.
"""

from __future__ import annotations

import math

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models_catalog import CatalogTitle

router = APIRouter()


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
