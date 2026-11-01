"""Pubs manuelles (créées avec /pub dans le bot) : choix, image, comptage des vues et des clics."""

from __future__ import annotations

import logging
import os
import random
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models_ads import AD_SLOTS, AdCampaign

logger = logging.getLogger(__name__)
router = APIRouter()

CONTACT = {
    "telegram": "https://t.me/zgatez",
    "telegram_name": "@zgatez",
    "email": "antiflix9@gmail.com",
}


def _public_base(request: Request) -> str:
    base = (os.getenv("PUBLIC_BASE_URL") or str(request.base_url)).rstrip("/")
    if base.startswith("http://") and "localhost" not in base and "127.0.0.1" not in base:
        base = "https://" + base[len("http://"):]
    return base


def live_filter(now: datetime):
    return (AdCampaign.active.is_(True), AdCampaign.starts_at <= now, AdCampaign.ends_at > now)


def serves_slot(ad: AdCampaign, slot: str) -> bool:
    places = ad.placements or []
    return "all" in places or slot in places


@router.get("")
async def pick_ad(request: Request, slot: str = Query(..., min_length=1, max_length=20), db: AsyncSession = Depends(get_db)):
    """La pub à afficher dans un emplacement (tirée au hasard s'il y en a plusieurs), ou null."""
    if slot not in AD_SLOTS:
        raise HTTPException(status_code=422, detail="Emplacement inconnu")
    now = datetime.now(timezone.utc)
    rows = (
        await db.execute(
            select(AdCampaign.id, AdCampaign.placements, AdCampaign.text, AdCampaign.button_text,
                   AdCampaign.mime, AdCampaign.ends_at).where(*live_filter(now))
        )
    ).all()
    candidates = [r for r in rows if "all" in (r.placements or []) or slot in (r.placements or [])]
    out: dict = {"ad": None, "contact": CONTACT}
    if candidates:
        r = random.choice(candidates)
        base = _public_base(request)
        out["ad"] = {
            "id": r.id,
            "media_url": f"{base}/api/ads/{r.id}/media",
            "mime": r.mime,
            "text": r.text,
            "button_text": r.button_text,
            "link": f"{base}/api/ads/{r.id}/go?to=main",
            "button_link": f"{base}/api/ads/{r.id}/go?to=button" if r.button_text else None,
        }
    return out


@router.get("/contact")
async def contact():
    return CONTACT


@router.get("/{ad_id}/media")
async def ad_media(ad_id: int, db: AsyncSession = Depends(get_db)):
    row = (await db.execute(select(AdCampaign.media, AdCampaign.mime).where(AdCampaign.id == ad_id))).first()
    if not row:
        raise HTTPException(status_code=404, detail="Pub introuvable")
    return Response(content=row.media, media_type=row.mime, headers={"Cache-Control": "public, max-age=3600"})


class ViewIn(BaseModel):
    slot: Optional[str] = None


@router.post("/{ad_id}/view")
async def ad_view(ad_id: int, _: ViewIn, db: AsyncSession = Depends(get_db)):
    await db.execute(update(AdCampaign).where(AdCampaign.id == ad_id).values(views=AdCampaign.views + 1))
    await db.commit()
    return {"ok": True}


@router.get("/{ad_id}/go")
async def ad_click(ad_id: int, to: str = Query("main"), db: AsyncSession = Depends(get_db)):
    """Compte le clic puis redirige vers le lien de la pub (ou celui du bouton)."""
    ad = (await db.execute(select(AdCampaign).where(AdCampaign.id == ad_id))).scalar_one_or_none()
    if not ad:
        raise HTTPException(status_code=404, detail="Pub introuvable")
    url = (ad.button_url or ad.link_url) if to == "button" else ad.link_url
    if not url.lower().startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Lien invalide")
    ad.clicks = (ad.clicks or 0) + 1
    await db.commit()
    return RedirectResponse(url, status_code=302, headers={"Cache-Control": "no-store"})
