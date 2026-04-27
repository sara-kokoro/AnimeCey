from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user_optional
from database import get_db
from models import PushSubscription, User
from schemas import PushSubscribeRequest, PushUnsubscribeRequest

router = APIRouter()


@router.post("/subscribe")
async def subscribe(
    body: PushSubscribeRequest,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(PushSubscription).where(PushSubscription.endpoint == body.endpoint)
    )
    sub = existing.scalar_one_or_none()
    if sub:
        sub.p256dh = body.p256dh
        sub.auth = body.auth
        if user:
            sub.user_id = user.id
    else:
        sub = PushSubscription(
            endpoint=body.endpoint,
            p256dh=body.p256dh,
            auth=body.auth,
            user_id=user.id if user else None,
        )
        db.add(sub)
    await db.commit()
    return {"detail": "Souscription enregistrée"}


@router.delete("/unsubscribe")
async def unsubscribe(
    body: PushUnsubscribeRequest,
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        delete(PushSubscription).where(PushSubscription.endpoint == body.endpoint)
    )
    await db.commit()
    return {"detail": "Souscription supprimée"}
