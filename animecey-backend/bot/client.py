"""Pyrogram bot client singleton.

Initialised with credentials from ``config.settings``.  The ``bot``
instance is started/stopped inside the FastAPI lifespan in ``main.py``.
"""

from __future__ import annotations

import pyrogram.utils as _pg_utils
from pyrogram import Client
from pyrogram.enums import ParseMode

from config import settings

# ── Correctif : canaux Telegram récents ────────────────────────────────────
# Pyrogram 2.0.106 refuse les identifiants de canal inférieurs à -1002147483647
# (« Peer id invalid »). Les canaux créés récemment ont des ids plus grands
# (ex. -1003702483523) : on élargit la plage acceptée.
_MIN_CHANNEL_ID = -1007852516352
_MIN_CHAT_ID = getattr(_pg_utils, "MIN_CHAT_ID", -2147483647)
_MAX_CHANNEL_ID = getattr(_pg_utils, "MAX_CHANNEL_ID", -1000000000000)
_MAX_USER_ID = getattr(_pg_utils, "MAX_USER_ID", 999999999999)


def _get_peer_type(peer_id: int) -> str:
    if peer_id < 0:
        if _MIN_CHAT_ID <= peer_id:
            return "chat"
        if _MIN_CHANNEL_ID <= peer_id < _MAX_CHANNEL_ID:
            return "channel"
    elif 0 < peer_id <= _MAX_USER_ID:
        return "user"
    raise ValueError(f"Peer id invalid: {peer_id}")


_pg_utils.get_peer_type = _get_peer_type
if hasattr(_pg_utils, "MIN_CHANNEL_ID"):
    _pg_utils.MIN_CHANNEL_ID = _MIN_CHANNEL_ID

bot = Client(
    "animecey_bot",
    api_id=settings.TELEGRAM_API_ID,
    api_hash=settings.TELEGRAM_API_HASH,
    bot_token=settings.TELEGRAM_BOT_TOKEN,
    # Telegram demande parfois d'attendre (FLOOD_WAIT) : on attend jusqu'à 15 min puis on réessaie
    # automatiquement, au lieu de faire échouer l'envoi.
    sleep_threshold=900,
    in_memory=True,  # No session file — avoids stale auth key issues on Koyeb restart
    # Texte brut : sinon Pyrogram prend « <id> » pour une balise HTML et l'efface du message.
    parse_mode=ParseMode.DISABLED,
)
