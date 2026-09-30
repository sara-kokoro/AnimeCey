"""Synchronisation périodique des liens de lecture TMCooper -> base de données.

Principe (comme l'ancienne version) : les liens M3U8/MP4 expirent, donc toutes
les TMCOOPER_SYNC_INTERVAL_MIN minutes on rappelle l'API pour chaque source
suivie et on remplace le lien stocké.

Différence importante : on met à jour le lien SUR la ligne d'épisode existante
au lieu de supprimer/recréer l'épisode. Sinon les likes, commentaires et
historiques de lecture liés à l'épisode (ON DELETE CASCADE) seraient perdus à
chaque cycle.

Garde-fous :
  * si l'API est injoignable ou renvoie une liste vide, on ne touche à rien ;
  * un épisode qui n'est plus dans la réponse voit son lien effacé (jamais
    l'épisode lui-même) ;
  * un seul cycle de synchro à la fois (verrou) ;
  * pause entre deux animés pour ne pas déclencher Cloudflare côté source.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import async_session
from models import Anime, Episode, Folder, FolderType, LanguageEnum, TmcooperSource
from services import tmcooper

logger = logging.getLogger(__name__)

_sync_lock = asyncio.Lock()
_loop_task: asyncio.Task | None = None


def language_from_version(version: str) -> LanguageEnum:
    return LanguageEnum.VF if (version or "").lower().startswith("vf") else LanguageEnum.VOSTFR


async def _get_or_create_folder(
    db: AsyncSession, anime: Anime, language: LanguageEnum, season_number: int
) -> Folder:
    """Arborescence anime -> langue -> saison, comme celle créée par l'admin."""
    root = (
        await db.execute(
            select(Folder).where(
                Folder.anime_id == anime.id,
                Folder.folder_type == FolderType.anime,
                Folder.parent_id.is_(None),
            )
        )
    ).scalars().first()
    if root is None:
        root = Folder(anime_id=anime.id, name=anime.title, folder_type=FolderType.anime)
        db.add(root)
        await db.flush()

    lang_folder = (
        await db.execute(
            select(Folder).where(
                Folder.anime_id == anime.id,
                Folder.folder_type == FolderType.language,
                Folder.parent_id == root.id,
                Folder.language == language,
            )
        )
    ).scalars().first()
    if lang_folder is None:
        lang_folder = Folder(
            anime_id=anime.id,
            name=language.value,
            folder_type=FolderType.language,
            language=language,
            parent_id=root.id,
        )
        db.add(lang_folder)
        await db.flush()

    season_folder = (
        await db.execute(
            select(Folder).where(
                Folder.anime_id == anime.id,
                Folder.folder_type == FolderType.season,
                Folder.parent_id == lang_folder.id,
                Folder.season_number == season_number,
            )
        )
    ).scalars().first()
    if season_folder is None:
        season_folder = Folder(
            anime_id=anime.id,
            name=f"Saison {season_number}",
            folder_type=FolderType.season,
            language=language,
            season_number=season_number,
            parent_id=lang_folder.id,
        )
        db.add(season_folder)
        await db.flush()

    return season_folder


