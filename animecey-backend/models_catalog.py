"""Index léger du catalogue (table catalog_titles).

Même structure que la migration alembic 0001_catalog_titles : ainsi, que la
table soit créée par create_all() au démarrage ou par alembic, le résultat est
identique.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class CatalogTitle(Base):
    __tablename__ = "catalog_titles"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_catalog_titles_source_external_id"),
        CheckConstraint("type IN ('anime', 'serie', 'film')", name="ck_catalog_titles_type"),
        CheckConstraint("source IN ('tmcooper', 'streamsdl')", name="ck_catalog_titles_source"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    title_jp: Mapped[str | None] = mapped_column(String(500), nullable=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    poster_url: Mapped[str | None] = mapped_column(String(1000), nullable=True, index=False)
    tmdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    anilist_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    is_ongoing: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AnimeSeason(Base):
    """Saisons / sagas d'un animé ouvert depuis le catalogue.

    season_number : numéro séquentiel 1..N (ordre d'Anime-Sama) utilisé dans episodes.
    api_season    : nom de la saison tel que TMCooper l'attend (paramètre s=).
    label         : nom affiché ("Saga 1 (East Blue)", "Saison 2 Partie 1", "Film"...).
    """

    __tablename__ = "anime_seasons"
    __table_args__ = (
        UniqueConstraint("anime_id", "api_season", name="uq_anime_seasons_api"),
        UniqueConstraint("anime_id", "season_number", name="uq_anime_seasons_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    anime_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("animes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    season_number: Mapped[int] = mapped_column(Integer, nullable=False)
    api_season: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)


class EpisodeServer(Base):
    """Un serveur de lecture (lecteur) disponible pour un épisode."""

    __tablename__ = "episode_servers"
    __table_args__ = (
        UniqueConstraint("episode_id", "position", name="uq_episode_servers_position"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    episode_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(String(10), nullable=False, default="embed")
