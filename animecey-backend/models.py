from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Enums ──────────────────────────────────────────────────────────────


class AnimeType(str, enum.Enum):
    serie = "serie"
    film = "film"


class AnimeStatus(str, enum.Enum):
    ongoing = "ongoing"
    completed = "completed"
    upcoming = "upcoming"


class FolderType(str, enum.Enum):
    anime = "anime"
    language = "language"
    season = "season"


class LanguageEnum(str, enum.Enum):
    VF = "VF"
    VOSTFR = "VOSTFR"


class UserRole(str, enum.Enum):
    user = "user"
    admin = "admin"


class WatchlistStatus(str, enum.Enum):
    watching = "watching"
    completed = "completed"
    planned = "planned"
    dropped = "dropped"


class BroadcastType(str, enum.Enum):
    info = "info"
    new = "new"
    alert = "alert"
    maintenance = "maintenance"


class BroadcastTarget(str, enum.Enum):
    all = "all"
    users = "users"


# ── Models ─────────────────────────────────────────────────────────────


class Anime(Base):
    __tablename__ = "animes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    title_jp: Mapped[str | None] = mapped_column(String(255), nullable=True)
    type: Mapped[AnimeType] = mapped_column(Enum(AnimeType), nullable=False)
    status: Mapped[AnimeStatus] = mapped_column(Enum(AnimeStatus), nullable=False)
    synopsis: Mapped[str | None] = mapped_column(Text, nullable=True)
    poster_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    banner_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    genres: Mapped[list | None] = mapped_column(JSON, nullable=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tmdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True)
    anilist_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True)
    trailer_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    # Téléchargement autorisé pour les épisodes de ce titre (réglé avec /dl dans le bot ; éteint par défaut)
    downloadable: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    # « anime » (animation) ou « live » (films et séries avec de vrais acteurs)
    category: Mapped[str] = mapped_column(String(10), nullable=False, default="anime", server_default="anime")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    folders: Mapped[list["Folder"]] = relationship(back_populates="anime", cascade="all, delete-orphan")
    episodes: Mapped[list["Episode"]] = relationship(back_populates="anime", cascade="all, delete-orphan")


