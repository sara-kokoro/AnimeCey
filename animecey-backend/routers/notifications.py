from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user, get_current_user_optional
from database import get_db
from models import Broadcast, BroadcastRead, User
from schemas import UnreadCountResponse

router = APIRouter()


@router.get("")
async def list_notifications(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    base = select(Broadcast).order_by(Broadcast.created_at.desc())
    total_q = await db.execute(select(func.count()).select_from(Broadcast))
    total = total_q.scalar() or 0
    pages = max(1, math.ceil(total / limit))

    result = await db.execute(base.offset((page - 1) * limit).limit(limit))
    broadcasts = result.scalars().all()

    read_ids: set[int] = set()
    if user:
        reads_q = await db.execute(
            select(BroadcastRead.broadcast_id).where(BroadcastRead.user_id == user.id)
        )
        read_ids = {row[0] for row in reads_q.all()}

    items = []
    for b in broadcasts:
        items.append({
            "id": b.id,
            "title": b.title,
            "content": b.content,
            "image_url": b.image_url,
            "caption": b.caption,
            "type": b.type.value if hasattr(b.type, "value") else b.type,
            "is_read": b.id in read_ids,
            "created_at": b.created_at.isoformat(),
        })

    return {"items": items, "total": total, "page": page, "pages": pages}


@router.get("/unread-count", response_model=UnreadCountResponse)
async def unread_count(
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    if user:
        read_q = await db.execute(
            select(func.count()).select_from(
                select(BroadcastRead).where(BroadcastRead.user_id == user.id).subquery()
            )
        )
        read_count = read_q.scalar() or 0
        total_q = await db.execute(select(func.count()).select_from(Broadcast))
        total = total_q.scalar() or 0
        return UnreadCountResponse(count=max(0, total - read_count))
    else:
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        q = await db.execute(
            select(func.count()).select_from(
                select(Broadcast).where(Broadcast.created_at >= week_ago).subquery()
            )
        )
        return UnreadCountResponse(count=q.scalar() or 0)


@router.post("/{notification_id}/read")
async def mark_read(
    notification_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    broadcast = await db.execute(select(Broadcast).where(Broadcast.id == notification_id))
    b = broadcast.scalar_one_or_none()
    if not b:
        raise HTTPException(status_code=404, detail="Notification introuvable")

    existing = await db.execute(
        select(BroadcastRead).where(
            BroadcastRead.broadcast_id == notification_id,
            BroadcastRead.user_id == user.id,
        )
    )
    if not existing.scalar_one_or_none():
        db.add(BroadcastRead(broadcast_id=notification_id, user_id=user.id))
        b.reads_count += 1
        await db.commit()
    return {"detail": "Marqué comme lu"}


@router.post("/read-all")
async def mark_all_read(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    all_broadcasts = await db.execute(select(Broadcast.id))
    all_ids = {row[0] for row in all_broadcasts.all()}

    already_read = await db.execute(
        select(BroadcastRead.broadcast_id).where(BroadcastRead.user_id == user.id)
    )
    read_ids = {row[0] for row in already_read.all()}

    unread = all_ids - read_ids
    for bid in unread:
        db.add(BroadcastRead(broadcast_id=bid, user_id=user.id))
        broadcast = await db.execute(select(Broadcast).where(Broadcast.id == bid))
        b = broadcast.scalar_one_or_none()
        if b:
            b.reads_count += 1

    await db.commit()
    return {"detail": f"{len(unread)} notifications marquées comme lues"}
