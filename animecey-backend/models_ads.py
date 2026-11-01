"""Pubs manuelles, appareils/visites, notifications de l'app.

Les tables sont créées automatiquement au démarrage (Base.metadata.create_all dans init_db) :
ce module doit être importé avant (il l'est par routers/ads.py, routers/track.py et routers/app_notifications.py).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, JSON, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Emplacements de pub : clé -> libellé affiché dans le bot
AD_SLOTS: dict[str, str] = {
    "home_top": "Accueil · haut",
    "home_bottom": "Accueil · bas de page",
    "detail": "Fiche d'un animé / film / série",
    "watch": "Sous le lecteur (en ligne)",
    "downloads": "Mes téléchargements (lecteur et liste)",
    "offline": "Page hors connexion de l'app",
}

# Pages où une notification de l'app peut mener : clé -> libellé
APP_PAGES: dict[str, str] = {
    "home": "Accueil",
    "downloads": "Mes téléchargements",
    "catalogue": "Catalogue",
    "calendar": "Calendrier",
    "donate": "Faire un don",
}


class AdCampaign(Base):
    """Une pub vendue à la main : image ou GIF, lien, texte + bouton facultatifs, emplacements et durée."""

    __tablename__ = "ad_campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    advertiser: Mapped[str | None] = mapped_column(String(120), nullable=True)
    media: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    mime: Mapped[str] = mapped_column(String(60), nullable=False)
    link_url: Mapped[str] = mapped_column(String(600), nullable=False)
    text: Mapped[str | None] = mapped_column(String(400), nullable=True)
    button_text: Mapped[str | None] = mapped_column(String(40), nullable=True)
    button_url: Mapped[str | None] = mapped_column(String(600), nullable=True)
    placements: Mapped[list] = mapped_column(JSON, nullable=False, default=list)  # ["home_top", ...] ou ["all"]
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    views: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    clicks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Device(Base):
    """Un appareil (navigateur ou application), identifié par un code anonyme tiré au hasard : sert aux statistiques."""

    __tablename__ = "devices"

    device_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    platform: Mapped[str] = mapped_column(String(8), nullable=False, default="web")  # web | app
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)


class ViewEvent(Base):
    """Un épisode ouvert en lecture (au plus une fois par appareil et par épisode toutes les 6 h)."""

    __tablename__ = "view_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    episode_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    anime_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    device_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    platform: Mapped[str] = mapped_column(String(8), nullable=False, default="web")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)


class AppNotification(Base):
    """Notification envoyée à tous les utilisateurs de l'application (commande /notification du bot)."""

    __tablename__ = "app_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    image: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    image_mime: Mapped[str | None] = mapped_column(String(60), nullable=True)
    path: Mapped[str] = mapped_column(String(200), nullable=False, default="/")  # page ouverte au clic : « /anime/12 »
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
