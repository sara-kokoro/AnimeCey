"""Service for interacting with byse.sx (formerly Filemoon) API.

API base: https://api.byse.sx/
Auth: query parameter ``key``.

Key endpoints used:
  - remote/add      → start a remote upload from a URL
  - remote/status   → poll progress of a remote upload
  - remote/remove   → cancel a pending remote upload
  - file/info       → retrieve metadata for an uploaded file
  - get/domain      → resolve current embed domain
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)

_EMBED_DOMAIN: Optional[str] = None


async def _get(endpoint: str, params: dict | None = None) -> dict:
    params = params or {}
    params["key"] = settings.BYSE_API_KEY
    url = f"{settings.BYSE_BASE_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
    if data.get("msg") == "Wrong Auth":
        raise RuntimeError("Clé API byse.sx invalide")
    return data


async def remote_upload(url: str, title: str | None = None) -> dict:
    """Start a remote upload on byse.sx and return the response including ``filecode``."""
    params: dict = {"url": url}
    if title:
        params["title"] = title
    data = await _get("remote/add", params)
    return data.get("result", data)


async def check_upload_status(file_code: str) -> dict:
    """Return progress / status of a remote upload job."""
    data = await _get("remote/status", {"file_code": file_code})
    return data.get("result", data)


async def wait_for_upload(file_code: str, poll_interval: float = 5.0, max_wait: float = 600.0) -> dict:
    """Poll ``remote/status`` until upload completes or times out."""
    elapsed = 0.0
    while elapsed < max_wait:
        status_data = await check_upload_status(file_code)
        st = str(status_data.get("status", "")).upper()
        if st in ("COMPLETED", "OK", ""):
            if not st:
                return status_data
            return status_data
        if "error" in st.lower() or status_data.get("error_msg"):
            return status_data
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
    return {"status": "TIMEOUT", "error_msg": "Upload timed out"}


async def remove_remote_upload(file_code: str) -> dict:
    """Cancel / remove a pending remote upload."""
    return await _get("remote/remove", {"file_code": file_code})


async def get_file_info(file_code: str) -> dict:
    """Retrieve metadata about an uploaded file."""
    data = await _get("file/info", {"file_code": file_code})
    return data.get("result", data)


async def _resolve_embed_domain() -> str:
    """Fetch the current embed domain from byse.sx API and cache it."""
    global _EMBED_DOMAIN
    if _EMBED_DOMAIN:
        return _EMBED_DOMAIN
    try:
        data = await _get("get/domain")
        domain = data.get("new_domain") or data.get("old_domain") or "byse.sx"
        _EMBED_DOMAIN = domain.rstrip("/")
        return _EMBED_DOMAIN
    except Exception:
        logger.warning("Impossible de résoudre le domaine embed byse.sx, utilisation du défaut")
        return "byse.sx"


async def get_embed_url(file_code: str) -> str:
    """Build the embed / player URL for a given file_code."""
    domain = await _resolve_embed_domain()
    if not domain.startswith("http"):
        domain = f"https://{domain}"
    return f"{domain}/e/{file_code}"


async def delete_file(file_code: str) -> bool:
    """Delete a file from byse.sx. Returns True on success."""
    try:
        data = await _get("file/delete", {"file_code": file_code})
        return data.get("msg") == "OK"
    except Exception:
        logger.exception("Erreur lors de la suppression du fichier byse.sx %s", file_code)
        return False
