"""Épisodes + TOUS leurs serveurs, depuis TMCooper (/api/getAnimeServers).

Pour les animés ouverts depuis le catalogue (table anime_seasons) :
  * numéros d'épisodes à partir de 1 (TMCooper compte à partir de 0) ;
  * tous les lecteurs d'Anime-Sama (Sibnet, Vidmoly, Sendvid...) sont gardés,
    pas seulement le premier qui répond ;
  * les liens sont des pages "embed" stables : pas besoin de les rafraîchir
    toutes les 30 min. Une saison n'est synchronisée qu'à la demande (1re
    ouverture), puis seule la dernière saison d'un animé en cours est
    rafraîchie (toutes les CATALOG_EPISODES_REFRESH_HOURS heures, 12 par défaut).
    C'est ce qui protège le quota du proxy.

Mettre ce fichier dans services/catalog_episodes.py.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError

from database import async_session
from models import Anime, AnimeStatus, Episode, TmcooperSource
from models_catalog import AnimeSeason, EpisodeServer
from services import tmcooper

logger = logging.getLogger(__name__)

REFRESH_HOURS = max(1.0, float(os.getenv("CATALOG_EPISODES_REFRESH_HOURS", "12")))

# (morceau du nom d'hôte, libellé affiché)
_HOSTS = [
    ("sibnet", "Sibnet"),
    ("vidmoly", "Vidmoly"),
    ("sendvid", "Sendvid"),
    ("vidhide", "Vidhide"),
    ("streamwish", "Streamwish"),
    ("smoothpre", "Smoothpre"),
    ("filemoon", "Filemoon"),
    ("byse", "Byse"),
    ("embed4me", "Embed4me"),
    ("oneupload", "Oneupload"),
    ("ansembed", "Ansembed"),
    ("vidoza", "Vidoza"),
    ("voe", "Voe"),
    ("dood", "Doodstream"),
    ("mixdrop", "Mixdrop"),
    ("vk.com", "VK"),
    ("anime-sama", "Anime-Sama"),
]


def server_label(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    for part, label in _HOSTS:
        if part in host:
            return label
    pieces = [p for p in host.split(".") if p]
    return (pieces[-2] if len(pieces) >= 2 else host or "Serveur").title()


def _priority(url: str) -> int:
    host = (urlparse(url).hostname or "").lower()
    if "sibnet" in host:
        return 0
    if any(s in host for s in ("vidmoly", "streamwish", "vidhide", "smoothpre", "ansembed")):
        return 1
    if any(s in host for s in ("sendvid", "embed4me", "oneupload")):
        return 2
    return 3


def _lecteur_index(name: str) -> int:
    digits = re.sub(r"[^0-9]", "", name or "")
    return int(digits) if digits else 99


def build_episode_servers(servers: list[dict]) -> dict[int, list[dict]]:
    """[{"name": "eps1", "urls": [...]}, ...] -> {numéro d'épisode (à partir de 1): [serveurs]}."""
    clean: list[dict] = []
    for srv in servers or []:
        if isinstance(srv, dict) and isinstance(srv.get("urls"), list):
            clean.append({"name": str(srv.get("name") or ""), "urls": srv["urls"]})

    def first_url(srv: dict) -> str:
        return next((u for u in srv["urls"] if isinstance(u, str) and u.startswith("http")), "")

    ordered = sorted(clean, key=lambda s: (_priority(first_url(s)), _lecteur_index(s["name"])))
    total = max((len(s["urls"]) for s in clean), default=0)

    result: dict[int, list[dict]] = {}
    for idx in range(total):
        entries: list[dict] = []
        seen: set[str] = set()
        counts: dict[str, int] = {}
        for srv in ordered:
            if idx >= len(srv["urls"]):
                continue
            url = srv["urls"][idx]
            url = url.strip() if isinstance(url, str) else ""
            if not url.startswith(("http://", "https://")) or url in seen:
                continue
            seen.add(url)
            label = server_label(url)
            counts[label] = counts.get(label, 0) + 1
            if counts[label] > 1:
                label = f"{label} {counts[label]}"
            entries.append({"label": label, "url": url, "type": tmcooper.detect_type(url)})
        if entries:
            result[idx + 1] = entries  # TMCooper numérote à partir de 0, nous à partir de 1
    return result


async def fetch_servers(name: str, season: str, version: str) -> list[dict]:
    data = await tmcooper._get(
        "/api/getAnimeServers", {"n": name, "s": season, "v": version}, retries=0
    )
    servers = data.get("servers") if isinstance(data, dict) else None
    return servers if isinstance(servers, list) else []


# ── Quelles sources gère ce module ? ───────────────────────────────────


async def is_managed(source_id: int) -> bool:
    async with async_session() as db:
        src = await db.get(TmcooperSource, source_id)
        if src is None:
            return False
        row = (
            await db.execute(
                select(AnimeSeason.id).where(
                    AnimeSeason.anime_id == src.anime_id, AnimeSeason.api_season == src.season
                )
            )
        ).first()
        return row is not None


_SERIES_RE = re.compile(r"^(saison|saga|season|arc|partie)")


async def _is_refresh_candidate(db, src: TmcooperSource, anime: Anime) -> bool:
    """Seule la dernière saison d'un animé en cours est rafraîchie automatiquement."""
    if anime.status != AnimeStatus.ongoing:
        return False
    rows = (
        await db.execute(
            select(AnimeSeason.season_number, AnimeSeason.api_season).where(AnimeSeason.anime_id == anime.id)
        )
    ).all()
    if not rows:
        return False
    main = [r for r in rows if _SERIES_RE.match(r.api_season)] or rows
    latest = max(main, key=lambda r: r.season_number)
    return latest.api_season == src.season


# ── Synchronisation ────────────────────────────────────────────────────


async def sync_source(source_id: int, force: bool = False) -> dict:
    """Synchronise une source gérée. À appeler sous le verrou de tmcooper_sync."""
    from services.tmcooper_sync import _get_or_create_folder, language_from_version

    async with async_session() as db:
        src = await db.get(TmcooperSource, source_id)
        if src is None:
            return {"source_id": source_id, "ok": False, "error": "source introuvable"}
        anime = await db.get(Anime, src.anime_id)
        season = (
            await db.execute(
                select(AnimeSeason).where(
                    AnimeSeason.anime_id == src.anime_id, AnimeSeason.api_season == src.season
                )
            )
        ).scalars().first()
        if anime is None or season is None:
            return {"source_id": source_id, "ok": False, "error": "animé ou saison introuvable"}

        now = datetime.now(timezone.utc)
        result = {"source_id": src.id, "anime": anime.title, "season": src.season, "version": src.version, "ok": False}

        if not force and src.last_sync_at is not None:
            last = src.last_sync_at if src.last_sync_at.tzinfo else src.last_sync_at.replace(tzinfo=timezone.utc)
            fresh = now - last < timedelta(hours=REFRESH_HOURS)
            if fresh or not await _is_refresh_candidate(db, src, anime):
                result.update(ok=True, skipped=True)
                return result

        try:
            servers = await fetch_servers(src.api_name, src.season, src.version)
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

        per_episode = build_episode_servers(servers)
        if not per_episode:
            # pas de VF pour cet animé, ou panne côté source : on garde ce qui existe
            src.last_sync_at, src.last_count = now, 0
            src.last_status = "aucun serveur renvoyé (données conservées)"
            await db.commit()
            result["error"] = src.last_status
            return result

        language = language_from_version(src.version)
        try:
            folder = await _get_or_create_folder(db, anime, language, season.season_number)
            if season.label and folder.name != season.label:
                folder.name = season.label[:255]

            rows = (
                await db.execute(
                    select(Episode).where(
                        Episode.anime_id == anime.id,
                        Episode.language == language,
                        Episode.season_number == season.season_number,
                    )
                )
            ).scalars().all()
            existing = {ep.episode_number: ep for ep in rows}

            created = 0
            episodes: dict[int, Episode] = {}
            for number, entries in per_episode.items():
                ep = existing.get(number)
                first = entries[0]
                if ep is None:
                    ep = Episode(
                        anime_id=anime.id,
                        folder_id=folder.id,
                        episode_number=number,
                        language=language,
                        season_number=season.season_number,
                    )
                    db.add(ep)
                    created += 1
                ep.stream_url = first["url"]
                ep.stream_type = first["type"]
                ep.links_refreshed_at = now
                episodes[number] = ep
            await db.flush()  # donne un id aux nouveaux épisodes

            ids = [ep.id for ep in episodes.values()]
            await db.execute(delete(EpisodeServer).where(EpisodeServer.episode_id.in_(ids)))
            for number, entries in per_episode.items():
                for position, entry in enumerate(entries, start=1):
                    db.add(
                        EpisodeServer(
                            episode_id=episodes[number].id,
                            position=position,
                            label=entry["label"][:80],
                            url=entry["url"],
                            type=entry["type"],
                        )
                    )

            avg = sum(len(v) for v in per_episode.values()) / len(per_episode)
            src.last_sync_at = now
            src.last_count = len(per_episode)
            src.last_status = f"ok: {len(per_episode)} épisodes, {avg:.1f} serveurs en moyenne ({created} nouveaux)"
            await db.commit()
        except SQLAlchemyError as exc:
            await db.rollback()
            logger.exception("Catalogue: erreur base pour la source %s", source_id)
            async with async_session() as db2:
                src2 = await db2.get(TmcooperSource, source_id)
                if src2:
                    src2.last_sync_at = now
                    src2.last_status = f"erreur base: {type(exc).__name__}"[:255]
                    await db2.commit()
            result["error"] = f"erreur base: {type(exc).__name__}"
            return result

        result.update(ok=True, total=len(per_episode), created=created)
        return result
