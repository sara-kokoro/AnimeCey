"""/bilan <n° animé> : ce qui est réellement en ligne, saison par saison et langue par langue."""

from __future__ import annotations

import logging
from collections import defaultdict

from pyrogram import Client, filters
from pyrogram.types import Message
from sqlalchemy import select

from bot.handlers.admin import is_admin
from database import async_session
from models import Anime, Episode
from models_catalog import AnimeSeason

logger = logging.getLogger(__name__)


def _ranges(numbers: list[int]) -> str:
    """[1,2,3,5,6,9] -> '1-3, 5-6, 9'"""
    nums = sorted(set(numbers))
    if not nums:
        return "—"
    parts, start, prev = [], nums[0], nums[0]
    for n in nums[1:]:
        if n == prev + 1:
            prev = n
            continue
        parts.append(f"{start}-{prev}" if start != prev else str(start))
        start = prev = n
    parts.append(f"{start}-{prev}" if start != prev else str(start))
    return ", ".join(parts)


def register(bot: Client):

    @bot.on_message(filters.private & filters.command("bilan"))
    async def cmd_bilan(client: Client, message: Message):
        if not message.from_user or not is_admin(message.from_user.id):
            return
        args = message.command[1:]
        if not args or not args[0].isdigit():
            return await message.reply("Usage : /bilan <n° animé>\nEx. /bilan 4 (le n° est affiché par /list)")
        anime_id = int(args[0])
        try:
            async with async_session() as db:
                anime = await db.get(Anime, anime_id)
                if not anime:
                    return await message.reply("Animé introuvable.")
                seasons = (
                    await db.execute(
                        select(AnimeSeason).where(AnimeSeason.anime_id == anime_id).order_by(AnimeSeason.season_number)
                    )
                ).scalars().all()
                episodes = (await db.execute(select(Episode).where(Episode.anime_id == anime_id))).scalars().all()

            labels = {s.season_number: s.label for s in seasons}
            own: dict[tuple[int, str], list[int]] = defaultdict(list)    # envoyés sur ServCey 1
            other: dict[tuple[int, str], int] = defaultdict(int)         # autres serveurs seulement
            for ep in episodes:
                key = (ep.season_number, ep.language.value)
                if ep.servcey1_available:
                    own[key].append(ep.episode_number)
                else:
                    other[key] += 1

            keys = sorted(set(own) | set(other) | {(n, "VF") for n in labels} | {(n, "VOSTFR") for n in labels})
            lines = [f"📊 {anime.title} (n°{anime.id})", ""]
            for season_number, lang in keys:
                name = labels.get(season_number, f"Saison {season_number}")
                mine, ext = own.get((season_number, lang), []), other.get((season_number, lang), 0)
                if not mine and not ext:
                    continue
                bit = f"ServCey 1 : {len(mine)} ({_ranges(mine)})" if mine else "ServCey 1 : aucun"
                if ext:
                    bit += f" · autres serveurs : {ext}"
                lines.append(f"• {name} · {lang} → {bit}")
            if len(lines) == 2:
                lines.append("Aucun épisode pour le moment.")
            await message.reply("\n".join(lines)[:4000])
        except Exception as exc:  # noqa: BLE001
            logger.exception("/bilan en échec")
            await message.reply(f"❌ Erreur : {exc}")
