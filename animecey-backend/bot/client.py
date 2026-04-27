"""Pyrogram bot client singleton.

Initialised with credentials from ``config.settings``.  The ``bot``
instance is started/stopped inside the FastAPI lifespan in ``main.py``.
"""

from __future__ import annotations

from pyrogram import Client

from config import settings

bot = Client(
    "animecey_bot",
    api_id=settings.TELEGRAM_API_ID,
    api_hash=settings.TELEGRAM_API_HASH,
    bot_token=settings.TELEGRAM_BOT_TOKEN,
)
