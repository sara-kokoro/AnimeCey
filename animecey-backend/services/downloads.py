"""Téléchargement d'épisodes : tickets signés, limite par utilisateur, nom de fichier.

Déroulement : le front demande un ticket (compte connecté obligatoire), affiche la pub Monetag et un
compte à rebours, puis ouvre /api/episodes/{id}/download?ticket=... Le serveur refuse le ticket tant que
le délai n'est pas écoulé, donc appeler directement l'adresse du fichier ne permet pas de sauter la pub.

Un ticket vaut pour un seul téléchargement (le compteur ne le compte qu'une fois, ce qui permet de
reprendre un téléchargement interrompu) et expire après 2 h.

Variables d'environnement : DOWNLOAD_DAILY_LIMIT (défaut 5 par 24 h), DOWNLOAD_WAIT_SECONDS (défaut 8).
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import time
import unicodedata
from dataclasses import dataclass
from urllib.parse import quote

from config import settings


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "") or default)
    except ValueError:
        return default


DAILY_LIMIT = _env_int("DOWNLOAD_DAILY_LIMIT", 5)
WAIT_SECONDS = _env_int("DOWNLOAD_WAIT_SECONDS", 8)
TICKET_TTL = 2 * 3600


class TicketError(Exception):
    """Ticket invalide, trop tôt ou expiré (message affiché tel quel)."""


@dataclass
class Ticket:
    user_id: int
    episode_id: int
    issued_at: int
    jti: str


def _sig(payload: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), f"dl:{payload}".encode(), hashlib.sha256).hexdigest()[:32]


def make_ticket(user_id: int, episode_id: int) -> str:
    payload = f"{user_id}.{episode_id}.{int(time.time())}.{secrets.token_hex(8)}"
    return f"{payload}.{_sig(payload)}"


def check_ticket(ticket: str | None, episode_id: int) -> Ticket:
    if not ticket:
        raise TicketError("Ticket manquant.")
    payload, _, sig = ticket.rpartition(".")
    if not payload or not hmac.compare_digest(sig, _sig(payload)):
        raise TicketError("Ticket invalide.")
    try:
        user_s, ep_s, iat_s, jti = payload.split(".")
        t = Ticket(int(user_s), int(ep_s), int(iat_s), jti)
    except ValueError:
        raise TicketError("Ticket invalide.")
    if t.episode_id != episode_id:
        raise TicketError("Ticket invalide pour cet épisode.")
    now = time.time()
    if now > t.issued_at + TICKET_TTL:
        raise TicketError("Ticket expiré : relance le téléchargement.")
    if now + 1 < t.issued_at + WAIT_SECONDS:
        raise TicketError("Patiente encore quelques secondes avant de télécharger.")
    return t


def _clean(text: str) -> str:
    text = re.sub(r'[\\/:*?"<>|\x00-\x1f]', " ", text)
    return re.sub(r"\s+", " ", text).strip(" .")


def download_filename(title: str, is_film: bool, season: int, episode: int, language: str) -> str:
    """« Magi-Stream - The Batman (VF).mp4 » ou « Magi-Stream - Teen Wolf - S01E05 (VF).mp4 »."""
    base = _clean(title) or "Episode"
    if is_film:
        return f"Magi-Stream - {base} ({language}).mp4"
    return f"Magi-Stream - {base} - S{season:02d}E{episode:02d} ({language}).mp4"


def content_disposition(filename: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode() or "episode.mp4"
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"
