from __future__ import annotations

import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_client_ip, get_current_user, get_current_user_optional
from config import settings
from database import get_db
from models import Episode, EpisodeLike, User
from schemas import EpisodePublic, LikeResponse, StreamResponse
from services import byse
from services.stream_token import check_token, make_token

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


def _public_base(request: Request) -> str:
    """URL publique du backend. Derrière le proxy, le schéma vu est parfois http:// :
    on force https (sinon le navigateur bloque la vidéo en contenu mixte)."""
    base = (os.getenv("PUBLIC_BASE_URL") or str(request.base_url)).rstrip("/")
    if base.startswith("http://") and "localhost" not in base and "127.0.0.1" not in base:
        base = "https://" + base[len("http://"):]
    return base


def _parse_range(header: str | None, size: int) -> tuple[int, int | None] | None:
    """'bytes=a-b', 'bytes=a-' ou 'bytes=-n' -> (début, fin|None). None si invalide."""
    if not header:
        return 0, None
    spec = header.replace("bytes=", "").strip().split(",")[0]
    start_s, _, end_s = spec.partition("-")
    try:
        if start_s == "":  # suffixe : les n derniers octets
            n = int(end_s)
            return max(size - n, 0), None
        start = int(start_s)
        end = int(end_s) if end_s else None
    except ValueError:
        return None
    if start >= size or (end is not None and end < start):
        return None
    return start, end


async def _telegram_response(ep: Episode, request: Request, db: AsyncSession) -> StreamingResponse:
    """Lit le fichier de l'épisode depuis le canal Telegram (MTProto), avec support de Range.

    La lecture est confiée au pool de bots (services/botpool.py) : le bot le moins occupé sert la vidéo,
    et si Telegram le refuse, un autre prend le relais sans couper le spectateur.
    """
    from services import botpool

    if not ep.servcey1_file_id:
        raise HTTPException(status_code=404, detail="Épisode introuvable")

    msg_id = await _ensure_channel_msg(ep, db)
    if not msg_id:
        raise HTTPException(status_code=503, detail="Fichier introuvable dans le canal Telegram")

    try:
        handle = await botpool.pool.open_stream(msg_id, request.headers.get("range"), _parse_range)
    except botpool.RangeError as exc:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{exc.size}"})
    except botpool.MediaMissing:
        raise HTTPException(status_code=404, detail="Fichier non trouvé dans le canal")
    except botpool.PoolUnavailable as exc:
        logger.error("Aucun bot n'a pu lire l'épisode %s : %s", ep.id, exc)
        raise HTTPException(status_code=503, detail=f"Erreur streaming: {exc}")

    mime_type = handle.mime_type
    if not (mime_type or "").startswith("video/"):
        mime_type = "video/mp4"  # un MP4 envoyé comme document arrive parfois en octet-stream
    headers = {
        "Content-Type": mime_type,
        "Content-Length": str(handle.until_bytes - handle.from_bytes + 1),
        "Accept-Ranges": "bytes",
        "Cache-Control": "private, max-age=3600",
    }
    partial = request.headers.get("range") is not None
    if partial:
        headers["Content-Range"] = f"bytes {handle.from_bytes}-{handle.until_bytes}/{handle.file_size}"
    return StreamingResponse(handle.body, status_code=206 if partial else 200, headers=headers)


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
    server: Optional[str] = Query(None, pattern="^(servcey[12]|tmcooper)$"),
    db: AsyncSession = Depends(get_db),
):
    """Renvoie l'URL de lecture.

    - server=tmcooper (ou absent) : lien M3U8/MP4 résolu par TMCooper, rafraîchi
      toutes les 30 min par la synchro ;
    - server=servcey1/2 : anciens serveurs (Telegram / Byse) s'ils sont dispo ;
      sinon on retombe sur le lien TMCooper de l'épisode s'il existe, pour que
      un front qui demande encore servcey1 continue de fonctionner.
    """
    result = await db.execute(select(Episode).where(Episode.id == episode_id))
    ep = result.scalar_one_or_none()
    if not ep:
        raise HTTPException(status_code=404, detail="Épisode introuvable")

    def _tmcooper_response() -> StreamResponse:
        return StreamResponse(url=ep.stream_url, type=ep.stream_type)

    if server == "tmcooper":
        if not ep.stream_url:
            raise HTTPException(status_code=404, detail="Aucun lien TMCooper pour cet épisode")
        return _tmcooper_response()

    if server is None and ep.stream_url:
        return _tmcooper_response()

    if server in (None, "servcey1") and ep.servcey1_available and ep.servcey1_file_id:
        token = make_token(episode_id)
        return StreamResponse(url=f"{_public_base(request)}/api/episodes/{episode_id}/video?t={token}", type="mp4")

    if server in (None, "servcey2") and ep.servcey2_available and ep.servcey2_file_code:
        url = await byse.get_embed_url(ep.servcey2_file_code)
        return StreamResponse(url=url)

    if ep.stream_url:
        return _tmcooper_response()

    raise HTTPException(status_code=404, detail="Aucune source de lecture disponible pour cet épisode")


