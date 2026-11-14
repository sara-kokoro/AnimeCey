"""Calendrier des sorties (copié de franime.fr/calendrier).

Une ligne = un épisode annoncé pour une langue précise (VF ou VOSTFR).
La table est créée toute seule au démarrage par create_all() (rien à migrer).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class CalendarState(Base):
    """Petite mémoire du calendrier (ex. date de la dernière lecture réussie de FRAnime).

    Gardée en base pour survivre aux redémarrages : sans ça, chaque redéploiement relirait la page
    (et consommerait des crédits ZenRows). Table créée par create_all().
    """

    __tablename__ = "calendar_state"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(String(100), nullable=False)


class CalendarVfSlot(Base):
    """Heure de sortie VF d'un animé du calendrier AniList (réglée avec /vf dans le bot).

    Les jours sont ceux de la VO (AniList) ; seule l'heure change. Heure en UTC (Lomé/Togo = UTC+0).
    Table créée toute seule au démarrage par create_all().
    """

    __tablename__ = "calendar_vf_slots"

    anilist_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    hour: Mapped[int] = mapped_column(Integer, nullable=False)
    minute: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CalendarEntry(Base):
    __tablename__ = "calendar_entries"
    __table_args__ = (
        UniqueConstraint(
            "franime_id", "season_raw", "episode_number", "language",
            name="uq_calendar_entry",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # identifiant de l'animé chez la source : n° FRAnime (positif, ancienne source) ou
    # -n° AniList (négatif, nouvelle source) — le signe évite toute collision entre les deux
    # et ne demande aucune migration.
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


class TmdbRelease(Base):
    """Sortie annoncée par TMDB (film, nouvelle série, épisode d'une série suivie), lue tous les 3 jours.

    Une ligne = une sortie à une date précise (jour, sans heure : TMDB ne donne pas l'heure).
    L'alerte aux admins part le jour J (voir services/tmdb_releases.py). Table créée par create_all().
    """

    __tablename__ = "tmdb_releases"
    __table_args__ = (
        UniqueConstraint("tmdb_id", "media", "kind", "season_number", "episode_number", name="uq_tmdb_release"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tmdb_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    media: Mapped[str] = mapped_column(String(5), nullable=False)  # "movie" | "tv"
    kind: Mapped[str] = mapped_column(String(10), nullable=False)  # "movie" | "premiere" | "episode"
    season_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    episode_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    original_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    episode_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    overview: Mapped[str | None] = mapped_column(Text, nullable=True)
    poster_path: Mapped[str | None] = mapped_column(String(200), nullable=True)
    popularity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_anime: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # animation japonaise : /ajouter
    release_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    # n° du titre chez nous s'il est déjà au catalogue (même fiche TMDB)
    anime_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("animes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
