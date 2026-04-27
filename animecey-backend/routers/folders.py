from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from auth import require_admin
from database import get_db
from models import Episode, Folder, User
from schemas import FolderCreate, FolderPublic

router = APIRouter()


def _folder_tree(folder: Folder) -> dict:
    return {
        "id": folder.id,
        "anime_id": folder.anime_id,
        "name": folder.name,
        "folder_type": folder.folder_type.value if hasattr(folder.folder_type, "value") else folder.folder_type,
        "language": folder.language.value if folder.language and hasattr(folder.language, "value") else folder.language,
        "season_number": folder.season_number,
        "parent_id": folder.parent_id,
        "children": [_folder_tree(c) for c in folder.children],
        "created_at": folder.created_at.isoformat(),
    }


@router.get("")
async def list_folders(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Folder)
        .where(Folder.parent_id.is_(None))
        .options(selectinload(Folder.children).selectinload(Folder.children).selectinload(Folder.children))
    )
    folders = result.scalars().all()
    return [_folder_tree(f) for f in folders]


@router.post("", status_code=201)
async def create_folder(
    body: FolderCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    folder = Folder(
        anime_id=body.anime_id,
        name=body.name,
        folder_type=body.folder_type,
        language=body.language,
        season_number=body.season_number,
        parent_id=body.parent_id,
    )
    db.add(folder)
    await db.commit()
    await db.refresh(folder)
    return {"id": folder.id, "name": folder.name, "folder_type": folder.folder_type.value}


@router.delete("/{folder_id}", status_code=204)
async def delete_folder(
    folder_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Folder).where(Folder.id == folder_id))
    folder = result.scalar_one_or_none()
    if not folder:
        raise HTTPException(status_code=404, detail="Dossier introuvable")

    ep_count = await db.execute(
        select(Episode).where(Episode.folder_id == folder_id).limit(1)
    )
    if ep_count.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Impossible de supprimer un dossier contenant des épisodes")

    await db.delete(folder)
    await db.commit()