@router.get("/{episode_id}/video")
async def video_proxy(
    episode_id: int,
    request: Request,
    t: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Vidéo servie depuis Telegram (MTProto, sans limite de taille, avec Range).

    Exige un jeton signé (?t=...) obtenu via /stream : l'id seul ne suffit pas.
    """
    if not check_token(episode_id, t):
        raise HTTPException(status_code=403, detail="Lien expiré ou invalide")
    ep = (await db.execute(select(Episode).where(Episode.id == episode_id))).scalar_one_or_none()
    if not ep:
        raise HTTPException(status_code=404, detail="Épisode introuvable")
    return await _telegram_response(ep, request, db)


_thumb_cache: dict[int, bytes] = {}


@router.get("/{episode_id}/thumb")
async def episode_thumb(episode_id: int, db: AsyncSession = Depends(get_db)):
    """Vignette de l'épisode, lue depuis le canal Telegram puis gardée en cache."""
    ep = (await db.execute(select(Episode).where(Episode.id == episode_id))).scalar_one_or_none()
    if not ep or not ep.thumb_msg_id:
        raise HTTPException(status_code=404, detail="Vignette introuvable")
    data = _thumb_cache.get(ep.thumb_msg_id)
    if data is None:
        from services import botpool

        client = botpool.pool.any_client()
        if client is None:
            raise HTTPException(status_code=503, detail="Aucun bot Telegram disponible")
        try:
            msg = await client.get_messages(settings.TELEGRAM_CHANNEL_ID, ep.thumb_msg_id)
            if not msg or not msg.photo:
                raise HTTPException(status_code=404, detail="Vignette introuvable")
            buf = await client.download_media(msg, in_memory=True)
            data = buf.getvalue()
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("thumb ep %s", episode_id)
            raise HTTPException(status_code=503, detail=f"Erreur Telegram: {exc}")
        if len(_thumb_cache) >= 400:
            _thumb_cache.pop(next(iter(_thumb_cache)))
        _thumb_cache[ep.thumb_msg_id] = data
    return Response(
        content=data,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=604800, immutable"},
    )


@router.get("/{episode_id}/like", response_model=LikeResponse)
async def like_status(
    episode_id: int,
    request: Request,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """L'épisode est-il déjà aimé par ce visiteur (compte connecté, sinon son adresse IP) ?"""
    ep = (await db.execute(select(Episode).where(Episode.id == episode_id))).scalar_one_or_none()
    if not ep:
        raise HTTPException(status_code=404, detail="Épisode introuvable")
    if user:
        q = select(EpisodeLike.id).where(EpisodeLike.episode_id == episode_id, EpisodeLike.user_id == user.id)
    else:
        q = select(EpisodeLike.id).where(
            EpisodeLike.episode_id == episode_id,
            EpisodeLike.ip_address == get_client_ip(request),
            EpisodeLike.user_id.is_(None),
        )
    liked = (await db.execute(q)).first() is not None
    return LikeResponse(liked=liked, likes_count=ep.likes_count)


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
