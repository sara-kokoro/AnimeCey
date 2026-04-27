from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from auth import get_current_user
from database import get_db
from models import Anime, Episode, Favorite, User, WatchHistory, Watchlist
from schemas import (
    EpisodePublic,
    AnimePublic,
    FavoriteItem,
    HistoryItem,
    HistoryRequest,
    WatchlistItem,
    WatchlistRequest,
)

router = APIRouter()


# ── Watchlist ──────────────────────────────────────────────────────────


@router.get("/watchlist")
async def get_watchlist(
    status: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(Watchlist).where(Watchlist.user_id == user.id)
    if status:
        q = q.where(Watchlist.status == status)
    result = await db.execute(q.order_by(Watchlist.added_at.desc()))
    items = result.scalars().all()
    out = []
    for w in items:
        anime = await db.execute(select(Anime).where(Anime.id == w.anime_id))
        a = anime.scalar_one_or_none()
        if a:
            out.append({
                "id": w.id,
                "anime": AnimePublic.model_validate(a).model_dump(),
                "status": w.status.value if hasattr(w.status, "value") else w.status,
                "added_at": w.added_at.isoformat(),
            })
    return out


@router.post("/watchlist")
async def add_to_watchlist(
    body: WatchlistRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(Watchlist).where(Watchlist.user_id == user.id, Watchlist.anime_id == body.anime_id)
    )
    w = existing.scalar_one_or_none()
    if w:
        w.status = body.status
    else:
        w = Watchlist(user_id=user.id, anime_id=body.anime_id, status=body.status)
        db.add(w)
    await db.commit()
    return {"detail": "Watchlist mise à jour"}


@router.delete("/watchlist/{anime_id}", status_code=204)
async def remove_from_watchlist(
    anime_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        delete(Watchlist).where(Watchlist.user_id == user.id, Watchlist.anime_id == anime_id)
    )
    await db.commit()


# ── Favorites ──────────────────────────────────────────────────────────


@router.get("/favorites")
async def get_favorites(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Favorite).where(Favorite.user_id == user.id).order_by(Favorite.created_at.desc())
    )
    items = result.scalars().all()
    out = []
    for f in items:
        anime = await db.execute(select(Anime).where(Anime.id == f.anime_id))
        a = anime.scalar_one_or_none()
        if a:
            out.append({
                "id": f.id,
                "anime": AnimePublic.model_validate(a).model_dump(),
                "created_at": f.created_at.isoformat(),
            })
    return out


@router.post("/favorites/{anime_id}")
async def add_favorite(
    anime_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(Favorite).where(Favorite.user_id == user.id, Favorite.anime_id == anime_id)
    )
    if existing.scalar_one_or_none():
        return {"detail": "Déjà dans les favoris"}
    db.add(Favorite(user_id=user.id, anime_id=anime_id))
    await db.commit()
    return {"detail": "Ajouté aux favoris"}


@router.delete("/favorites/{anime_id}", status_code=204)
async def remove_favorite(
    anime_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        delete(Favorite).where(Favorite.user_id == user.id, Favorite.anime_id == anime_id)
    )
    await db.commit()


# ── History ────────────────────────────────────────────────────────────


@router.get("/history")
async def get_history(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WatchHistory)
        .where(WatchHistory.user_id == user.id)
        .order_by(WatchHistory.watched_at.desc())
    )
    items = result.scalars().all()
    out = []
    for h in items:
        ep_r = await db.execute(select(Episode).where(Episode.id == h.episode_id))
        ep = ep_r.scalar_one_or_none()
        if not ep:
            continue
        anime_r = await db.execute(select(Anime).where(Anime.id == ep.anime_id))
        anime = anime_r.scalar_one_or_none()
        if not anime:
            continue
        out.append({
            "id": h.id,
            "episode": EpisodePublic.model_validate(ep).model_dump(),
            "anime": AnimePublic.model_validate(anime).model_dump(),
            "progress_seconds": h.progress_seconds,
            "watched_at": h.watched_at.isoformat(),
        })
    return out


@router.post("/history")
async def update_history(
    body: HistoryRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(WatchHistory).where(
            WatchHistory.user_id == user.id,
            WatchHistory.episode_id == body.episode_id,
        )
    )
    h = existing.scalar_one_or_none()
    if h:
        h.progress_seconds = body.progress_seconds
    else:
        h = WatchHistory(
            user_id=user.id,
            episode_id=body.episode_id,
            progress_seconds=body.progress_seconds,
        )
        db.add(h)
    await db.commit()
    return {"detail": "Historique mis à jour"}


@router.get("/continue-watching")
async def continue_watching(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WatchHistory)
        .where(WatchHistory.user_id == user.id)
        .order_by(WatchHistory.watched_at.desc())
        .limit(20)
    )
    items = result.scalars().all()
    out = []
    for h in items:
        if len(out) >= 12:
            break
        ep_r = await db.execute(select(Episode).where(Episode.id == h.episode_id))
        ep = ep_r.scalar_one_or_none()
        if not ep or not ep.duration:
            continue
        if h.progress_seconds >= ep.duration * 0.9:
            continue
        anime_r = await db.execute(select(Anime).where(Anime.id == ep.anime_id))
        anime = anime_r.scalar_one_or_none()
        if not anime:
            continue
        out.append({
            "id": h.id,
            "episode": EpisodePublic.model_validate(ep).model_dump(),
            "anime": AnimePublic.model_validate(anime).model_dump(),
            "progress_seconds": h.progress_seconds,
            "watched_at": h.watched_at.isoformat(),
        })
    return out
