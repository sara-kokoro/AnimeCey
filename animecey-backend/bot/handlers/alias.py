"""/alias : autres noms d'un animé, pour la recherche du site.

  /alias 16                         liste les autres noms
  /alias 16 Shingeki no Kyojin | SNK   ajoute un ou plusieurs noms (séparés par |)
  /alias 16 - SNK                   retire un nom
  /alias 16 auto                    relance la récupération automatique (catalogue + AniList)
"""

from __future__ import annotations

from pyrogram import Client, filters
from pyrogram.types import Message

from bot.handlers.admin import is_admin
from database import async_session
from models import Anime
from services import aliases


def register(bot: Client):

    @bot.on_message(filters.private & filters.command("alias"))
    async def cmd_alias(client: Client, message: Message):
        if not message.from_user or not is_admin(message.from_user.id):
            return
        parts = message.command[1:]
        if not parts or not parts[0].isdigit():
            return await message.reply(
                "Usage :\n/alias <n°> → voir les autres noms\n"
                "/alias <n°> nom1 | nom2 → ajouter\n/alias <n°> - nom → retirer\n"
                "/alias <n°> auto → récupération automatique"
            )
        anime_id = int(parts[0])
        rest = " ".join(parts[1:]).strip()
        async with async_session() as db:
            anime = await db.get(Anime, anime_id)
        if anime is None:
            return await message.reply(f"Animé {anime_id} introuvable.")

        if rest.lower() == "auto":
            try:
                n = await aliases.sync_aliases(anime_id)
            except Exception as exc:  # noqa: BLE001
                return await message.reply(f"❌ Récupération impossible : {exc}")
            rest = ""
            head = f"🔄 {n} nouveau(x) nom(s) trouvé(s) pour « {anime.title} »."
        elif rest.startswith("-"):
            name = rest.lstrip("-").strip()
            n = await aliases.remove_alias(anime_id, name) if name else 0
            head = f"🗑 « {name} » retiré." if n else "Ce nom n'existe pas."
            rest = ""
        elif rest:
            n = await aliases.add_aliases(anime_id, [x.strip() for x in rest.split("|")])
            head = f"✅ {n} nom(s) ajouté(s) à « {anime.title} »."
        else:
            head = f"« {anime.title} »"

        names = await aliases.list_aliases(anime_id)
        body = "\n".join(f"• {x}" for x in names[:40]) or "(aucun autre nom)"
        await message.reply(f"{head}\nAutres noms :\n{body}")
