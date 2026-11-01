"""Notifications de l'application Android (créées avec /notification dans le bot).

L'application les récupère toutes les ~15 minutes (service natif) : GET /api/app-notifications?after=<dernier id>.
Sans `after`, seul l'identifiant de la dernière notification est renvoyé : une nouvelle installation ne reçoit pas l'ancien historique.
"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models_ads import AppNotification

router = APIRouter()


def _base(request: Request) -> str:
    base = (os.getenv("PUBLIC_BASE_URL") or str(request.base_url)).rstrip("/")
    if base.startswith("http://") and "localhost" not in base and "127.0.0.1" not in base:
        base = "https://" + base[len("http://"):]
    return base


@router.get("")
async def list_new(request: Request, after: Optional[int] = Query(None, ge=0), db: AsyncSession = Depends(get_db)):
    if after is None:
        last = (await db.execute(select(func.max(AppNotification.id)))).scalar() or 0
        return {"latest_id": last, "items": []}
    rows = (
        await db.execute(
            select(AppNotification.id, AppNotification.title, AppNotification.body, AppNotification.path,
                   AppNotification.image_mime, AppNotification.created_at)
            .where(AppNotification.id > after)
            .order_by(AppNotification.id.asc())
            .limit(10)
        )
    ).all()
    base = _base(request)
    return {
        "latest_id": rows[-1].id if rows else after,
        "items": [
            {
                "id": r.id,
                "title": r.title,
                "body": r.body,
                "path": r.path,
                "image_url": f"{base}/api/app-notifications/{r.id}/image" if r.image_mime else None,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
    }


@router.get("/{nid}/image")
async def image(nid: int, db: AsyncSession = Depends(get_db)):
    row = (await db.execute(select(AppNotification.image, AppNotification.image_mime).where(AppNotification.id == nid))).first()
    if not row or not row.image:
        raise HTTPException(status_code=404, detail="Image introuvable")
    return Response(content=row.image, media_type=row.image_mime or "image/jpeg", headers={"Cache-Control": "public, max-age=86400"})
