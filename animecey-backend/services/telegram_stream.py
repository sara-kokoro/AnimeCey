"""Generate streaming responses from Telegram file IDs via Pyrogram (MTProto).

Uses Pyrogram to stream files of any size (no 20MB Bot API limit).
The frontend hits ``/api/episodes/{id}/stream?server=servcey1`` which
returns a redirect or a streaming response.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def get_stream_url(file_id: str) -> str:
    """Return an internal streaming URL that the episodes router will handle.

    Instead of calling the Bot API getFile (limited to 20MB), we return
    a sentinel URL that tells the stream endpoint to use Pyrogram streaming.
    """
    # Return a marker that episodes.py will intercept to use Pyrogram streaming
    return f"pyrogram://{file_id}"
