"""POST /api/reports : un visiteur (inscrit ou non) signale un problème ; les admins sont prévenus via le bot."""

from __future__ import annotations

import hashlib
import re
import time
from collections import defaultdict, deque
from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_client_ip, get_current_user_optional
from config import settings
from database import get_db
from models import Anime, Episode, User
from models_catalog import AnimeSeason
from models_reports import Report
from services import report_notify

router = APIRouter()

# Nouvelle notification (avec sonnerie) quand un même problème atteint ces nombres de signalements
_PING_COUNTS = {3, 10, 25, 50, 100}

# limite par visiteur : 5 signalements / 10 min et 15 / heure (en mémoire, repart de zéro au redémarrage)
_hits: dict[str, deque] = defaultdict(deque)


def _rate_limited(key: str) -> bool:
    now = time.time()
    q = _hits[key]
    while q and now - q[0] > 3600:
        q.popleft()
    if sum(1 for t in q if now - t < 600) >= 5 or len(q) >= 15:
        return True
    q.append(now)
    if len(_hits) > 5000:  # ménage
        for k in [k for k, v in _hits.items() if not v]:
            _hits.pop(k, None)
    return False


def _clean(value: Optional[str], limit: int) -> Optional[str]:
    if not value:
        return None
    value = re.sub(r"\s+", " ", value).strip()
    return value[:limit] or None


class ReportIn(BaseModel):
    kind: Literal[
        "not_playable", "missing_episode", "wrong_language", "subtitles",
        "wrong_content", "wrong_info", "quality", "other",
    ]
    anime_id: Optional[int] = Field(None, ge=1)
    episode_id: Optional[int] = Field(None, ge=1)
    message: Optional[str] = Field(None, max_length=1500)
    contact: Optional[str] = Field(None, max_length=200)
    page_url: Optional[str] = Field(None, max_length=500)
    website: Optional[str] = None  # champ piège : un vrai visiteur ne le remplit jamais


async def _build_label(db: AsyncSession, anime: Anime, ep: Optional[Episode]) -> str:
    if ep is None:
        return anime.title
    season = (
        await db.execute(
            select(AnimeSeason).where(AnimeSeason.anime_id == anime.id, AnimeSeason.season_number == ep.season_number)
        )
    ).scalars().first()
    season_label = season.label if season else f"Saison {ep.season_number}"
    lang = getattr(ep.language, "value", str(ep.language))
    return f"{anime.title} — {season_label} · Épisode {ep.episode_number} ({lang})"[:300]


@router.post("", status_code=201)
async def create_report(
    body: ReportIn,
    request: Request,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
):
    if body.website:  # robot : on fait semblant que tout va bien
        return {"ok": True}

    message = _clean(body.message, 1000)
    contact = _clean(body.contact, 120)
    page_url = _clean(body.page_url, 300)
    if body.kind in ("missing_episode", "other") and len(message or "") < 3:
        raise HTTPException(status_code=422, detail="Précise le problème en quelques mots.")

    ep: Optional[Episode] = None
    anime_id = body.anime_id
    if body.episode_id:
        ep = await db.get(Episode, body.episode_id)
        if ep is None:
            raise HTTPException(status_code=404, detail="Épisode introuvable.")
        anime_id = ep.anime_id
    if not anime_id:
        raise HTTPException(status_code=422, detail="Il manque l'animé ou l'épisode concerné.")
    anime = await db.get(Anime, anime_id)
    if anime is None:
        raise HTTPException(status_code=404, detail="Titre introuvable.")

    ip_hash = hashlib.sha256(f"{get_client_ip(request)}|{settings.SECRET_KEY}".encode()).hexdigest()[:20]
    if _rate_limited(ip_hash):
        raise HTTPException(status_code=429, detail="Trop de signalements d'affilée. Réessaie dans quelques minutes.")

    # Même problème déjà ouvert sur la même cible ? On regroupe au lieu de renvoyer un message de plus.
    stmt = select(Report).where(Report.kind == body.kind, Report.status == "open", Report.anime_id == anime.id)
    stmt = stmt.where(Report.episode_id == ep.id) if ep else stmt.where(Report.episode_id.is_(None))
    existing = (await db.execute(stmt.order_by(Report.id.desc()).limit(1))).scalars().first()
    if existing is not None:
        if existing.ip_hash != ip_hash:  # le même visiteur qui insiste ne compte qu'une fois
            existing.count = (existing.count or 1) + 1
            if message and not existing.message:
                existing.message = message
            await db.commit()
            background.add_task(report_notify.notify, existing.id, existing.count in _PING_COUNTS)
        return {"ok": True, "id": existing.id}

    report = Report(
        kind=body.kind,
        anime_id=anime.id,
        episode_id=ep.id if ep else None,
        label=await _build_label(db, anime, ep),
        message=message,
        contact=contact,
        page_url=page_url,
        user_id=user.id if user else None,
        ip_hash=ip_hash,
        status="open",
        count=1,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    background.add_task(report_notify.notify, report.id, True)
    return {"ok": True, "id": report.id}