async def sync_source(source_id: int) -> dict:
    """Synchronise une source. À appeler sous verrou (voir sync_one / sync_all)."""
    async with async_session() as db:
        src = await db.get(TmcooperSource, source_id)
        if src is None:
            return {"source_id": source_id, "ok": False, "error": "source introuvable"}
        anime = await db.get(Anime, src.anime_id)
        if anime is None:
            return {"source_id": source_id, "ok": False, "error": "animé introuvable"}

        result: dict = {
            "source_id": src.id,
            "anime": anime.title,
            "season": src.season,
            "version": src.version,
            "ok": False,
        }
        now = datetime.now(timezone.utc)

        try:
            links = await tmcooper.episode_links(src.api_name, src.season, src.version)
        except tmcooper.TmcooperCatalogNotReady:
            src.last_sync_at, src.last_status = now, "catalogue TMCooper en cours d'indexation"
            await db.commit()
            result.update(error=src.last_status, catalog_not_ready=True)
            return result
        except tmcooper.TmcooperError as exc:
            src.last_sync_at, src.last_status = now, f"erreur API: {exc}"[:255]
            await db.commit()
            result["error"] = src.last_status
            return result

        if not links:
            # Liste vide = probablement une panne côté source : on garde les liens actuels.
            src.last_sync_at, src.last_status = now, "aucun lien renvoyé (liens conservés)"
            await db.commit()
            result["error"] = src.last_status
            return result

        language = language_from_version(src.version)
        season_number = tmcooper.parse_season_number(src.season)

        try:
            folder = await _get_or_create_folder(db, anime, language, season_number)

            rows = (
                await db.execute(
                    select(Episode).where(
                        Episode.anime_id == anime.id,
                        Episode.language == language,
                        Episode.season_number == season_number,
                    )
                )
            ).scalars().all()
            existing = {ep.episode_number: ep for ep in rows}

            created = updated = cleared = 0
            seen: set[int] = set()
            for link in links:
                number = link["episode"]
                seen.add(number)
                ep = existing.get(number)
                if ep is None:
                    db.add(
                        Episode(
                            anime_id=anime.id,
                            folder_id=folder.id,
                            episode_number=number,
                            language=language,
                            season_number=season_number,
                            stream_url=link["url"],
                            stream_type=link["type"],
                            links_refreshed_at=now,
                        )
                    )
                    created += 1
                else:
                    if ep.stream_url != link["url"]:
                        updated += 1
                    ep.stream_url = link["url"]
                    ep.stream_type = link["type"]
                    ep.links_refreshed_at = now

            for number, ep in existing.items():
                if number not in seen and ep.stream_url:
                    ep.stream_url = None
                    ep.stream_type = None
                    cleared += 1

            src.last_sync_at = now
            src.last_count = len(links)
            src.last_status = f"ok: {len(links)} liens ({created} nouveaux, {updated} mis à jour, {cleared} effacés)"
            await db.commit()
        except SQLAlchemyError as exc:
            await db.rollback()
            logger.exception("TMCooper: erreur base pour la source %s", source_id)
            # état de la source relu proprement après rollback
            async with async_session() as db2:
                src2 = await db2.get(TmcooperSource, source_id)
                if src2:
                    src2.last_sync_at = now
                    src2.last_status = f"erreur base: {type(exc).__name__}"[:255]
                    await db2.commit()
            result["error"] = f"erreur base: {type(exc).__name__}"
            return result

        result.update(ok=True, total=len(links), created=created, updated=updated, cleared=cleared)
        return result


async def sync_one(source_id: int) -> dict:
    async with _sync_lock:
        return await sync_source(source_id)


async def sync_all() -> dict:
    """Un cycle complet sur toutes les sources actives."""
    if _sync_lock.locked():
        return {"skipped": True, "reason": "une synchronisation est déjà en cours"}

    async with _sync_lock:
        async with async_session() as db:
            ids = (
                await db.execute(
                    select(TmcooperSource.id).where(TmcooperSource.is_active.is_(True)).order_by(TmcooperSource.id)
                )
            ).scalars().all()

        results: list[dict] = []
        for i, source_id in enumerate(ids):
            res = await sync_source(source_id)
            results.append(res)
            if res.get("catalog_not_ready"):
                break  # inutile d'insister tant que le catalogue n'est pas indexé
            if i < len(ids) - 1:
                await asyncio.sleep(settings.TMCOOPER_SYNC_DELAY_SEC)

        ok = sum(1 for r in results if r.get("ok"))
        return {"sources": len(ids), "ok": ok, "failed": len(results) - ok, "results": results}


# ── Boucle de fond ─────────────────────────────────────────────────────


async def _loop() -> None:
    await asyncio.sleep(15)  # laisse l'app (et l'API TMCooper) finir de démarrer
    interval = settings.TMCOOPER_SYNC_INTERVAL_MIN * 60
    while True:
        try:
            summary = await sync_all()
            if not summary.get("skipped"):
                logger.info(
                    "TMCooper sync: %s source(s), %s ok, %s en échec",
                    summary["sources"], summary["ok"], summary["failed"],
                )
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — la boucle ne doit jamais mourir
            logger.exception("TMCooper sync: cycle interrompu par une erreur")
        await asyncio.sleep(interval)


def start_loop() -> None:
    global _loop_task
    if not settings.TMCOOPER_SYNC_ENABLED:
        logger.info("TMCooper sync désactivée (TMCOOPER_SYNC_ENABLED=false).")
        return
    if _loop_task is None or _loop_task.done():
        _loop_task = asyncio.create_task(_loop(), name="tmcooper-sync")
        logger.info(
            "TMCooper sync démarrée (toutes les %s min, API: %s).",
            settings.TMCOOPER_SYNC_INTERVAL_MIN, settings.TMCOOPER_API_URL,
        )


async def stop_loop() -> None:
    global _loop_task
    if _loop_task is not None and not _loop_task.done():
        _loop_task.cancel()
        try:
            await _loop_task
        except asyncio.CancelledError:
            pass
    _loop_task = None
    await tmcooper.close()
