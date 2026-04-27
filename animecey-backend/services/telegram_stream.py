"""Generate streaming URLs from Telegram file IDs.

Uses the Telegram Bot API ``getFile`` method to resolve a ``file_id``
to a temporary download URL.  The returned URL is served to the frontend
as ``servcey1`` — the word "Telegram" never appears in public API output.
"""

from __future__ import annotations

import httpx

from config import settings


async def get_stream_url(file_id: str) -> str:
    """Return a direct-download URL for a Telegram *file_id*."""
    token = settings.TELEGRAM_BOT_TOKEN
    api_url = f"https://api.telegram.org/bot{token}/getFile"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(api_url, params={"file_id": file_id})
        resp.raise_for_status()
        data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(data.get("description", "Telegram getFile failed"))
    file_path = data["result"]["file_path"]
    return f"https://api.telegram.org/file/bot{token}/{file_path}"
