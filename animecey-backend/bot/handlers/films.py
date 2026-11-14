"""/lierfilm : montrer un film déjà rangé dans une série sur sa propre fiche.

  /lierfilm <n° fiche du film> <n° de la série> <emplacement>
  Ex. /lierfilm 52 10 film15     → les fichiers de « One Piece » > Film 15 apparaissent aussi sur la fiche n°52

Rien n'est copié ni envoyé de nouveau : la fiche du film pointe vers les mêmes messages du canal.
Pour les prochains envois, ce lien se fait tout seul (voir services/film_link.py) quand la légende
ressemble au titre de la fiche du film (« One Piece Film Red » ↔ « One Piece Film - Red »).
"""

from __future__ import annotations

import logging
import re

from pyrogram import Client, filters
from pyrogram.types import Message
from sqlalchemy import select

from bot.handlers.admin import is_admin
from database import async_session
from models import Anime, AnimeType, Episode
from models_catalog import AnimeSeason
from services import film_link, httpcache

logger = logging.getLogger(__name__)


def _key(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def register(bot: Client):

    @bot.on_message(filters.private & filters.command(["lierfilm", "lienfilm"]))
    async def cmd_lierfilm(client: Client, message: Message):
        if not message.from_user or not is_admin(message.from_user.id):
            return
        args = message.command[1:]
        if len(args) < 3 or not args[0].isdigit() or not args[1].isdigit():
            return await message.reply(
                "Usage : /lierfilm <n° fiche du film> <n° de la série> <emplacement>\n"
                "Ex. /lierfilm 52 10 film15 : les fichiers de « One Piece » > Film 15 apparaissent aussi sur la fiche n°52.\n"
                "(Trouve les n° avec /list <titre>.) Rien n'est renvoyé dans le canal : les deux fiches partagent le même fichier."
            )
        film_id, series_id, slot = int(args[0]), int(args[1]), _key(" ".join(args[2:]))
        try:
            async with async_session() as db:
                film, series = await db.get(Anime, film_id), await db.get(Anime, series_id)
                if not film or not series:
                    return await message.reply("Fiche introuvable (vérifie les deux n°).")
                if film_id == series_id:
                    return await message.reply("La fiche du film et la série doivent être différentes.")
                seasons = (await db.execute(select(AnimeSeason).where(AnimeSeason.anime_id == series_id))).scalars().all()
                src = next((s for s in seasons if _key(s.api_season or "") == slot or _key(s.label or "") == slot), None)
                if src is None:
                    src = next((s for s in seasons if _key(s.api_season or "").startswith(slot) and slot), None)
                if src is None:
                    names = ", ".join(s.label for s in seasons if s.kind != "saison") or "aucun film"
                    return await message.reply(f"« {series.title} » n'a pas d'emplacement « {' '.join(args[2:])} ». Emplacements non-saison : {names}.")
                episodes = (
                    await db.execute(
                        select(Episode).where(
                            Episode.anime_id == series_id, Episode.season_number == src.season_number,
                            Episode.servcey1_file_id.is_not(None), Episode.servcey1_msg_id.is_not(None),
                        )
                    )
                ).scalars().all()
                if not episodes:
                    return await message.reply(
                        f"« {series.title} » > {src.label} n'a aucun fichier envoyé par le bot à copier "
                        "(les épisodes lus depuis une source externe ne se copient pas)."
                    )
                # emplacement du film sur sa fiche : son « Film 1 » (créé s'il manque)
                fseasons = (await db.execute(select(AnimeSeason).where(AnimeSeason.anime_id == film_id))).scalars().all()
                dst = next((s for s in fseasons if s.kind == "film"), None) or (fseasons[0] if fseasons else None)
                if dst is None:
                    dst = AnimeSeason(anime_id=film_id, season_number=1, api_season="film1", label="Film 1", kind="film")
                    db.add(dst)
                    await db.flush()
                added = replaced = kept = 0
                for ep in episodes:
                    status, _stale = await film_link.mirror_episode(
                        db, film, dst.season_number, dst.label, ep.language, ep.episode_number,
                        ep.servcey1_file_id, ep.servcey1_msg_id, ep.duration, replace=False,
                    )
                    added += status == "added"
                    replaced += status == "replaced"
                    kept += status == "kept"
                if film.type != AnimeType.film and len(fseasons) <= 1:
                    film.type = AnimeType.film
                await db.commit()
            httpcache.clear()
            langs = ", ".join(sorted({e.language.value for e in episodes}))
            await message.reply(
                f"✅ « {film.title} » (n°{film_id}) montre maintenant « {series.title} » > {src.label} : "
                f"{added} fichier(s) relié(s) ({langs})" + (f", {kept} déjà présent(s)" if kept else "") + "."
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("/lierfilm en échec")
            await message.reply(f"❌ Erreur : {exc}")
