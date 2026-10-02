"""Import automatique du catalogue TMCooper dans catalog_titles.

Comment TMCooper fonctionne (vu dans son code) :
  * /api/getSerchAnime cherche dans un fichier local (AnimeInfo.json) et renvoie
    [] tant que ce fichier n'existe pas ;
  * ce fichier est créé par /api/getAllAnime (3 à 5 min) ;
  * /api/loadBaseAnimeData renvoie TOUT le catalogue d'un coup :
    [{"title", "link", "cover"}, ...].

Ce module :
  1. vérifie que TMCooper connaît le domaine Anime-Sama ;
  2. lit le catalogue complet (lance getAllAnime si le fichier n'existe pas) ;
  3. l'enregistre en base (ajoute les nouveautés, met à jour le reste) ;
  4. recommence toutes les CATALOG_SYNC_INTERVAL_MIN minutes (30 par défaut) ;
  5. relance un scraping complet toutes les CATALOG_RESCRAPE_HOURS heures
     (168 = 1 semaine par défaut) pour que les vraies nouveautés arrivent.

Économie de requêtes (important avec un proxy à quota, ex. Fixie) : le fichier
de TMCooper disparaît à chaque redémarrage du conteneur. Si la base contient
déjà le catalogue, on ne relance PAS de scraping pour autant ; la date du
dernier scraping est gardée en base (table catalog_meta).

Jamais de suppression en base : en cas de panne côté TMCooper, rien ne bouge.

Variables d'environnement (toutes optionnelles) :
  CATALOG_SYNC_ENABLED        true / false            (défaut : true)
  CATALOG_SYNC_INTERVAL_MIN   minutes entre 2 cycles   (défaut : 30)
  CATALOG_RESCRAPE_HOURS      heures entre 2 scrapings complets, 0 = jamais (défaut : 168)
  CATALOG_MIN_TITLES          nb de titres en base au-delà duquel on considère le
                              catalogue déjà rempli (défaut : 50)

Mettre ce fichier dans services/catalog_sync.py.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from sqlalchemy import func, literal_column, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from database import async_session, engine
from models_catalog import CatalogTitle
from services import tmcooper

logger = logging.getLogger(__name__)

SOURCE = "tmcooper"
ENABLED = os.getenv("CATALOG_SYNC_ENABLED", "true").lower() in ("true", "1", "yes")
INTERVAL_MIN = max(1, int(os.getenv("CATALOG_SYNC_INTERVAL_MIN", "30")))
RESCRAPE_HOURS = max(0.0, float(os.getenv("CATALOG_RESCRAPE_HOURS", "168")))
MIN_TITLES = max(1, int(os.getenv("CATALOG_MIN_TITLES", "50")))
RETRY_SEC = 300
INDEX_TIMEOUT = 1800.0
BATCH = 200

_lock = asyncio.Lock()
_task: asyncio.Task | None = None


# ── Appels à TMCooper ──────────────────────────────────────────────────


async def _api(path: str, params: dict | None = None, timeout: float = 60.0):
    """GET sur l'API TMCooper, renvoie le JSON décodé."""
    client = tmcooper._get_client()
    try:
        resp = await client.get(path, params=params, timeout=timeout)
    except httpx.HTTPError as exc:
        raise tmcooper.TmcooperError(f"injoignable ({path}): {exc!r}")
    try:
        return resp.json()
    except ValueError:
        raise tmcooper.TmcooperError(
            f"réponse non JSON (HTTP {resp.status_code}) sur {path}: {resp.text[:200]!r}"
        )


async def _anime_sama_domain() -> str | None:
    data = await _api("/api/getAnimeSamaURL")
    url = data.get("url") if isinstance(data, dict) else None
    return url or None


async def _load_catalog() -> list | None:
    """Catalogue complet, ou None si le fichier local de TMCooper n'existe pas encore."""
    data = await _api("/api/loadBaseAnimeData", timeout=INDEX_TIMEOUT)
    return data if isinstance(data, list) else None


async def _scrape(reset: bool) -> None:
    """Lance getAllAnime (plusieurs minutes). Lève TmcooperError si ça échoue."""
    logger.info("Catalogue: scraping complet d'Anime-Sama demandé à TMCooper (3 à 5 min)...")
    result = await _api("/api/getAllAnime", {"r": "True"} if reset else None, timeout=INDEX_TIMEOUT)
    if isinstance(result, str) and (result.lower().startswith("recup") or "existant" in result.lower()):
        await _mark_scrape()
        logger.info("Catalogue: scraping terminé (%s).", result)
        return
    # TMCooper renvoie le code HTTP (ex. 403) si Anime-Sama refuse la requête.
    raise tmcooper.TmcooperError(f"scraping refusé par la source: {result!r}")


# ── Mémoire du dernier scraping (survit aux redémarrages) ──────────────


