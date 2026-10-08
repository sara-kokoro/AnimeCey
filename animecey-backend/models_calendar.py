"""Calendrier des sorties (copié de franime.fr/calendrier).

Une ligne = un épisode annoncé pour une langue précise (VF ou VOSTFR).
La table est créée toute seule au démarrage par create_all() (rien à migrer).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class CalendarEntry(Base):
    __tablename__ = "calendar_entries"
    __table_args__ = (
        UniqueConstraint(
            "franime_id", "season_raw", "episode_number", "language",
            name="uq_calendar_entry",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # identifiant de l'animé chez FRAnime (paramètre anime_id du lien)
    franime_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    # saison telle qu'écrite par FRAnime : "1", "2", "3.1" (= saison 3, partie 1)
    season_raw: Mapped[str] = mapped_column(String(16), nullable=False, default="1")
    episode_number: Mapped[int] = mapped_column(Integer, nullable=False)
    language: Mapped[str] = mapped_column(String(8), nullable=False)  # "VF" | "VOSTFR"
    # heure de sortie, enregistrée en UTC
    release_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    # n° de l'animé chez nous (seulement si le titre correspond exactement)
    anime_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("animes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # alerte admins : envoyée à (UTC) + id des messages épinglés {"<id admin>": <id message>}
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pins: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    unpinned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
