"""Images des titres : logo, backdrop, affiches supplémentaires.

Trois rôles :

1. Rattrapage des ANCIENS titres (« lazy ») : au premier affichage d'une fiche (ou à sa première
   apparition dans une recherche), le logo et le backdrop TMDB sont lus UNE fois et enregistrés
   (colonne animes.images_synced). Aucun appel en masse : seuls les titres réellement consultés
   coûtent un appel TMDB, et les détails sont mis en cache 7 jours.
2. Hébergement des images envoyées à la main au bot (/poster, /setposter, /setlogo, /setbackdrop) :
   sur Cloudflare R2 si configuré, sinon dans le canal Telegram (servies par /api/animes/media/<id>).
3. Vignettes d'épisodes : le backdrop du titre remplace les vignettes tirées de Telegram.
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import secrets
import time

import httpx

from config import settings
from database import async_session
from models import Anime, AnimeType
from services import tmdb

logger = logging.getLogger(__name__)

TMDB_IMG = "https://image.tmdb.org/t/p"
MAX_UPLOAD = 8 * 1024 * 1024
CACHE_CONTROL = "public, max-age=31536000, immutable"  # l'adresse change à chaque remplacement
MEDIA_CAPTION = "image"  # début de la légende des images rangées dans le canal (voir /api/animes/media)


# ── Adresses ───────────────────────────────────────────────────────────


def backdrop_thumb(url: str | None) -> str | None:
    """Backdrop TMDB « original » (plusieurs Mo) -> 780 px ; les autres sources restent telles quelles."""
    return url.replace("/t/p/original/", "/t/p/w780/") if url else url


def episode_thumb(anime: Anime | None) -> str | None:
    """Image affichée pour les épisodes d'un titre : son backdrop (sinon son affiche)."""
    if anime is None:
        return None
    return backdrop_thumb(anime.banner_url) or anime.poster_url


def sniff(data: bytes) -> tuple[str, str]:
    """(type MIME, extension) d'une image PNG / JPEG / WebP. ValueError sinon."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png", "png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg", "jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", "webp"
    raise ValueError("Format d'image non reconnu (PNG, JPEG ou WebP).")


# ── Stockage des images envoyées à la main ─────────────────────────────


def _r2():
    from services import thumbs

    return thumbs._r2()  # noqa: SLF001


async def store_bytes(client, anime_id: int, kind: str, data: bytes) -> str:
    """Héberge l'image et renvoie son adresse publique. Lève ValueError(message) si impossible."""
    if len(data) > MAX_UPLOAD:
        raise ValueError(f"Image trop lourde ({len(data) // 2**20} Mo, 8 Mo maximum).")
    mime, ext = sniff(data)
    version = secrets.token_hex(4)

    r = _r2()
    if r is not None:
        key = f"images/{int(anime_id)}/{kind}-{version}.{ext}"
        try:
            await r.put_bytes(key, data, content_type=mime, cache_control=CACHE_CONTROL)
        except Exception as exc:  # noqa: BLE001
            logger.warning("image %s non envoyée sur R2", key, exc_info=True)
            raise ValueError(f"Envoi sur R2 impossible : {exc}") from exc
        return r.public_url_for(key)

    base = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
    if not base:
        raise ValueError(
            "Impossible d'héberger l'image : ni Cloudflare R2 ni PUBLIC_BASE_URL ne sont configurés. "
            "Tu peux donner une adresse https:// à la place du fichier."
        )
    bio = io.BytesIO(data)
    bio.name = f"{kind}-{anime_id}.{ext}"
    # En document (pas en photo) : Telegram ne recompresse pas, la transparence des logos PNG est gardée
    sent = await client.send_document(
        settings.TELEGRAM_CHANNEL_ID, bio, caption=f"{MEDIA_CAPTION} {kind} #{anime_id}", force_document=True
    )
    return f"{base}/api/animes/media/{sent.id}.{ext}"


async def delete_stored(url: str | None) -> None:
    """Supprime de R2 une image que nous avions hébergée (ne touche jamais à TMDB ni aux liens externes)."""
    r = _r2()
    if r is None or not url:
        return
    base = (r.public_base or "") + "/"
    if url.startswith(base + "images/"):
        try:
            await r.delete(url[len(base):])
        except Exception:  # noqa: BLE001
            logger.info("image R2 non supprimée : %s", url, exc_info=True)