async def _ensure_meta_table() -> None:
    async with engine.begin() as conn:
        await conn.execute(text(
            "CREATE TABLE IF NOT EXISTS catalog_meta ("
            "key VARCHAR(64) PRIMARY KEY, value TEXT, "
            "updated_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        ))


async def _last_scrape_age() -> float | None:
    """Secondes écoulées depuis le dernier scraping, ou None s'il n'y en a jamais eu."""
    async with async_session() as db:
        age = (await db.execute(text(
            "SELECT EXTRACT(EPOCH FROM (now() - updated_at)) "
            "FROM catalog_meta WHERE key = 'last_scrape'"
        ))).scalar()
    return float(age) if age is not None else None


async def _mark_scrape() -> None:
    async with async_session() as db:
        await db.execute(text(
            "INSERT INTO catalog_meta (key, value, updated_at) VALUES ('last_scrape', 'ok', now()) "
            "ON CONFLICT (key) DO UPDATE SET updated_at = now()"
        ))
        await db.commit()


async def _db_count() -> int:
    async with async_session() as db:
        return (await db.execute(
            select(func.count()).select_from(CatalogTitle).where(CatalogTitle.source == SOURCE)
        )).scalar() or 0


# ── Normalisation et écriture en base ──────────────────────────────────


def _slug(link: str | None, title: str) -> str:
    """Identifiant stable : dernier segment de l'URL (ne change pas si le domaine change)."""
    path = urlparse(link or "").path.strip("/")
    slug = path.split("/")[-1] if path else ""
    return (slug or title)[:255]


def _normalize(item) -> dict | None:
    if not isinstance(item, dict):
        return None
    title = (item.get("title") or "").strip()
    if not title:
        return None
    cover = item.get("cover")
    poster = cover[:1000] if isinstance(cover, str) and cover.startswith(("http://", "https://")) else None
    return {"external_id": _slug(item.get("link"), title), "title": title[:500], "poster_url": poster}


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


# ── Cycle de synchronisation ───────────────────────────────────────────


async def sync_catalog() -> dict:
    """Un cycle complet. Ne lève jamais d'exception TMCooper : renvoie un résumé."""
    if _lock.locked():
        return {"skipped": True, "reason": "un import est déjà en cours"}

    async with _lock:
        try:
            domain = await _anime_sama_domain()
            if not domain:
                return {
                    "ok": False,
                    "error": "TMCooper n'a pas trouvé le domaine Anime-Sama (BASE_URL vide). "
                             "Voir les logs [launcher] ou définir ANIMESAMA_URL.",
                }

            items = await _load_catalog()
            age = await _last_scrape_age()
            due = RESCRAPE_HOURS > 0 and age is not None and age >= RESCRAPE_HOURS * 3600

            if items is None:
                # Fichier TMCooper absent (premier lancement ou redémarrage du conteneur).
                in_db = await _db_count()
                if in_db >= MIN_TITLES and not due:
                    if age is None:
                        await _mark_scrape()  # base déjà remplie avant l'ajout de catalog_meta
                    logger.info(
                        "Catalogue: fichier TMCooper absent mais %s titres déjà en base : "
                        "scraping évité (économie de requêtes).", in_db,
                    )
                    return {"ok": True, "total": in_db, "new": 0, "domain": domain}
                await _scrape(reset=False)
                items = await _load_catalog()
            elif age is None:
                await _mark_scrape()  # fichier présent, âge du scraping inconnu
            elif due:
                try:
                    await _scrape(reset=True)
                    items = await _load_catalog() or items
                except tmcooper.TmcooperError as exc:
                    # on garde l'ancien fichier, il reste valable
                    logger.warning("Catalogue: nouveau scraping impossible (%s), ancien fichier conservé.", exc)
        except tmcooper.TmcooperError as exc:
            return {"ok": False, "error": str(exc)}

        if not items:
            return {"ok": False, "error": "catalogue TMCooper vide, base inchangée"}

        logger.info("Catalogue: %s titres reçus de TMCooper, exemple: %.300s", len(items), repr(items[0]))
        rows: dict[str, dict] = {}
        for item in items:
            row = _normalize(item)
            if row:
                rows.setdefault(row["external_id"], row)
        if not rows:
            return {"ok": False, "error": "aucun titre exploitable dans la réponse, base inchangée"}

        new_count = await _upsert(list(rows.values()))
        return {"ok": True, "total": len(rows), "new": new_count, "domain": domain}


async def _loop() -> None:
    await asyncio.sleep(20)  # laisse l'API (et TMCooper) finir de démarrer
    try:
        await _ensure_meta_table()
    except Exception:  # noqa: BLE001
        logger.exception("Catalogue: table catalog_meta non créée")
    await _ensure_indexes()
    while True:
        wait = INTERVAL_MIN * 60
        try:
            summary = await sync_catalog()
            if summary.get("ok"):
                logger.info("Catalogue: %s titres en base, %s nouveaux.", summary["total"], summary["new"])
            elif not summary.get("skipped"):
                logger.warning("Catalogue: %s Nouvel essai dans 5 min.", summary.get("error"))
                wait = min(wait, RETRY_SEC)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — la boucle ne doit jamais mourir
            logger.exception("Catalogue: cycle interrompu par une erreur")
            wait = min(wait, RETRY_SEC)
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
