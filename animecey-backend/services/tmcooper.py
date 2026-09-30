"""Client asynchrone pour AnimeSamaApi (TMCooper).

L'API est un service Flask séparé qui scrape Anime-Sama et résout les liens
Sibnet / Vidmoly / SmoothPre / SendVid en MP4 ou M3U8. Ce module ne fait que
l'appeler en HTTP ; il ne contient aucune logique de scraping.

Routes utilisées (cf. README de TMCooper/AnimeSamaApi) :
  GET /api/getSerchAnime?q=&l=       recherche floue (sic : "Serch")
  GET /api/getInfoAnime?q=           saisons disponibles
  GET /api/getAnimeLink?n=&s=&v=     [{"episode": int, "url": str}, ...]
  GET /api/getAnimeSamaURL           domaine actif
  GET /api/getAllAnime               (ré)indexation du catalogue (3-5 min)
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import httpx

from config import settings

logger = logging.getLogger(__name__)


class TmcooperError(Exception):
    """L'API TMCooper est injoignable ou a répondu par une erreur."""


class TmcooperCatalogNotReady(TmcooperError):
    """Le catalogue local de l'API n'est pas encore initialisé (getAllAnime)."""


_client: httpx.AsyncClient | None = None
_indexing_task: asyncio.Task | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            base_url=settings.TMCOOPER_API_URL,
            timeout=httpx.Timeout(settings.TMCOOPER_TIMEOUT, connect=10.0),
            follow_redirects=True,
        )
    return _client


async def close() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


async def _get(path: str, params: dict[str, Any] | None = None, retries: int = 2) -> Any:
    """GET avec réessais sur les erreurs réseau / 5xx. Renvoie le JSON décodé."""
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = await _get_client().get(path, params=params)
        except httpx.HTTPError as exc:
            last_exc = exc
        else:
            if resp.status_code < 500:
                return _decode(resp)
            last_exc = TmcooperError(f"HTTP {resp.status_code} sur {path}")
        if attempt < retries:
            await asyncio.sleep(1.5 * (attempt + 1))
    raise TmcooperError(f"TMCooper injoignable ({path}): {last_exc}")


def _decode(resp: httpx.Response) -> Any:
    try:
        data = resp.json()
    except ValueError:
        raise TmcooperError(f"Réponse non JSON (HTTP {resp.status_code})")

    # Catalogue local absent : l'API répond par une chaîne qui cite getAllAnime.
    if isinstance(data, str) and "getAllAnime" in data:
        _kick_off_indexing()
        raise TmcooperCatalogNotReady(data)
    if resp.status_code >= 400:
        detail = data.get("error") if isinstance(data, dict) else data
        raise TmcooperError(f"HTTP {resp.status_code}: {detail}")
    if isinstance(data, dict) and "error" in data and len(data) == 1:
        raise TmcooperError(str(data["error"]))
    return data


def _kick_off_indexing() -> None:
    """Lance getAllAnime en tâche de fond (une seule fois à la fois)."""
    global _indexing_task
    if _indexing_task is not None and not _indexing_task.done():
        return

    async def _run() -> None:
        logger.warning("TMCooper: catalogue absent, lancement de getAllAnime (plusieurs minutes)...")
        try:
            async with httpx.AsyncClient(base_url=settings.TMCOOPER_API_URL, timeout=900.0) as c:
                await c.get("/api/getAllAnime")
            logger.info("TMCooper: catalogue indexé.")
        except Exception as exc:  # noqa: BLE001
            logger.error("TMCooper: échec de l'indexation du catalogue: %s", exc)

    _indexing_task = asyncio.create_task(_run())


# ── Routes de l'API ────────────────────────────────────────────────────


async def search(query: str, limit: int = 5) -> list[dict]:
    data = await _get("/api/getSerchAnime", {"q": query, "l": limit})
    return data if isinstance(data, list) else []


async def seasons(name: str) -> list[dict]:
    data = await _get("/api/getInfoAnime", {"q": name})
    return data if isinstance(data, list) else []


async def active_domain() -> str | None:
    data = await _get("/api/getAnimeSamaURL")
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0].get("url")
    return None


async def episode_links(name: str, season: str = "saison1", version: str = "vostfr") -> list[dict]:
    """Liste normalisée [{"episode": int, "url": str, "type": str}, ...]."""
    # getAnimeLink résout chaque épisode chez son hébergeur : ça peut prendre plusieurs
    # minutes. Pas de réessai ici, la synchro suivante (30 min) fait office de réessai.
    data = await _get("/api/getAnimeLink", {"n": name, "s": season, "v": version}, retries=0)
    if not isinstance(data, list):
        return []

    links: dict[int, dict] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        try:
            number = int(item.get("episode"))
        except (TypeError, ValueError):
            continue
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            continue
        # En cas de doublon sur un même épisode, on garde le premier lien valide.
        links.setdefault(number, {"episode": number, "url": url, "type": detect_type(url)})
    return [links[n] for n in sorted(links)]


_M3U8_RE = re.compile(r"\.m3u8(\?|$|#)", re.IGNORECASE)
_MP4_RE = re.compile(r"\.mp4(\?|$|#)", re.IGNORECASE)


def detect_type(url: str) -> str:
    if _M3U8_RE.search(url) or "m3u8" in url.lower():
        return "m3u8"
    if _MP4_RE.search(url):
        return "mp4"
    return "embed"


def parse_season_number(season: str) -> int:
    """'saison2' -> 2 ; 'film', 'oav' (sans numéro) -> 1."""
    m = re.search(r"(\d+)", season or "")
    return int(m.group(1)) if m else 1