def tmdb_url(path: str | None, size: str) -> str | None:
    return f"{TMDB_IMG}/{size}{path}" if path else None


# ── Rattrapage des anciens titres ──────────────────────────────────────

_inflight: set[int] = set()
_failed_until: dict[int, float] = {}
_tasks: set[asyncio.Task] = set()
_sem = asyncio.Semaphore(2)
RETRY_AFTER = 600  # secondes avant de retenter un titre dont TMDB n'a pas répondu


async def _fetch_details(anime: Anime, db) -> dict | None:
    """Détails TMDB du titre (via sa fiche, sinon recherche par titre pour les animés). None si introuvable."""
    if anime.tmdb_id:
        first = "movie" if anime.type == AnimeType.film else "tv"
        for media in (first, "tv" if first == "movie" else "movie"):
            try:
                return dict(await tmdb.get_details(int(anime.tmdb_id), media, db) or {})
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 404:
                    raise
        return None
    if anime.category == "anime":  # les films / séries live ont toujours leur fiche ; pas de recherche floue pour eux
        from services import catalog_meta

        details, _media = await catalog_meta._tmdb_lookup(anime.title, db)  # noqa: SLF001
        return details
    return None


async def sync_anime(anime_id: int, force: bool = False, keep_logo: bool = False) -> dict:
    """Lit le logo + backdrop TMDB d'un titre et les enregistre. Ne lève jamais d'exception.

    Ne remplace JAMAIS un backdrop déjà présent. Un logo déjà présent n'est remplacé qu'avec force=True
    (et jamais avec keep_logo=True). force=True relit aussi les titres déjà marqués « synchronisés ».
    Renvoie {"ok": bool, "logo": bool, "banner": bool}.
    """
    out = {"ok": False, "logo": False, "banner": False}
    try:
        async with async_session() as db:
            anime = await db.get(Anime, anime_id)
            if anime is None:
                return out
            if anime.images_synced and not force:
                out["ok"] = True
                return out
            details = await _fetch_details(anime, db)
            if details:
                if details.get("logo_path") and (not anime.logo_url or (force and not keep_logo)):
                    anime.logo_url = tmdb_url(details["logo_path"], "w500")
                    out["logo"] = True
                back = details.get("best_backdrop_path") or details.get("backdrop_path")
                if back and not anime.banner_url:
                    anime.banner_url = tmdb_url(back, "original")
                    out["banner"] = True
            anime.images_synced = True  # même sans résultat : TMDB a répondu, inutile de redemander
            await db.commit()
            out["ok"] = True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Images TMDB indisponibles pour l'animé %s : %s", anime_id, exc)
        _failed_until[anime_id] = time.monotonic() + RETRY_AFTER
    if out["logo"] or out["banner"]:
        from services import httpcache

        httpcache.clear()
    return out


def _can_try(anime_id: int) -> bool:
    return anime_id not in _inflight and _failed_until.get(anime_id, 0) < time.monotonic()


async def _run(anime_id: int) -> None:
    async with _sem:
        try:
            await sync_anime(anime_id)
        finally:
            _inflight.discard(anime_id)


def schedule(animes: list[Anime], limit: int = 5) -> None:
    """Lance en arrière-plan le rattrapage des titres pas encore synchronisés (au plus `limit` à la fois)."""
    todo = [a.id for a in animes if not a.images_synced and _can_try(a.id)][:limit]
    for anime_id in todo:
        _inflight.add(anime_id)
        task = asyncio.create_task(_run(anime_id))
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)


async def ensure_now(anime: Anime, timeout: float = 3.0) -> bool:
    """Rattrape le titre tout de suite (page de détail) ; True si la fiche a changé et doit être relue."""
    if anime.images_synced or not _can_try(anime.id):
        return False
    _inflight.add(anime.id)
    try:
        res = await asyncio.wait_for(sync_anime(anime.id), timeout)
    except asyncio.TimeoutError:
        _failed_until[anime.id] = time.monotonic() + 60  # TMDB lent : on ne bloque pas la page, on retentera dans une minute
        return False
    finally:
        _inflight.discard(anime.id)
    return bool(res.get("ok"))
