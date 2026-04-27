from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ── Generic ────────────────────────────────────────────────────────────


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    pages: int


# ── Auth ───────────────────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=6)


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserPublic"


class UpdateProfileRequest(BaseModel):
    username: Optional[str] = Field(None, min_length=2, max_length=50)
    email: Optional[str] = Field(None, max_length=255)
    avatar_url: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6)


# ── Users ──────────────────────────────────────────────────────────────


class UserPublic(BaseModel):
    id: int
    username: str
    email: str
    role: str
    avatar_url: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserBrief(BaseModel):
    id: int
    username: str
    avatar_url: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Anime ──────────────────────────────────────────────────────────────


class AnimePublic(BaseModel):
    id: int
    title: str
    title_jp: Optional[str] = None
    type: str
    status: str
    synopsis: Optional[str] = None
    poster_url: Optional[str] = None
    banner_url: Optional[str] = None
    genres: Optional[List[str]] = None
    score: float = 0.0
    year: Optional[int] = None
    trailer_url: Optional[str] = None
    languages_available: List[str] = []
    seasons_count: int = 0
    episodes_count: int = 0
    is_featured: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class AnimeCreate(BaseModel):
    title: str = Field(..., max_length=255)
    title_jp: Optional[str] = None
    type: str
    status: str
    synopsis: Optional[str] = None
    poster_url: Optional[str] = None
    banner_url: Optional[str] = None
    genres: Optional[List[str]] = None
    score: float = 0.0
    year: Optional[int] = None
    tmdb_id: Optional[int] = None
    anilist_id: Optional[int] = None
    trailer_url: Optional[str] = None
    is_featured: bool = False


class AnimeUpdate(BaseModel):
    title: Optional[str] = None
    title_jp: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None
    synopsis: Optional[str] = None
    poster_url: Optional[str] = None
    banner_url: Optional[str] = None
    genres: Optional[List[str]] = None
    score: Optional[float] = None
    year: Optional[int] = None
    tmdb_id: Optional[int] = None
    anilist_id: Optional[int] = None
    trailer_url: Optional[str] = None
    is_featured: Optional[bool] = None


# ── Folder ─────────────────────────────────────────────────────────────


class FolderPublic(BaseModel):
    id: int
    anime_id: Optional[int] = None
    name: str
    folder_type: str
    language: Optional[str] = None
    season_number: Optional[int] = None
    parent_id: Optional[int] = None
    children: List["FolderPublic"] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class FolderCreate(BaseModel):
    anime_id: Optional[int] = None
    name: str = Field(..., max_length=255)
    folder_type: str
    language: Optional[str] = None
    season_number: Optional[int] = None
    parent_id: Optional[int] = None


# ── Episode ────────────────────────────────────────────────────────────


class EpisodePublic(BaseModel):
    id: int
    anime_id: int
    episode_number: int
    title: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration: Optional[int] = None
    language: str
    season_number: int
    servcey1_available: bool = False
    servcey2_available: bool = False
    likes_count: int = 0
    comments_count: int = 0
    air_date: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class EpisodeAdmin(EpisodePublic):
    folder_id: int
    servcey1_file_id: Optional[str] = None
    servcey2_file_code: Optional[str] = None


class EpisodeCreate(BaseModel):
    anime_id: int
    folder_id: int
    episode_number: int
    title: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration: Optional[int] = None
    language: str
    season_number: int = 1
    servcey1_file_id: Optional[str] = None
    servcey1_available: bool = False
    servcey2_file_code: Optional[str] = None
    servcey2_available: bool = False


class EpisodeUpdate(BaseModel):
    episode_number: Optional[int] = None
    title: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration: Optional[int] = None
    language: Optional[str] = None
    season_number: Optional[int] = None
    servcey1_file_id: Optional[str] = None
    servcey1_available: Optional[bool] = None
    servcey2_file_code: Optional[str] = None
    servcey2_available: Optional[bool] = None


class StreamResponse(BaseModel):
    url: str


# ── Comments ───────────────────────────────────────────────────────────


class CommentPublic(BaseModel):
    id: int
    user: UserBrief
    content: str
    likes_count: int = 0
    is_liked_by_me: bool = False
    parent_id: Optional[int] = None
    replies: List["CommentPublic"] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class CommentCreate(BaseModel):
    episode_id: int
    content: str = Field(..., max_length=500)
    parent_id: Optional[int] = None


# ── Like ───────────────────────────────────────────────────────────────


class LikeResponse(BaseModel):
    liked: bool
    likes_count: int


# ── Watchlist ──────────────────────────────────────────────────────────


class WatchlistItem(BaseModel):
    id: int
    anime: AnimePublic
    status: str
    added_at: datetime

    model_config = {"from_attributes": True}


class WatchlistRequest(BaseModel):
    anime_id: int
    status: str


# ── Favorites ──────────────────────────────────────────────────────────


class FavoriteItem(BaseModel):
    id: int
    anime: AnimePublic
    created_at: datetime

    model_config = {"from_attributes": True}


# ── History ────────────────────────────────────────────────────────────


class HistoryItem(BaseModel):
    id: int
    episode: EpisodePublic
    anime: AnimePublic
    progress_seconds: int
    watched_at: datetime

    model_config = {"from_attributes": True}


class HistoryRequest(BaseModel):
    episode_id: int
    progress_seconds: int


# ── Notifications / Broadcasts ─────────────────────────────────────────


class BroadcastPublic(BaseModel):
    id: int
    title: str
    content: str
    image_url: Optional[str] = None
    caption: Optional[str] = None
    type: str
    target: str = "all"
    is_read: bool = False
    reads_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class BroadcastCreate(BaseModel):
    title: str = Field(..., max_length=255)
    content: str
    image_url: Optional[str] = None
    caption: Optional[str] = None
    type: str
    target: str = "all"


class UnreadCountResponse(BaseModel):
    count: int


# ── Push ───────────────────────────────────────────────────────────────


class PushSubscribeRequest(BaseModel):
    endpoint: str
    p256dh: str
    auth: str


class PushUnsubscribeRequest(BaseModel):
    endpoint: str


# ── Admin ──────────────────────────────────────────────────────────────


class AdminStatsResponse(BaseModel):
    animes_count: int
    episodes_count: int
    users_count: int
    comments_count: int
    recent_uploads: List[EpisodeAdmin]


class SetFeaturedRequest(BaseModel):
    is_featured: bool


class SetRoleRequest(BaseModel):
    role: str
