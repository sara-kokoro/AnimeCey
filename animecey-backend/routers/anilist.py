from __future__ import annotations

from fastapi import APIRouter, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_admin
from database import get_db
from models import User
from services import anilist

router = APIRouter()


@router.post("/search")
async def anilist_search(
    body: dict = Body(...),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    query = body.get("query", "")
    return await anilist.search(query, db)


@router.get("/details/{anilist_id}")
async def anilist_details(
    anilist_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await anilist.get_details(anilist_id, db)
