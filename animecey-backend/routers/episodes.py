from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_client_ip, get_current_user, get_current_user_optional
from config import settings
from database import get_db
from models import Episode, EpisodeLike, User
from schemas import EpisodePublic, LikeResponse, StreamResponse
from services import byse

logger = logging.getLogger(__name__)

router = APIRouter()


async def _ensure_channel_msg(ep: Episode, db: AsyncSession):
    """Ensure the episode has a channel message for FileStream.

    If servcey1_msg_id is missing (legacy episode), copy the file to
    the storage channel and save the resulting message ID.
    """
    if ep.servcey1_msg_id:
        return ep.servcey1_msg_id

    if not ep.servcey1_file_id:
        return None

    try:
        from bot.client import bot

        if not bot.is_connected:
            return None

        # Send the file to channel using its file_id
        sent = await bot.send_document(
            chat_id=settings.TELEGRAM_CHANNEL_ID,
            document=ep.servcey1_file_id,
        )
        if sent:
            ep.servcey1_msg_id = sent.id
            await db.commit()
            logger.info("Lazy-forwarded ep %s to channel, msg_id=%s", ep.id, sent.id)
            return sent.id
    except Exception as exc:
        logger.warning("Failed to lazy-forward ep %s to channel: %s", ep.id, exc)

    return None


@router.get("")
async def list_episodes(
    anime_id: int = Query(...),
    language: str = Query(...),
    season: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Episode)
        .where(
            Episode.anime_id == anime_id,
            Episode.language == language,
            Episode.season_number == season,
        )
        .order_by(Episode.episode_number)
    )
    episodes = result.scalars().all()
    return [EpisodePublic.model_validate(ep) for ep in episodes]


@router.get("/{episode_id}", response_model=EpisodePublic)
async def get_episode(episode_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Episode).where(Episode.id == episode_id))
    ep = result.scalar_one_or_none()
    if not ep:
        raise HTTPException(status_code=404, detail="Épisode introuvable")
    return EpisodePublic.model_validate(ep)


@router.get("/{episode_id}/stream")
async def stream(
    episode_id: int,
    request: Request,
    server: str = Query(..., pattern="^servcey[12]$"),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Episode).where(Episode.id == episode_id))
    ep = result.scalar_one_or_none()
    if not ep:
        raise HTTPException(status_code=404, detail="Épisode introuvable")

    if server == "servcey1":
        if not ep.servcey1_available or not ep.servcey1_file_id:
            raise HTTPException(status_code=404, detail="ServCey 1 non disponible pour cet épisode")

        base = str(request.base_url).rstrip("/")
        player_url = f"{base}/api/episodes/{episode_id}/player"
        return StreamResponse(url=player_url)

    else:
        if not ep.servcey2_available or not ep.servcey2_file_code:
            raise HTTPException(status_code=404, detail="ServCey 2 non disponible pour cet épisode")
        url = await byse.get_embed_url(ep.servcey2_file_code)
        return StreamResponse(url=url)


@router.get("/{episode_id}/player")
async def player_page(
    episode_id: int,
    db: AsyncSession = Depends(get_db),
):
    """HTML5 video player page — loaded inside iframe from frontend."""
    result = await db.execute(select(Episode).where(Episode.id == episode_id))
    ep = result.scalar_one_or_none()
    if not ep or not ep.servcey1_file_id:
        raise HTTPException(status_code=404, detail="Épisode introuvable")

    html = f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AnimeCey Player</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#000;width:100vw;height:100vh;overflow:hidden;display:flex;align-items:center;justify-content:center}}
