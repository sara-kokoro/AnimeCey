from __future__ import annotations

import math

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_admin, require_anime_adder
from database import get_db
from models import (
    Anime,
    Broadcast,
    BroadcastRead,
    Comment,
    Episode,
    Folder,
    FolderType,
    User,
    UserRole,
)
from schemas import (
    AdminStatsResponse,
    AnimeCreate,
    AnimeUpdate,
    BroadcastCreate,
    BroadcastPublic,
    EpisodeAdmin,
    EpisodeCreate,
    EpisodeUpdate,
    SetFeaturedRequest,
    SetRoleRequest,
    UserPublic,
)
from services import byse, push as push_service

router = APIRouter()


# ── Stats ──────────────────────────────────────────────────────────────


@router.get("/stats")
async def stats(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    animes_count = (await db.execute(select(func.count()).select_from(Anime))).scalar() or 0
    episodes_count = (await db.execute(select(func.count()).select_from(Episode))).scalar() or 0
    users_count = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
    comments_count = (await db.execute(select(func.count()).select_from(Comment))).scalar() or 0

    recent = await db.execute(select(Episode).order_by(Episode.created_at.desc()).limit(10))
    recent_uploads = [EpisodeAdmin.model_validate(ep) for ep in recent.scalars().all()]

    return AdminStatsResponse(
        animes_count=animes_count,
        episodes_count=episodes_count,
        users_count=users_count,
        comments_count=comments_count,
        recent_uploads=recent_uploads,
    )


# ── Animes ─────────────────────────────────────────────────────────────


@router.get("/animes")
async def admin_list_animes(
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=100),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    total_q = await db.execute(select(func.count()).select_from(Anime))
    total = total_q.scalar() or 0
    pages = max(1, math.ceil(total / limit))
    result = await db.execute(
        select(Anime).order_by(Anime.created_at.desc()).offset((page - 1) * limit).limit(limit)
    )
    items = [
        {**AnimeCreate.model_validate(a, from_attributes=True).model_dump(), "id": a.id, "created_at": a.created_at.isoformat()}
        for a in result.scalars().all()
    ]
    return {"items": items, "total": total, "page": page, "pages": pages}


@router.post("/animes", status_code=201)
async def admin_create_anime(
    body: AnimeCreate,
    admin: User = Depends(require_anime_adder),
    db: AsyncSession = Depends(get_db),
):
    anime = Anime(**body.model_dump())
    db.add(anime)
    await db.commit()
    await db.refresh(anime)

    root_folder = Folder(
        anime_id=anime.id,
        name=anime.title,
        folder_type=FolderType.anime,
    )
    db.add(root_folder)
    await db.commit()

    from services import aliases

    aliases.schedule_sync(anime.id)
    return {"id": anime.id, "title": anime.title, "folder_id": root_folder.id}


@router.put("/animes/{anime_id}")
async def admin_update_anime(
    anime_id: int,
    body: AnimeUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Anime).where(Anime.id == anime_id))
    anime = result.scalar_one_or_none()
    if not anime:
        raise HTTPException(status_code=404, detail="Animé introuvable")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(anime, key, value)
    await db.commit()
    await db.refresh(anime)
    return {"id": anime.id, "title": anime.title}


@router.delete("/animes/{anime_id}", status_code=204)
async def admin_delete_anime(
    anime_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Anime).where(Anime.id == anime_id))
    anime = result.scalar_one_or_none()
    if not anime:
        raise HTTPException(status_code=404, detail="Animé introuvable")
    await db.delete(anime)
    await db.commit()


@router.put("/animes/{anime_id}/featured")
async def set_featured(
    anime_id: int,
    body: SetFeaturedRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Anime).where(Anime.id == anime_id))
    anime = result.scalar_one_or_none()
    if not anime:
        raise HTTPException(status_code=404, detail="Animé introuvable")
    anime.is_featured = body.is_featured
    await db.commit()
    return {"id": anime.id, "is_featured": anime.is_featured}


# ── Episodes ───────────────────────────────────────────────────────────


