"""Signalements de problèmes envoyés depuis le site (épisode manquant, vidéo injouable...).

La table `reports` est créée automatiquement au démarrage (Base.metadata.create_all dans init_db).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# clé envoyée par le site -> libellé affiché dans le bot
REPORT_KINDS: dict[str, str] = {
    "not_playable": "Vidéo injouable",
    "missing_episode": "Épisode manquant",
    "wrong_language": "Mauvaise langue / audio",
    "subtitles": "Sous-titres absents ou décalés",
    "wrong_content": "Mauvais épisode / mauvaise vidéo",
    "wrong_info": "Infos erronées (titre, synopsis, affiche)",
    "quality": "Image ou son de mauvaise qualité",
    "other": "Autre problème",
}


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    anime_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("animes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    episode_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("episodes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # « Titre — Saison 1 · Épisode 5 (VF) » figé au moment du signalement (reste lisible si l'épisode est supprimé)
    label: Mapped[str | None] = mapped_column(String(300), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact: Mapped[str | None] = mapped_column(String(120), nullable=True)
    page_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    ip_hash: Mapped[str | None] = mapped_column(String(24), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="open", index=True)  # open | resolved | ignored
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)  # signalements identiques regroupés
    tg_messages: Mapped[list | None] = mapped_column(JSON, nullable=True)  # [[chat_id, message_id], ...]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
