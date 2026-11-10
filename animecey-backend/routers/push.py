from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user_optional
from database import get_db
from models import PushSubscription, User
from models_ads import FcmToken
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


class FcmRegisterRequest(BaseModel):
    token: str = Field(min_length=20, max_length=512)
    platform: str = Field(default="android", max_length=16)


@router.post("/fcm")
async def register_fcm(body: FcmRegisterRequest, db: AsyncSession = Depends(get_db)):
    """Appelée par l'application Android (POST {API}/push/fcm) avec son jeton Firebase."""
    row = (await db.execute(select(FcmToken).where(FcmToken.token == body.token))).scalar_one_or_none()
    if row:
        row.last_seen = datetime.now(timezone.utc)
    else:
        db.add(FcmToken(token=body.token, platform=body.platform))
    await db.commit()
    return {"ok": True}