class Folder(Base):
    __tablename__ = "folders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    anime_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("animes.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    folder_type: Mapped[FolderType] = mapped_column(Enum(FolderType), nullable=False)
    language: Mapped[LanguageEnum | None] = mapped_column(Enum(LanguageEnum), nullable=True)
    season_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("folders.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    anime: Mapped["Anime | None"] = relationship(back_populates="folders")
    parent: Mapped["Folder | None"] = relationship(remote_side="Folder.id", back_populates="children")
    children: Mapped[list["Folder"]] = relationship(back_populates="parent", cascade="all, delete-orphan")
    episodes: Mapped[list["Episode"]] = relationship(back_populates="folder")


class Episode(Base):
    __tablename__ = "episodes"
    __table_args__ = (
        UniqueConstraint("folder_id", "episode_number", "language", name="uq_episode_folder_num_lang"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    anime_id: Mapped[int] = mapped_column(Integer, ForeignKey("animes.id"), nullable=False)
    folder_id: Mapped[int] = mapped_column(Integer, ForeignKey("folders.id"), nullable=False)
    episode_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    language: Mapped[LanguageEnum] = mapped_column(Enum(LanguageEnum), nullable=False)
    season_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    servcey1_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    servcey1_msg_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    servcey1_available: Mapped[bool] = mapped_column(Boolean, default=False)
    # Message du canal Telegram qui contient la vignette de l'épisode (photo)
    thumb_msg_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    servcey2_file_code: Mapped[str | None] = mapped_column(String(255), nullable=True)
    servcey2_available: Mapped[bool] = mapped_column(Boolean, default=False)
    # Lien de lecture résolu via TMCooper (rafraîchi régulièrement, il expire)
    stream_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    stream_type: Mapped[str | None] = mapped_column(String(10), nullable=True)  # mp4 | m3u8 | embed
    links_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    likes_count: Mapped[int] = mapped_column(Integer, default=0)
    comments_count: Mapped[int] = mapped_column(Integer, default=0)
    air_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    anime: Mapped["Anime"] = relationship(back_populates="episodes")
    folder: Mapped["Folder"] = relationship(back_populates="episodes")

    @property
    def stream_available(self) -> bool:
        return bool(self.stream_url)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.user)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Watchlist(Base):
    __tablename__ = "watchlist"
    __table_args__ = (UniqueConstraint("user_id", "anime_id", name="uq_watchlist_user_anime"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    anime_id: Mapped[int] = mapped_column(Integer, ForeignKey("animes.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[WatchlistStatus] = mapped_column(Enum(WatchlistStatus), nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "anime_id", name="uq_favorite_user_anime"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    anime_id: Mapped[int] = mapped_column(Integer, ForeignKey("animes.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class WatchHistory(Base):
    __tablename__ = "watch_history"
    __table_args__ = (UniqueConstraint("user_id", "episode_id", name="uq_history_user_ep"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    episode_id: Mapped[int] = mapped_column(Integer, ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False)
    progress_seconds: Mapped[int] = mapped_column(Integer, default=0)
    watched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class DownloadLog(Base):
    """Un téléchargement d'épisode : sert à la limite par utilisateur et par 24 h."""

    __tablename__ = "download_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    episode_id: Mapped[int] = mapped_column(Integer, ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False)
    jti: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)  # identifiant du ticket
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)


class EpisodeLike(Base):
    __tablename__ = "episode_likes"
    __table_args__ = (UniqueConstraint("episode_id", "user_id", name="uq_ep_like_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    episode_id: Mapped[int] = mapped_column(Integer, ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    episode_id: Mapped[int] = mapped_column(Integer, ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content: Mapped[str] = mapped_column(String(500), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("comments.id"), nullable=True)
    likes_count: Mapped[int] = mapped_column(Integer, default=0)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    user: Mapped["User"] = relationship()
    replies: Mapped[list["Comment"]] = relationship(
        back_populates="parent_comment", cascade="all, delete-orphan"
    )
    parent_comment: Mapped["Comment | None"] = relationship(
        remote_side="Comment.id", back_populates="replies"
    )


class CommentLike(Base):
    __tablename__ = "comment_likes"
    __table_args__ = (UniqueConstraint("comment_id", "user_id", name="uq_comment_like_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    comment_id: Mapped[int] = mapped_column(Integer, ForeignKey("comments.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Broadcast(Base):
    __tablename__ = "broadcasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    caption: Mapped[str | None] = mapped_column(String(500), nullable=True)
    type: Mapped[BroadcastType] = mapped_column(Enum(BroadcastType), nullable=False)
    target: Mapped[BroadcastTarget] = mapped_column(Enum(BroadcastTarget), default=BroadcastTarget.all)
    admin_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    reads_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class BroadcastRead(Base):
    __tablename__ = "broadcast_reads"
    __table_args__ = (UniqueConstraint("broadcast_id", "user_id", name="uq_broadcast_read"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    broadcast_id: Mapped[int] = mapped_column(Integer, ForeignKey("broadcasts.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    endpoint: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    p256dh: Mapped[str] = mapped_column(Text, nullable=False)
    auth: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class TmcooperSource(Base):
    """Un (animé, saison, version) à synchroniser depuis l'API TMCooper."""

    __tablename__ = "tmcooper_sources"
    __table_args__ = (
        UniqueConstraint("anime_id", "season", "version", name="uq_tmcooper_source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    anime_id: Mapped[int] = mapped_column(Integer, ForeignKey("animes.id", ondelete="CASCADE"), nullable=False)
    api_name: Mapped[str] = mapped_column(String(255), nullable=False)  # paramètre n= de l'API
    season: Mapped[str] = mapped_column(String(50), nullable=False, default="saison1")
    version: Mapped[str] = mapped_column(String(10), nullable=False, default="vostfr")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class TmdbCache(Base):
    __tablename__ = "tmdb_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cache_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    data_json: Mapped[str] = mapped_column(Text, nullable=False)
    cached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class BotSession(Base):
    __tablename__ = "bot_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    current_state: Mapped[str | None] = mapped_column(String(50), nullable=True)
    selected_folder_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("folders.id"), nullable=True)
    selected_language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    selected_season: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_activity: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