@router.get("/episodes")
async def admin_list_episodes(
    folder_id: int | None = None,
    anime_id: int | None = None,
    language: str | None = None,
    season: int | None = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(Episode)
    if folder_id:
        q = q.where(Episode.folder_id == folder_id)
    if anime_id:
        q = q.where(Episode.anime_id == anime_id)
    if language:
        q = q.where(Episode.language == language)
    if season:
        q = q.where(Episode.season_number == season)
    result = await db.execute(q.order_by(Episode.episode_number))
    return [EpisodeAdmin.model_validate(ep) for ep in result.scalars().all()]


@router.post("/episodes", status_code=201)
async def admin_create_episode(
    body: EpisodeCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    ep = Episode(**body.model_dump())
    db.add(ep)
    await db.commit()
    await db.refresh(ep)
    return EpisodeAdmin.model_validate(ep)


@router.put("/episodes/{episode_id}")
async def admin_update_episode(
    episode_id: int,
    body: EpisodeUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Episode).where(Episode.id == episode_id))
    ep = result.scalar_one_or_none()
    if not ep:
        raise HTTPException(status_code=404, detail="Épisode introuvable")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(ep, key, value)
    await db.commit()
    await db.refresh(ep)
    return EpisodeAdmin.model_validate(ep)


@router.delete("/episodes/{episode_id}", status_code=204)
async def admin_delete_episode(
    episode_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Episode).where(Episode.id == episode_id))
    ep = result.scalar_one_or_none()
    if not ep:
        raise HTTPException(status_code=404, detail="Épisode introuvable")
    if ep.servcey2_file_code:
        await byse.delete_file(ep.servcey2_file_code)
    await db.delete(ep)
    await db.commit()


@router.get("/recent-uploads")
async def recent_uploads(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Episode).order_by(Episode.created_at.desc()).limit(10))
    return [EpisodeAdmin.model_validate(ep) for ep in result.scalars().all()]


# ── Users ──────────────────────────────────────────────────────────────


@router.get("/users")
async def admin_list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=100),
    search: str | None = None,
    role: str | None = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(User)
    if search:
        q = q.where(User.username.ilike(f"%{search}%") | User.email.ilike(f"%{search}%"))
    if role:
        q = q.where(User.role == role)
    total_q = await db.execute(select(func.count()).select_from(q.subquery()))
    total = total_q.scalar() or 0
    pages = max(1, math.ceil(total / limit))
    result = await db.execute(q.order_by(User.created_at.desc()).offset((page - 1) * limit).limit(limit))
    items = [UserPublic.model_validate(u).model_dump() for u in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "pages": pages}


@router.put("/users/{user_id}/role")
async def admin_set_role(
    user_id: int,
    body: SetRoleRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    user.role = body.role
    await db.commit()
    return {"id": user.id, "role": user.role.value if hasattr(user.role, "value") else user.role}


@router.delete("/users/{user_id}", status_code=204)
async def admin_delete_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    await db.delete(user)
    await db.commit()


# ── Comments ───────────────────────────────────────────────────────────


@router.get("/comments")
async def admin_list_comments(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = None,
    anime_id: int | None = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(Comment)
    if search:
        q = q.where(Comment.content.ilike(f"%{search}%"))
    if anime_id:
        sub = select(Episode.id).where(Episode.anime_id == anime_id)
        q = q.where(Comment.episode_id.in_(sub))
    total_q = await db.execute(select(func.count()).select_from(q.subquery()))
    total = total_q.scalar() or 0
    pages = max(1, math.ceil(total / limit))
    result = await db.execute(q.order_by(Comment.created_at.desc()).offset((page - 1) * limit).limit(limit))
    items = []
    for c in result.scalars().all():
        items.append({
            "id": c.id,
            "episode_id": c.episode_id,
            "user_id": c.user_id,
            "content": c.content,
            "is_deleted": c.is_deleted,
            "likes_count": c.likes_count,
            "created_at": c.created_at.isoformat(),
        })
    return {"items": items, "total": total, "page": page, "pages": pages}


@router.delete("/comments/{comment_id}", status_code=204)
async def admin_delete_comment(
    comment_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Comment).where(Comment.id == comment_id))
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="Commentaire introuvable")
    comment.content = "[Commentaire supprimé]"
    comment.is_deleted = True
    await db.commit()


# ── Broadcasts ─────────────────────────────────────────────────────────


@router.get("/broadcasts")
async def admin_list_broadcasts(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Broadcast).order_by(Broadcast.created_at.desc()))
    return [
        BroadcastPublic.model_validate(b).model_dump()
        for b in result.scalars().all()
    ]


@router.post("/broadcasts", status_code=201)
async def admin_create_broadcast(
    body: BroadcastCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    broadcast = Broadcast(
        title=body.title,
        content=body.content,
        image_url=body.image_url,
        caption=body.caption,
        type=body.type,
        target=body.target,
        admin_id=admin.id,
    )
    db.add(broadcast)
    await db.commit()
    await db.refresh(broadcast)

    sent = await push_service.broadcast(
        db, broadcast.id, body.target, body.title, body.content
    )
    return {"id": broadcast.id, "push_sent": sent}


@router.delete("/broadcasts/{broadcast_id}", status_code=204)
async def admin_delete_broadcast(
    broadcast_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Broadcast).where(Broadcast.id == broadcast_id))
    broadcast = result.scalar_one_or_none()
    if not broadcast:
        raise HTTPException(status_code=404, detail="Annonce introuvable")
    await db.execute(delete(BroadcastRead).where(BroadcastRead.broadcast_id == broadcast_id))
    await db.delete(broadcast)
    await db.commit()
