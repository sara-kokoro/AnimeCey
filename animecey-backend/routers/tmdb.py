from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_admin
from database import get_db
from models import User
from services import tmdb

router = APIRouter()


@router.get("/search")
async def tmdb_search(
    q: str = Query(...),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await tmdb.search(q, db)


@router.get("/details/{tmdb_id}")
async def tmdb_details(
    tmdb_id: int,
    type: str = Query("tv"),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await tmdb.get_details(tmdb_id, type, db)
