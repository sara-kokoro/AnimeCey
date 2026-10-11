"""Vignettes d'épisodes sur Cloudflare R2.

Sans R2, chaque vignette est relue dans le canal Telegram puis gardée en mémoire (400 images au maximum) :
une page d'animé peut donc déclencher des dizaines de téléchargements Telegram, de la RAM et du CPU.
Avec R2, la vignette est envoyée une seule fois ; ensuite le navigateur la prend directement sur
R2_PUBLIC_URL (servie et mise en cache par Cloudflare) sans toucher à ton serveur.

Tout est facultatif : sans les variables R2_*, ou si boto3 n'est pas installé, `enabled()` renvoie False
et le fonctionnement reste celui d'avant.
"""

from __future__ import annotations

import logging

from sqlalchemy import update

from database import async_session
from models import Episode

logger = logging.getLogger(__name__)

PREFIX = "thumbs/"
CACHE_CONTROL = "public, max-age=31536000, immutable"  # l'adresse change à chaque remplacement (version)


def _r2():
    """Le client R2, ou None s'il n'est pas utilisable (variables manquantes, boto3 absent)."""
    try:
        from services.r2 import r2  # import tardif : boto3 n'est requis que si R2 est utilisé
    except Exception:  # noqa: BLE001
        logger.warning("R2 indisponible (boto3 non installé ?)", exc_info=True)
        return None
    return r2 if (r2.is_configured and r2.public_base) else None


def enabled() -> bool:
    return _r2() is not None


def public_base() -> str:
    r = _r2()
    return r.public_base if r else ""


def thumb_key(episode_id: int, version: int | str) -> str:
    # version = id du message Telegram de la vignette : une vignette remplacée a donc une adresse neuve
    return f"{PREFIX}{int(episode_id)}-{version}.jpg"


def is_r2_url(url: str | None) -> bool:
    base = public_base()
    return bool(url and base and url.startswith(base + "/"))


async def store(episode_id: int, data: bytes, version: int | str) -> str | None:
    """Envoie la vignette sur R2. Renvoie son adresse publique, ou None (jamais d'exception)."""
    r = _r2()
    if r is None or not data:
        return None
    key = thumb_key(episode_id, version)
    try:
        await r.put_bytes(key, data, content_type="image/jpeg", cache_control=CACHE_CONTROL)
    except Exception:  # noqa: BLE001
        logger.warning("vignette %s non envoyée sur R2", key, exc_info=True)
        return None
    return r.public_url_for(key)


async def migrate_one(episode_id: int, data: bytes, version: int | str) -> bool:
    """Envoie la vignette sur R2 et pointe l'épisode dessus (Episode.thumbnail_url)."""
    url = await store(episode_id, data, version)
    if not url:
        return False
    try:
        async with async_session() as db:
            await db.execute(update(Episode).where(Episode.id == episode_id).values(thumbnail_url=url))
            await db.commit()
    except Exception:  # noqa: BLE001
        logger.warning("adresse R2 non enregistrée pour l'épisode %s", episode_id, exc_info=True)
        return False
    return True


async def delete(episode_id: int, version: int | str | None) -> None:
    """Supprime la vignette de R2 (au mieux : ne lève jamais d'erreur)."""
    r = _r2()
    if r is None or not version:
        return
    try:
        await r.delete(thumb_key(episode_id, version))
    except Exception:  # noqa: BLE001
        logger.info("vignette R2 de l'épisode %s non supprimée", episode_id, exc_info=True)
