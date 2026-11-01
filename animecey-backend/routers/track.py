"""Statistiques anonymes : appareils (site / application) et épisodes ouverts. Lues avec /stats dans le bot."""

from __future__ import annotations

import re
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_client_ip
from database import get_db
from models import Episode
from models_ads import Device, ViewEvent

router = APIRouter()

_ID = re.compile(r"^[A-Za-z0-9_-]{8,40}$")
_hits: dict[str, deque] = defaultdict(deque)


def _limited(key: str, per_min: int = 30) -> bool:
    now = time.time()
    q = _hits[key]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= per_min:
        return True
    q.append(now)
    if len(_hits) > 5000:
        for k in [k for k, v in _hits.items() if not v]:
            _hits.pop(k, None)
    return False


class PingIn(BaseModel):
    device_id: str = Field(..., min_length=8, max_length=40)
    platform: Literal["web", "app"] = "web"


@router.post("/ping")
async def ping(body: PingIn, request: Request, db: AsyncSession = Depends(get_db)):
    if not _ID.match(body.device_id) or _limited(get_client_ip(request)):
        return {"ok": False}
    now = datetime.now(timezone.utc)
    dev = (await db.execute(select(Device).where(Device.device_id == body.device_id))).scalar_one_or_none()
    if dev:
        dev.last_seen = now
        if body.platform == "app":
            dev.platform = "app"
    else:
        db.add(Device(device_id=body.device_id, platform=body.platform, first_seen=now, last_seen=now))
    await db.commit()
    return {"ok": True}


class ViewIn(BaseModel):
    device_id: Optional[str] = Field(None, max_length=40)
    episode_id: int = Field(..., ge=1)
    platform: Literal["web", "app"] = "web"


@router.post("/view")
async def view(body: ViewIn, request: Request, db: AsyncSession = Depends(get_db)):
    if _limited("v:" + get_client_ip(request), 60):
        return {"ok": False}
    device = body.device_id if body.device_id and _ID.match(body.device_id) else None
    ep = (await db.execute(select(Episode.anime_id).where(Episode.id == body.episode_id))).first()
    if not ep:
        return {"ok": False}
    if device:
        since = datetime.now(timezone.utc) - timedelta(hours=6)
        seen = (
            await db.execute(
                select(ViewEvent.id)
                .where(ViewEvent.device_id == device, ViewEvent.episode_id == body.episode_id, ViewEvent.created_at >= since)
                .limit(1)
            )
        ).first()
        if seen:
            return {"ok": True}
    db.add(ViewEvent(episode_id=body.episode_id, anime_id=ep.anime_id, device_id=device, platform=body.platform))
    await db.commit()
    return {"ok": True}
