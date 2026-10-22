"""Distribution / équipe et titres similaires d'une fiche.

  • animés (category « anime »)  → AniList : personnages + doubleurs japonais, staff, recommandations
  • films et séries (« live »)   → TMDB    : distribution, équipe, recommandations

Marche aussi pour les anciennes fiches : si l'id AniList / TMDB manque, on le cherche une fois
par le titre et on l'enregistre (sans jamais écraser un id déjà pris par une autre fiche).
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Anime
from services import anilist, catalog_meta, tmdb

logger = logging.getLogger(__name__)


async def _resolve_anilist_id(db: AsyncSession, anime: Anime) -> int | None:
    if anime.anilist_id:
        return anime.anilist_id
    for name in (anime.title_jp, anime.title):
        if not name:
            continue
        try:
            al = await catalog_meta._anilist_lookup(name, db)  # noqa: SLF001
        except Exception:  # noqa: BLE001
            al = None
        if al and al.get("id"):
            taken = (await db.execute(select(Anime.id).where(Anime.anilist_id == al["id"], Anime.id != anime.id))).first()
            if not taken:
                anime.anilist_id = int(al["id"])
                await db.commit()
            return int(al["id"])
    return None


async def _resolve_tmdb(db: AsyncSession, anime: Anime) -> tuple[int, str] | None:
    media = "movie" if anime.type.value == "film" else "tv"
    if anime.tmdb_id:
        return anime.tmdb_id, media
    try:
        details, found_media = await catalog_meta._tmdb_lookup(anime.title, db)  # noqa: SLF001
    except Exception:  # noqa: BLE001
        return None
    if not details or not details.get("id"):
        return None
    taken = (await db.execute(select(Anime.id).where(Anime.tmdb_id == details["id"], Anime.id != anime.id))).first()
    if not taken:
        anime.tmdb_id = int(details["id"])
        await db.commit()
    return int(details["id"]), found_media or media


async def credits_for(db: AsyncSession, anime: Anime) -> dict:
    """{"source": "anilist"|"tmdb"|None, "groups": [{"title", "people": [{name, role, image, sub_name, sub_image}]}]}."""
    if anime.category != "live":
        al_id = await _resolve_anilist_id(db, anime)
        if al_id:
            try:
                data = await anilist.get_credits(al_id, db)
            except Exception as exc:  # noqa: BLE001
                logger.warning("AniList credits indisponibles pour %s : %s", anime.id, exc)
                data = None
            if data and (data["characters"] or data["staff"]):
                groups = []
                if data["characters"]:
                    groups.append(
                        {
                            "title": "Personnages",
                            "people": [
                                {
                                    "name": c["name"],
                                    "role": c["role"],
                                    "image": c["image"],
                                    "sub_name": c["voice_actor"],
                                    "sub_image": c["voice_actor_image"],
                                }
                                for c in data["characters"]
                            ],
                        }
                    )
                if data["staff"]:
                    groups.append({"title": "Équipe", "people": [{**s, "sub_name": None, "sub_image": None} for s in data["staff"]]})
                return {"source": "anilist", "groups": groups}
    # films, séries — et repli des animés introuvables sur AniList
    ref = await _resolve_tmdb(db, anime)
    if ref:
        try:
            data = await tmdb.get_credits(ref[0], ref[1], db)
        except Exception as exc:  # noqa: BLE001
            logger.warning("TMDB credits indisponibles pour %s : %s", anime.id, exc)
            return {"source": None, "groups": []}
        groups = []
        if data["cast"]:
            groups.append(
                {
                    "title": "Distribution",
                    "people": [{**c, "sub_name": None, "sub_image": None} for c in data["cast"]],
                }
            )
        if data["crew"]:
            groups.append({"title": "Équipe", "people": [{**c, "sub_name": None, "sub_image": None} for c in data["crew"]]})
        return {"source": "tmdb", "groups": groups}
    return {"source": None, "groups": []}


async def similar_ids(db: AsyncSession, anime: Anime) -> list[int]:
    """n° (sur le site) des titres similaires, dans l'ordre de pertinence de la source."""
    ids: list[int] = []
    if anime.category != "live":
        al_id = await _resolve_anilist_id(db, anime)
        if al_id:
            try:
                recs = await anilist.get_recommendations(al_id, db)
            except Exception as exc:  # noqa: BLE001
                logger.warning("AniList recommandations indisponibles pour %s : %s", anime.id, exc)
                recs = []
            wanted = [int(r["id"]) for r in recs if r.get("id")]
            if wanted:
                rows = (await db.execute(select(Anime.id, Anime.anilist_id).where(Anime.anilist_id.in_(wanted)))).all()
                by_al = {al: aid for aid, al in rows}
                ids = [by_al[w] for w in wanted if w in by_al]
    if not ids:
        ref = await _resolve_tmdb(db, anime) if (anime.category == "live" or anime.tmdb_id) else None
        if ref:
            try:
                recs = await tmdb.get_similar(ref[0], ref[1], db)
            except Exception as exc:  # noqa: BLE001
                logger.warning("TMDB recommandations indisponibles pour %s : %s", anime.id, exc)
                recs = []
            wanted = [int(r["id"]) for r in recs if r.get("id")]
            if wanted:
                rows = (await db.execute(select(Anime.id, Anime.tmdb_id).where(Anime.tmdb_id.in_(wanted)))).all()
                by_tm = {tm: aid for aid, tm in rows}
                ids = [by_tm[w] for w in wanted if w in by_tm]
    return [i for i in ids if i != anime.id]
