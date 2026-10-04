"""/vignettes <n° animé> : remplit les vignettes (et titres) des épisodes depuis TMDB.

Utile pour les épisodes venus du catalogue et pour ceux déjà envoyés avant l'ajout des
vignettes automatiques. Ne touche pas aux vignettes tirées de tes propres vidéos.
Fonctionne pour les saisons « Saison N » ; les sagas, films et OAV n'ont pas de
correspondance fiable chez TMDB et sont ignorés.
"""

from __future__ import annotations

import logging
import re

import httpx
from pyrogram import Client, filters
from pyrogram.types import Message
from sqlalchemy import select

from bot.handlers.admin import is_admin
from database import async_session
from models import Anime, Episode
from models_catalog import AnimeSeason
from services import tmdb

logger = logging.getLogger(__name__)

TMDB_IMG = "https://image.tmdb.org/t/p/w500"
_SEASON_KEY = re.compile(r"^saison(\d+)$")


def register(bot: Client):

    @bot.on_message(filters.private & filters.command("vignettes"))
    async def cmd_vignettes(client: Client, message: Message):
        if not message.from_user or not is_admin(message.from_user.id):
            return
        args = message.command[1:]
        if not args or not args[0].isdigit():
            return await message.reply(
                "Usage : /vignettes <n° animé> [force]\n"
                "Ex. /vignettes 16\n"
                "Ajoute « force » pour remplacer aussi les vignettes déjà présentes."
            )
        anime_id, force = int(args[0]), "force" in [a.lower() for a in args[1:]]
        status = await message.reply("⏳ Recherche des vignettes…")
        try:
            async with async_session() as db:
                anime = await db.get(Anime, anime_id)
                if not anime:
                    return await status.edit_text("Animé introuvable.")
                if not anime.tmdb_id:
                    return await status.edit_text(
                        f"« {anime.title} » n'a pas de fiche TMDB. Fais d'abord /fiche {anime_id}."
                    )
                seasons = (
                    await db.execute(select(AnimeSeason).where(AnimeSeason.anime_id == anime_id))
                ).scalars().all()
                episodes = (
                    await db.execute(select(Episode).where(Episode.anime_id == anime_id))
                ).scalars().all()

                lines, filled_total, skipped = [], 0, []
                for season in sorted(seasons, key=lambda s: s.season_number):
                    m = _SEASON_KEY.match(season.api_season or "")
                    if not m:
                        skipped.append(season.label)
                        continue
                    tmdb_season = int(m.group(1))
                    try:
                        data = await tmdb.get_season(anime.tmdb_id, tmdb_season, db)
                    except httpx.HTTPStatusError:
                        lines.append(f"• {season.label} : introuvable chez TMDB")
                        continue
                    by_num = {e.get("episode_number"): e for e in data.get("episodes") or []}
                    filled = total = 0
                    for ep in episodes:
                        if ep.season_number != season.season_number:
                            continue
                        total += 1
                        info = by_num.get(ep.episode_number)
                        if not info:
                            continue
                        own = bool(ep.thumb_msg_id)  # vignette tirée de notre vidéo : on la garde
                        if info.get("still_path") and not own and (force or not ep.thumbnail_url):
                            ep.thumbnail_url = f"{TMDB_IMG}{info['still_path']}"
                            filled += 1
                        if not ep.title and info.get("name"):
                            ep.title = info["name"][:255]
                    filled_total += filled
                    lines.append(f"• {season.label} : {filled}/{total}")
                await db.commit()

            text = f"✅ {filled_total} vignette(s) ajoutée(s) pour « {anime.title} »\n" + "\n".join(lines)
            if skipped:
                text += "\nIgnorés (pas de correspondance TMDB) : " + ", ".join(skipped[:6])
            await status.edit_text(text[:4000])
        except Exception as exc:  # noqa: BLE001
            logger.exception("/vignettes en échec")
            await status.edit_text(f"❌ Erreur : {exc}")
