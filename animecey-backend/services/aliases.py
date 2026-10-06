"""Autres noms des animés (pour que « Shingeki no Kyojin » trouve « Attack des Titans »).

Sources, de la plus fiable à la moins fiable :
  1. l'index du catalogue Anime-Sama (titre + titre japonais du même titre) ;
  2. AniList (romaji, anglais, japonais, synonymes) ;
  3. les noms ajoutés à la main avec la commande /alias du bot.

Un animé qui a au moins un alias en base est considéré comme « fait » : la boucle de rattrapage
ne le retraite pas. En cas d'erreur réseau, rien n'est écrit et ce sera retenté au prochain démarrage.
"""

from __future__ import annotations

import asyncio
import logging
from difflib import SequenceMatcher

import httpx
from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from database import async_session
from models import Anime
from models_catalog import AnimeAlias, CatalogTitle
from services import search_fuzzy
from services.search_fuzzy import norm

logger = logging.getLogger(__name__)

ANILIST_URL = "https://graphql.anilist.co"
_QUERY = """
query ($id: Int, $search: String) {
  Media(id: $id, search: $search, type: ANIME) {
    id
    title { romaji english native }
    synonyms
  }
}
"""

_background: set[asyncio.Task] = set()


async def add_aliases(anime_id: int, names: list[str]) -> int:
    """Ajoute des noms (sans doublon, sans accents/majuscules). Renvoie le nombre ajouté."""
    rows, seen = [], set()
    for name in names:
        name = (name or "").strip()[:500]
        n = norm(name)
        if len(n) < 2 or n in seen:
            continue
        seen.add(n)
        rows.append({"anime_id": anime_id, "alias": name, "alias_norm": n[:500]})
    if not rows:
        return 0
    async with async_session() as db:
        res = await db.execute(
            pg_insert(AnimeAlias)
            .values(rows)
            .on_conflict_do_nothing(constraint="uq_anime_aliases_anime_norm")
            .returning(AnimeAlias.id)
        )
        added = len(res.all())
        await db.commit()
    search_fuzzy.invalidate()
    return added


async def remove_alias(anime_id: int, name: str) -> int:
    n = norm(name)
    async with async_session() as db:
        res = await db.execute(
            delete(AnimeAlias).where(AnimeAlias.anime_id == anime_id, AnimeAlias.alias_norm == n).returning(AnimeAlias.id)
        )
        removed = len(res.all())
        await db.commit()
    search_fuzzy.invalidate()
    return removed


async def list_aliases(anime_id: int) -> list[str]:
    async with async_session() as db:
        rows = (
            await db.execute(select(AnimeAlias.alias).where(AnimeAlias.anime_id == anime_id).order_by(AnimeAlias.id))
        ).scalars().all()
    return list(rows)


async def _anilist_names(client: httpx.AsyncClient, anime: Anime) -> list[str]:
    """Noms AniList ; lève une exception si le réseau échoue (=> on réessaiera plus tard)."""
    variables: dict = {"id": anime.anilist_id} if anime.anilist_id else {"search": anime.title}
    resp = await client.post(ANILIST_URL, json={"query": _QUERY, "variables": variables})
    if resp.status_code == 404:
        return []  # aucun résultat
    if resp.status_code == 429:
        raise RuntimeError("AniList : trop de requêtes")
    resp.raise_for_status()
    media = (resp.json().get("data") or {}).get("Media")
    if not media:
        return []
    t = media.get("title") or {}
    names = [t.get("romaji"), t.get("english"), t.get("native"), *(media.get("synonyms") or [])]
    names = [n for n in names if n]
    if not anime.anilist_id:
        # recherche par titre : on ne garde le résultat que s'il ressemble vraiment à l'animé
        mine = {norm(anime.title), norm(anime.title_jp)} - {""}
        theirs = {norm(n) for n in names}
        if not any(SequenceMatcher(None, a, b).ratio() >= 0.6 for a in mine for b in theirs):
            return []
    return names


async def sync_aliases(anime_id: int, use_anilist: bool = True) -> int:
    """Rassemble les autres noms d'un animé. Renvoie le nombre de nouveaux noms."""
    async with async_session() as db:
        anime = await db.get(Anime, anime_id)
        if anime is None:
            return 0
        names: list[str] = [anime.title, anime.title_jp or ""]

        cond = [func.lower(CatalogTitle.title) == anime.title.lower()]
        if anime.anilist_id:
            cond.append(CatalogTitle.anilist_id == anime.anilist_id)
        if anime.tmdb_id:
            cond.append(CatalogTitle.tmdb_id == anime.tmdb_id)
        for title, title_jp in (
            await db.execute(select(CatalogTitle.title, CatalogTitle.title_jp).where(or_(*cond)).limit(10))
        ).all():
            names += [title, title_jp or ""]

    if use_anilist:
        async with httpx.AsyncClient(timeout=15) as client:
            names += await _anilist_names(client, anime)  # peut lever : alors rien n'est écrit
    return await add_aliases(anime_id, names)


def schedule_sync(anime_id: int) -> None:
    """Lance la récupération des noms en arrière-plan (sans bloquer la requête)."""

    async def _run() -> None:
        try:
            await sync_aliases(anime_id)
        except Exception:  # noqa: BLE001
            logger.warning("Alias : récupération impossible pour l'animé %s (réessai au prochain démarrage)", anime_id, exc_info=True)

    task = asyncio.create_task(_run())
    _background.add(task)
    task.add_done_callback(_background.discard)


async def backfill_loop() -> None:
    """Au démarrage : renseigne les autres noms des animés qui n'en ont pas encore."""
    await asyncio.sleep(20)  # laisse le serveur démarrer
    try:
        async with async_session() as db:
            todo = (
                await db.execute(
                    select(Anime.id).where(~Anime.id.in_(select(AnimeAlias.anime_id).distinct())).order_by(Anime.id)
                )
            ).scalars().all()
        if todo:
            logger.info("Alias : %s animé(s) à renseigner", len(todo))
        for aid in todo:
            try:
                await sync_aliases(aid)
            except Exception:  # noqa: BLE001
                logger.warning("Alias : animé %s ignoré pour l'instant", aid, exc_info=True)
            await asyncio.sleep(2)  # AniList limite le nombre de requêtes
    except asyncio.CancelledError:
        raise
    except Exception:  # noqa: BLE001
        logger.exception("Alias : rattrapage interrompu")


def start_backfill() -> None:
    task = asyncio.create_task(backfill_loop(), name="alias-backfill")
    _background.add(task)
    task.add_done_callback(_background.discard)
