"""Import automatique du catalogue TMCooper dans catalog_titles.

Fonctionnement :
  * au démarrage de l'API (après ~20 s), un premier import complet est lancé ;
  * ensuite, un nouveau cycle toutes les CATALOG_SYNC_INTERVAL_MIN minutes
    (30 par défaut) : les titres existants sont mis à jour, les nouveautés
    sont ajoutées ;
  * la recherche (routers/catalog.py) ne lit que la base de données.

Garde-fous :
  * si l'API TMCooper est injoignable ou ne renvoie rien, la base n'est pas
    touchée (aucune suppression, jamais) ;
  * si le catalogue TMCooper est en cours d'indexation (getAllAnime), on
    réessaie au bout de 5 minutes au lieu d'attendre le cycle complet ;
  * un seul import à la fois (verrou).

Variables d'environnement (toutes optionnelles) :
  CATALOG_SYNC_ENABLED       true / false          (défaut : true)
  CATALOG_SYNC_INTERVAL_MIN  minutes entre 2 cycles (défaut : 30)
  CATALOG_SEED_LIMIT         résultats demandés par recherche (défaut : 50)

Mettre ce fichier dans services/catalog_sync.py.
"""

from __future__ import annotations

import asyncio
import logging
import os
import string
from datetime import datetime, timezone

from sqlalchemy import func, literal_column, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from config import settings
from database import async_session, engine
from models_catalog import CatalogTitle
from services import tmcooper

logger = logging.getLogger(__name__)

SOURCE = "tmcooper"
ENABLED = os.getenv("CATALOG_SYNC_ENABLED", "true").lower() in ("true", "1", "yes")
INTERVAL_MIN = max(1, int(os.getenv("CATALOG_SYNC_INTERVAL_MIN", "30")))
SEED_LIMIT = max(1, int(os.getenv("CATALOG_SEED_LIMIT", "50")))
RETRY_NOT_READY_SEC = 300
BATCH = 200

# L'API n'expose qu'une recherche floue : on la balaie avec chaque lettre et
# chaque chiffre pour récupérer un maximum de titres.
_SEEDS = list(string.ascii_lowercase + string.digits)

# Noms de champs possibles dans les réponses de l'API (à ajuster si besoin).
_NAME_KEYS = ("name", "title", "nom", "api_name", "n", "anime")
_POSTER_KEYS = ("img", "image", "poster", "poster_url", "cover", "thumbnail")

_lock = asyncio.Lock()
_task: asyncio.Task | None = None


def _first(data: dict, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _normalize(item) -> dict | None:
    if isinstance(item, str):
        name, poster = item.strip(), None
    elif isinstance(item, dict):
        name, poster = _first(item, _NAME_KEYS), _first(item, _POSTER_KEYS)
    else:
        return None
    if not name:
        return None
    return {
        "external_id": name[:255],
        "title": name[:500],
        "poster_url": poster[:1000] if poster and poster.startswith(("http://", "https://")) else None,
    }


async def _collect() -> dict[str, dict]:
    """Balaye la recherche TMCooper et renvoie {external_id: ligne}."""
    found: dict[str, dict] = {}
    reached = False
    for i, seed in enumerate(_SEEDS):
        try:
            items = await tmcooper.search(seed, SEED_LIMIT)
        except tmcooper.TmcooperCatalogNotReady:
            raise
        except tmcooper.TmcooperError as exc:
            logger.warning("Catalogue: recherche '%s' en échec: %s", seed, exc)
            continue
        reached = True
        for item in items:
            row = _normalize(item)
            if row:
                found.setdefault(row["external_id"], row)
        if i < len(_SEEDS) - 1:
            await asyncio.sleep(settings.TMCOOPER_SYNC_DELAY_SEC)
    return found if reached else {}


async def _upsert(rows: list[dict]) -> int:
    """Insère ou met à jour les titres. Renvoie le nombre de nouveautés."""
    now = datetime.now(timezone.utc)
    new_count = 0
    async with async_session() as db:
        for start in range(0, len(rows), BATCH):
            chunk = [
                {**row, "type": "anime", "source": SOURCE, "last_synced_at": now}
                for row in rows[start : start + BATCH]
            ]
            stmt = pg_insert(CatalogTitle).values(chunk)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_catalog_titles_source_external_id",
                set_={
                    "title": stmt.excluded.title,
                    # on garde l'ancienne affiche si la nouvelle réponse n'en a pas
                    "poster_url": func.coalesce(stmt.excluded.poster_url, CatalogTitle.poster_url),
                    "last_synced_at": stmt.excluded.last_synced_at,
                    "updated_at": now,
                },
            ).returning(literal_column("(xmax = 0)"))
            result = await db.execute(stmt)
            new_count += sum(1 for (inserted,) in result.all() if inserted)
        await db.commit()
    return new_count


async def _ensure_indexes() -> None:
    """Index trigram pour que ILIKE '%q%' reste rapide (idempotent)."""
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_catalog_titles_title_trgm "
                "ON catalog_titles USING gin (title gin_trgm_ops)"
            ))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_catalog_titles_title_jp_trgm "
                "ON catalog_titles USING gin (title_jp gin_trgm_ops)"
            ))
    except Exception as exc:  # noqa: BLE001 — la recherche marche sans index, juste plus lentement
        logger.warning("Catalogue: index trigram non créés: %s", exc)


async def sync_catalog() -> dict:
    """Un cycle complet d'import."""
    if _lock.locked():
        return {"skipped": True, "reason": "un import est déjà en cours"}

    async with _lock:
        try:
            found = await _collect()
        except tmcooper.TmcooperCatalogNotReady:
            return {"ok": False, "not_ready": True, "error": "catalogue TMCooper en cours d'indexation"}

        if not found:
            return {"ok": False, "error": "aucun titre renvoyé, base inchangée"}

        new_count = await _upsert(list(found.values()))
        return {"ok": True, "total": len(found), "new": new_count}


async def _loop() -> None:
    await asyncio.sleep(20)  # laisse l'API (et TMCooper) finir de démarrer
    await _ensure_indexes()
    while True:
        wait = INTERVAL_MIN * 60
        try:
            summary = await sync_catalog()
            if summary.get("ok"):
                logger.info("Catalogue: %s titres vus, %s nouveaux.", summary["total"], summary["new"])
            elif summary.get("not_ready"):
                logger.warning("Catalogue: %s, nouvel essai dans 5 min.", summary["error"])
                wait = RETRY_NOT_READY_SEC
            elif not summary.get("skipped"):
                logger.warning("Catalogue: %s", summary.get("error"))
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — la boucle ne doit jamais mourir
            logger.exception("Catalogue: cycle interrompu par une erreur")
        await asyncio.sleep(wait)


def start_loop() -> None:
    global _task
    if not ENABLED:
        logger.info("Import du catalogue désactivé (CATALOG_SYNC_ENABLED=false).")
        return
    if _task is None or _task.done():
        _task = asyncio.create_task(_loop(), name="catalog-sync")
        logger.info("Import du catalogue démarré (toutes les %s min).", INTERVAL_MIN)


async def stop_loop() -> None:
    global _task
    if _task is not None and not _task.done():
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
    _task = None
