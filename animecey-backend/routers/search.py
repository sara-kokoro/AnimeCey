from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from routers.animes import list_animes

router = APIRouter()


@router.get("")
async def search_animes(
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=100),
    sort: str | None = None,
    type: str | None = None,
    status: str | None = None,
    genre: str | None = None,
    language: str | None = None,
    year: int | None = None,
    q: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    return await list_animes(
        page=page,
        limit=limit,
        sort=sort,
        type=type,
        status=status,
        genre=genre,
        language=language,
        year=year,
        q=q,
        db=db,
    )
