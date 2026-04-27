from __future__ import annotations

import math

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from auth import get_client_ip, get_current_user, get_current_user_optional
from database import get_db
from models import Comment, CommentLike, Episode, User
from schemas import CommentCreate, CommentPublic, LikeResponse, UserBrief

router = APIRouter()


def _comment_to_dict(c: Comment, liked_ids: set[int]) -> dict:
    return {
        "id": c.id,
        "user": UserBrief.model_validate(c.user).model_dump(),
        "content": "[Commentaire supprimé]" if c.is_deleted else c.content,
        "likes_count": c.likes_count,
        "is_liked_by_me": c.id in liked_ids,
        "parent_id": c.parent_id,
        "replies": [
            _comment_to_dict(r, liked_ids)
            for r in sorted(c.replies, key=lambda x: x.created_at)
        ],
        "created_at": c.created_at.isoformat(),
    }


@router.get("")
async def list_comments(
    episode_id: int = Query(...),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    base = select(Comment).where(
        Comment.episode_id == episode_id, Comment.parent_id.is_(None)
    )
    total_q = await db.execute(select(func.count()).select_from(base.subquery()))
    total = total_q.scalar() or 0
    pages = max(1, math.ceil(total / limit))

    result = await db.execute(
        base.options(selectinload(Comment.user), selectinload(Comment.replies).selectinload(Comment.user))
        .order_by(Comment.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    comments = result.scalars().all()

    liked_ids: set[int] = set()
    if user:
        all_ids = []
        for c in comments:
            all_ids.append(c.id)
            all_ids.extend(r.id for r in c.replies)
        if all_ids:
            likes_q = await db.execute(
                select(CommentLike.comment_id).where(
                    CommentLike.comment_id.in_(all_ids),
                    CommentLike.user_id == user.id,
                )
            )
            liked_ids = {row[0] for row in likes_q.all()}

    items = [_comment_to_dict(c, liked_ids) for c in comments]
    return {"items": items, "total": total, "page": page, "pages": pages}


@router.post("", status_code=201)
async def create_comment(
    body: CommentCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ep = await db.execute(select(Episode).where(Episode.id == body.episode_id))
    if not ep.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Épisode introuvable")

    if body.parent_id:
        parent = await db.execute(select(Comment).where(Comment.id == body.parent_id))
        parent_comment = parent.scalar_one_or_none()
        if not parent_comment:
            raise HTTPException(status_code=404, detail="Commentaire parent introuvable")
        if parent_comment.parent_id is not None:
            raise HTTPException(status_code=400, detail="Réponse imbriquée non autorisée (1 niveau max)")

    comment = Comment(
        episode_id=body.episode_id,
        user_id=user.id,
        content=body.content,
        parent_id=body.parent_id,
    )
    db.add(comment)

    ep_result = await db.execute(select(Episode).where(Episode.id == body.episode_id))
    episode = ep_result.scalar_one()
    episode.comments_count += 1

    await db.commit()
    await db.refresh(comment)
    return {"id": comment.id, "content": comment.content, "created_at": comment.created_at.isoformat()}


@router.post("/{comment_id}/like", response_model=LikeResponse)
async def like_comment(
    comment_id: int,
    request: Request,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Comment).where(Comment.id == comment_id))
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="Commentaire introuvable")

    if user:
        existing = await db.execute(
            select(CommentLike).where(CommentLike.comment_id == comment_id, CommentLike.user_id == user.id)
        )
    else:
        ip = get_client_ip(request)
        existing = await db.execute(
            select(CommentLike).where(
                CommentLike.comment_id == comment_id,
                CommentLike.ip_address == ip,
                CommentLike.user_id.is_(None),
            )
        )

    if existing.scalar_one_or_none():
        return LikeResponse(liked=True, likes_count=comment.likes_count)

    like = CommentLike(
        comment_id=comment_id,
        user_id=user.id if user else None,
        ip_address=get_client_ip(request) if not user else None,
    )
    db.add(like)
    comment.likes_count += 1
    await db.commit()
    return LikeResponse(liked=True, likes_count=comment.likes_count)


@router.delete("/{comment_id}/like", response_model=LikeResponse)
async def unlike_comment(
    comment_id: int,
    request: Request,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Comment).where(Comment.id == comment_id))
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="Commentaire introuvable")

    if user:
        q = select(CommentLike).where(CommentLike.comment_id == comment_id, CommentLike.user_id == user.id)
    else:
        ip = get_client_ip(request)
        q = select(CommentLike).where(
            CommentLike.comment_id == comment_id,
            CommentLike.ip_address == ip,
            CommentLike.user_id.is_(None),
        )

    existing = await db.execute(q)
    like = existing.scalar_one_or_none()
    if not like:
        return LikeResponse(liked=False, likes_count=comment.likes_count)

    await db.delete(like)
    comment.likes_count = max(0, comment.likes_count - 1)
    await db.commit()
    return LikeResponse(liked=False, likes_count=comment.likes_count)