video{{width:100%;height:100%;object-fit:contain}}
.msg{{color:#fff;font-family:system-ui,sans-serif;text-align:center;padding:2rem}}
.msg p{{margin:0.3rem 0}}
.sub{{font-size:0.85rem;opacity:0.6}}
.spinner{{width:48px;height:48px;border:4px solid rgba(255,255,255,0.2);border-top-color:#fff;border-radius:50%;animation:spin 0.8s linear infinite}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
</style></head><body>
<div id="loading" class="msg"><div class="spinner" style="margin:0 auto 1rem"></div><p>Chargement...</p></div>
<video id="player" controls autoplay playsinline style="display:none">
<source src="/api/episodes/{episode_id}/video" type="video/mp4">
</video>
<script>
var v=document.getElementById('player'),ld=document.getElementById('loading');
v.addEventListener('loadeddata',function(){{ld.style.display='none';v.style.display='block'}});
v.addEventListener('error',function(){{
  ld.style.display='none';
  document.body.innerHTML='<div class="msg"><p>Impossible de charger la vid\\u00e9o.</p><p class="sub">Essayez ServCey 2 pour une meilleure exp\\u00e9rience.</p></div>';
}});
</script>
</body></html>"""
    return HTMLResponse(html, headers={"X-Frame-Options": "ALLOWALL"})


@router.get("/{episode_id}/video")
async def video_proxy(
    episode_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Stream video from Telegram via MTProto FileStream (no size limit, supports Range)."""
    result = await db.execute(select(Episode).where(Episode.id == episode_id))
    ep = result.scalar_one_or_none()
    if not ep or not ep.servcey1_file_id:
        raise HTTPException(status_code=404, detail="Épisode introuvable")

    try:
        from bot.client import bot
    except ImportError:
        raise HTTPException(status_code=503, detail="Bot Telegram non disponible")

    if not bot.is_connected:
        raise HTTPException(status_code=503, detail="Bot Telegram non connecté")

    # Ensure we have a channel message for this episode
    msg_id = await _ensure_channel_msg(ep, db)
    if not msg_id:
        raise HTTPException(
            status_code=503,
            detail="Impossible d'accéder au fichier Telegram. Essayez ServCey 2.",
        )

    # Fetch the message from the channel (fresh file_reference)
    try:
        msg = await bot.get_messages(settings.TELEGRAM_CHANNEL_ID, msg_id)
    except Exception as exc:
        logger.exception("Failed to get channel message %s", msg_id)
        raise HTTPException(status_code=503, detail=f"Erreur Telegram: {exc}")

    from services.filestream import get_media_from_message, stream_media

    media = get_media_from_message(msg)
    if not media:
        raise HTTPException(status_code=404, detail="Fichier non trouvé dans le channel")

    # Parse Range header
    range_header = request.headers.get("range")
    range_start = 0
    range_end = None

    if range_header:
        range_spec = range_header.replace("bytes=", "").strip()
        parts = range_spec.split("-")
        range_start = int(parts[0]) if parts[0] else 0
        range_end = int(parts[1]) if len(parts) > 1 and parts[1] else None

    try:
        body, from_bytes, until_bytes, file_size, mime_type, file_name = await stream_media(
            bot, msg, range_start, range_end
        )
    except Exception as exc:
        logger.exception("FileStream error for ep %s", episode_id)
        raise HTTPException(status_code=503, detail=f"Erreur streaming: {exc}")

    headers = {
        "Content-Type": mime_type,
        "Content-Range": f"bytes {from_bytes}-{until_bytes}/{file_size}",
        "Content-Disposition": f'inline; filename="{file_name}"',
        "Accept-Ranges": "bytes",
    }

    status = 206 if range_header else 200
    if status == 200:
        headers["Content-Length"] = str(file_size)

    return StreamingResponse(body, status_code=status, headers=headers)


@router.get("/{episode_id}/dl")
async def download_file(
    episode_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Download video from Telegram (attachment disposition)."""
    result = await db.execute(select(Episode).where(Episode.id == episode_id))
    ep = result.scalar_one_or_none()
    if not ep or not ep.servcey1_file_id:
        raise HTTPException(status_code=404, detail="Épisode introuvable")

    try:
        from bot.client import bot
    except ImportError:
        raise HTTPException(status_code=503, detail="Bot Telegram non disponible")

    if not bot.is_connected:
        raise HTTPException(status_code=503, detail="Bot Telegram non connecté")

    msg_id = await _ensure_channel_msg(ep, db)
    if not msg_id:
        raise HTTPException(status_code=503, detail="Fichier non disponible")

    try:
        msg = await bot.get_messages(settings.TELEGRAM_CHANNEL_ID, msg_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Erreur Telegram: {exc}")

    from services.filestream import get_media_from_message, stream_media

    media = get_media_from_message(msg)
    if not media:
        raise HTTPException(status_code=404, detail="Fichier non trouvé")

    range_header = request.headers.get("range")
    range_start = 0
    range_end = None

    if range_header:
        range_spec = range_header.replace("bytes=", "").strip()
        parts = range_spec.split("-")
        range_start = int(parts[0]) if parts[0] else 0
        range_end = int(parts[1]) if len(parts) > 1 and parts[1] else None

    try:
        body, from_bytes, until_bytes, file_size, mime_type, file_name = await stream_media(
            bot, msg, range_start, range_end
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Erreur: {exc}")

    headers = {
        "Content-Type": mime_type,
        "Content-Range": f"bytes {from_bytes}-{until_bytes}/{file_size}",
        "Content-Disposition": f'attachment; filename="{file_name}"',
        "Accept-Ranges": "bytes",
    }

    status = 206 if range_header else 200
    if status == 200:
        headers["Content-Length"] = str(file_size)

    return StreamingResponse(body, status_code=status, headers=headers)


@router.post("/{episode_id}/like", response_model=LikeResponse)
async def like_episode(
    episode_id: int,
    request: Request,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Episode).where(Episode.id == episode_id))
    ep = result.scalar_one_or_none()
    if not ep:
        raise HTTPException(status_code=404, detail="Épisode introuvable")

    if user:
        existing = await db.execute(
            select(EpisodeLike).where(
                EpisodeLike.episode_id == episode_id,
                EpisodeLike.user_id == user.id,
            )
        )
    else:
        ip = get_client_ip(request)
        existing = await db.execute(
            select(EpisodeLike).where(
                EpisodeLike.episode_id == episode_id,
                EpisodeLike.ip_address == ip,
                EpisodeLike.user_id.is_(None),
            )
        )

    if existing.scalar_one_or_none():
        return LikeResponse(liked=True, likes_count=ep.likes_count)

    like = EpisodeLike(
        episode_id=episode_id,
        user_id=user.id if user else None,
        ip_address=get_client_ip(request) if not user else None,
    )
    db.add(like)
    ep.likes_count += 1
    await db.commit()
    return LikeResponse(liked=True, likes_count=ep.likes_count)


@router.delete("/{episode_id}/like", response_model=LikeResponse)
async def unlike_episode(
    episode_id: int,
    request: Request,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Episode).where(Episode.id == episode_id))
    ep = result.scalar_one_or_none()
    if not ep:
        raise HTTPException(status_code=404, detail="Épisode introuvable")

    if user:
        q = select(EpisodeLike).where(
            EpisodeLike.episode_id == episode_id,
            EpisodeLike.user_id == user.id,
        )
    else:
        ip = get_client_ip(request)
        q = select(EpisodeLike).where(
            EpisodeLike.episode_id == episode_id,
            EpisodeLike.ip_address == ip,
            EpisodeLike.user_id.is_(None),
        )

    existing = await db.execute(q)
    like = existing.scalar_one_or_none()
    if not like:
        return LikeResponse(liked=False, likes_count=ep.likes_count)

    await db.delete(like)
    ep.likes_count = max(0, ep.likes_count - 1)
    await db.commit()
    return LikeResponse(liked=False, likes_count=ep.likes_count)
