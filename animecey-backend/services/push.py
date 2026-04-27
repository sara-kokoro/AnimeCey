"""Web Push notification service using pywebpush + VAPID."""

from __future__ import annotations

import json
import logging

from pywebpush import WebPushException, webpush
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models import PushSubscription

logger = logging.getLogger(__name__)


async def send_notification(
    subscription_info: dict,
    title: str,
    body: str,
    url: str = "/",
) -> bool:
    payload = json.dumps({"title": title, "body": body, "url": url})
    try:
        webpush(
            subscription_info=subscription_info,
            data=payload,
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": f"mailto:{settings.VAPID_CLAIMS_EMAIL}"},
        )
        return True
    except WebPushException as exc:
        if hasattr(exc, "response") and exc.response is not None:
            if exc.response.status_code == 410:
                return False
        logger.warning("Push échoué: %s", exc)
        return False


async def broadcast(
    db: AsyncSession,
    broadcast_id: int,
    target: str,
    title: str,
    body: str,
) -> int:
    query = select(PushSubscription)
    if target == "users":
        query = query.where(PushSubscription.user_id.isnot(None))
    result = await db.execute(query)
    subs = result.scalars().all()

    sent = 0
    to_remove: list[int] = []
    for sub in subs:
        sub_info = {
            "endpoint": sub.endpoint,
            "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
        }
        ok = await send_notification(sub_info, title, body, f"/notifications")
        if ok:
            sent += 1
        else:
            to_remove.append(sub.id)

    if to_remove:
        await db.execute(
            delete(PushSubscription).where(PushSubscription.id.in_(to_remove))
        )
        await db.commit()

    return sent
