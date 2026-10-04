"""Admin commands: /start, /help, /status, /cancel, /list, /ep."""

from __future__ import annotations

import logging

from pyrogram import Client, filters
from pyrogram.types import Message
from sqlalchemy import func, select

from config import settings
from database import async_session
from models import Anime, BotSession, Episode, Folder, FolderType, User

logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    return user_id in settings.TELEGRAM_ADMIN_IDS


HELP_TEXT = (
    "Bienvenue sur le bot AnimeCey 👋\n"
    "\n"
    "📤 AJOUTER UN ÉPISODE\n"
    "Envoie ou transfère la vidéo avec une légende. Elle peut être libre, elle doit contenir :\n"
    "• le titre de l'animé\n"
    "• la langue : VF ou VOSTFR (Multi = VOSTFR)\n"
    "• le numéro de l'épisode\n"
    "• la saison, la saga, le film ou l'OAV (sans rien : Saison 1)\n"
    "\n"
    "Exemples :\n"
    "Naruto S01E05 VF\n"
    "Black Clover Saison 2 Épisode 12 VOSTFR\n"
    "One Piece Saga 1 (East Blue) — Épisode 6 [VF]\n"
    "Demon Slayer Film 1 VF\n"
    "\n"
    "MP4 : copié tel quel. MKV : converti en MP4, un à la fois (patiente).\n"
    "Les sous-titres VOSTFR doivent être incrustés dans la vidéo.\n"
    "\n"
    "♻️ DOUBLONS\n"
    "Si l'épisode existe déjà, le bot répond « Déjà existant » et ne change rien.\n"
    "Pour le remplacer, ajoute le mot REMPLACER dans la légende.\n"
    "\n"
    "🎯 /anime <n° ou titre>\n"
    "Fixe l'animé pendant 3 h, quand la légende n'a pas le même titre que sur le site "
    "(ex. « Kage no Jitsuryokusha » pour « The Eminence in Shadow »).\n"
    "\n"
    "🖼 /fiche <n°> [recherche]\n"
    "Choisis la bonne fiche TMDB (affiche, synopsis, genres…). "
    "Ex. /fiche 16 Kimetsu no Yaiba\n"
    "\n"
    "🎞 /vignettes <n°> [force]\n"
    "Remplit les vignettes et les titres des épisodes depuis TMDB (fais /fiche avant si la fiche est fausse).\n"
    "\n"
    "🔎 /list <titre> — trouver le n° d'un animé\n"
    "📂 /ep <n° dossier> — épisodes d'un dossier\n"
    "📊 /status — statistiques\n"
    "❓ /help — afficher ce message\n"
    "\n"
    "Le n° d'un animé est son ID affiché par /list."
)


def register(bot: Client):

    @bot.on_message(filters.command(["start", "help"]) & filters.private)
    async def cmd_start(client: Client, message: Message):
        if not message.from_user or not is_admin(message.from_user.id):
            return await message.reply("Accès non autorisé.")
        await message.reply(HELP_TEXT)

    @bot.on_message(filters.command("status") & filters.private)
    async def cmd_status(client: Client, message: Message):
        if not is_admin(message.from_user.id):
            return await message.reply("Accès non autorisé.")
        async with async_session() as db:
            animes_count = (await db.execute(select(func.count()).select_from(Anime))).scalar() or 0
            episodes_count = (await db.execute(select(func.count()).select_from(Episode))).scalar() or 0
            users_count = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
        await message.reply(
            f"📊 Statistiques AnimeCey\n\n"
            f"Animés : {animes_count}\n"
            f"Épisodes : {episodes_count}\n"
            f"Utilisateurs : {users_count}"
        )

    @bot.on_message(filters.command("cancel") & filters.private)
    async def cmd_cancel(client: Client, message: Message):
        if not is_admin(message.from_user.id):
            return await message.reply("Accès non autorisé.")
        async with async_session() as db:
            result = await db.execute(
                select(BotSession).where(BotSession.telegram_user_id == message.from_user.id)
            )
            session = result.scalar_one_or_none()
            if session:
                session.current_state = None
                session.selected_folder_id = None
                session.selected_language = None
                session.selected_season = None
                await db.commit()
        await message.reply("Opération annulée.")

    @bot.on_message(filters.command("list") & filters.private)
    async def cmd_list(client: Client, message: Message):
        if not is_admin(message.from_user.id):
            return await message.reply("Accès non autorisé.")
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            return await message.reply("Usage : /list {titre}")
        query = parts[1].strip()
        async with async_session() as db:
            result = await db.execute(
                select(Anime).where(Anime.title.ilike(f"%{query}%")).limit(10)
            )
            animes = result.scalars().all()
        if not animes:
            return await message.reply(f"Aucun animé trouvé pour « {query} »")
        lines = []
        for a in animes:
            folders_text = ""
            async with async_session() as db:
                folders = await db.execute(
                    select(Folder).where(Folder.anime_id == a.id)
                )
                for f in folders.scalars().all():
                    folders_text += f"\n  📁 {f.name} (ID: {f.id}, type: {f.folder_type.value})"
            lines.append(f"🎬 {a.title} (ID: {a.id}){folders_text}")
        await message.reply("\n\n".join(lines))

    @bot.on_message(filters.command("ep") & filters.private)
    async def cmd_ep(client: Client, message: Message):
        if not is_admin(message.from_user.id):
            return await message.reply("Accès non autorisé.")
        parts = message.text.split()
        if len(parts) < 2 or not parts[1].isdigit():
            return await message.reply("Usage : /ep {folder_id}")
        folder_id = int(parts[1])
        async with async_session() as db:
            folder = await db.execute(select(Folder).where(Folder.id == folder_id))
            f = folder.scalar_one_or_none()
            if not f:
                return await message.reply(f"Dossier {folder_id} introuvable.")
            episodes = await db.execute(
                select(Episode)
                .where(Episode.folder_id == folder_id)
                .order_by(Episode.episode_number)
            )
            eps = episodes.scalars().all()
        if not eps:
            return await message.reply(f"Aucun épisode dans le dossier « {f.name} ».")
        lines = [f"📂 {f.name}\n"]
        for ep in eps:
            s1 = "✓" if ep.servcey1_available else "✗"
            s2 = "✓" if ep.servcey2_available else "✗"
            lines.append(f"  Ep. {ep.episode_number} — S1:{s1} S2:{s2}")
        await message.reply("\n".join(lines))
