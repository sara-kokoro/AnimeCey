"""Jetons signés pour les liens vidéo : /api/episodes/{id}/video?t=...

Le jeton lie un épisode à une date d'expiration et est signé avec SECRET_KEY.
Sans jeton valide, /video répond 403. Les ids d'épisodes (1, 2, 3...) ne suffisent plus.
La date d'expiration est arrondie par tranches de 6 h : pendant une tranche, le lien d'un
épisode est identique (le lecteur ne se recharge pas si le front redemande le lien).
"""

from __future__ import annotations

import hashlib
import hmac
import time

from config import settings

_WINDOW = 6 * 3600  # le lien vit entre 6 h et 12 h


def _sig(episode_id: int, exp: int) -> str:
    msg = f"video:{episode_id}:{exp}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()[:32]


def make_token(episode_id: int) -> str:
    exp = (int(time.time()) // _WINDOW + 2) * _WINDOW
    return f"{exp}.{_sig(episode_id, exp)}"


def check_token(episode_id: int, token: str | None) -> bool:
    if not token or "." not in token:
        return False
    exp_s, _, sig = token.partition(".")
    try:
        exp = int(exp_s)
    except ValueError:
        return False
    return exp > time.time() and hmac.compare_digest(sig, _sig(episode_id, exp))
