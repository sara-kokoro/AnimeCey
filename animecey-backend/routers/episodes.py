from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_client_ip, get_current_user, get_current_user_optional
from database import get_db
from models import Episode, EpisodeLike, User
from schemas import EpisodePublic, LikeResponse, StreamResponse
from services import byse, telegram_stream

router = APIRouter()


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


@router.get("/{episode_id}/stream", response_model=StreamResponse)
async def stream(
    episode_id: int,
    server: str = Query(..., regex="^servcey[12]$"),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Episode).where(Episode.id == episode_id))
    ep = result.scalar_one_or_none()
    if not ep:
        raise HTTPException(status_code=404, detail="Épisode introuvable")

    if server == "servcey1":
        if not ep.servcey1_available or not ep.servcey1_file_id:
            raise HTTPException(status_code=404, detail="Serveur non disponible pour cet épisode")
        url = await telegram_stream.get_stream_url(ep.servcey1_file_id)
    else:
        if not ep.servcey2_available or not ep.servcey2_file_code:
            raise HTTPException(status_code=404, detail="Serveur non disponible pour cet épisode")
        url = await byse.get_embed_url(ep.servcey2_file_code)

    return StreamResponse(url=url)


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
