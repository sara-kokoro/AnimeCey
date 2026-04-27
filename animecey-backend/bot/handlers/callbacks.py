"""Inline callback query handlers."""

from __future__ import annotations

import logging

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery
from sqlalchemy import select

from bot.handlers.admin import is_admin
from bot.utils.keyboards import season_keyboard
from database import async_session
from models import BotSession, Folder, FolderType

logger = logging.getLogger(__name__)


def register(bot: Client):

    @bot.on_callback_query(filters.regex(r"^select_lang:"))
    async def cb_select_lang(client: Client, query: CallbackQuery):
        if not is_admin(query.from_user.id):
            return await query.answer("Accès non autorisé.", show_alert=True)

        _, parent_folder_id, language = query.data.split(":", 2)
        parent_folder_id = int(parent_folder_id)

        async with async_session() as db:
            lang_folder_q = await db.execute(
                select(Folder).where(
                    Folder.parent_id == parent_folder_id,
                    Folder.folder_type == FolderType.language,
                    Folder.language == language,
                )
            )
            lang_folder = lang_folder_q.scalar_one_or_none()
            if not lang_folder:
                return await query.answer("Dossier de langue introuvable.", show_alert=True)

            children = await db.execute(
                select(Folder).where(
                    Folder.parent_id == lang_folder.id,
                    Folder.folder_type == FolderType.season,
                )
            )
            seasons = [
                {"id": f.id, "season_number": f.season_number}
                for f in children.scalars().all()
                if f.season_number
            ]

            session_q = await db.execute(
                select(BotSession).where(BotSession.telegram_user_id == query.from_user.id)
            )
            session = session_q.scalar_one_or_none()
            if session:
                session.selected_language = language

            if not seasons:
                if session:
                    session.current_state = "receiving_files"
                    session.selected_folder_id = lang_folder.id
                    session.selected_season = 1
                    await db.commit()
                await query.message.edit_text(
                    f"Langue : {language}\n"
                    "Aucune saison trouvée. Prêt à recevoir les fichiers.\n"
                    "/cancel pour terminer."
                )
            else:
                if session:
                    session.current_state = "select_season"
                    session.selected_folder_id = lang_folder.id
                    await db.commit()
                await query.message.edit_text(
                    f"Langue : {language}\nChoisissez la saison :",
                    reply_markup=season_keyboard(seasons),
                )

    @bot.on_callback_query(filters.regex(r"^select_season:"))
    async def cb_select_season(client: Client, query: CallbackQuery):
        if not is_admin(query.from_user.id):
            return await query.answer("Accès non autorisé.", show_alert=True)

        _, season_folder_id, season_number = query.data.split(":", 2)
        season_folder_id = int(season_folder_id)
        season_number = int(season_number)

        async with async_session() as db:
            folder_q = await db.execute(select(Folder).where(Folder.id == season_folder_id))
            folder = folder_q.scalar_one_or_none()
            if not folder:
                return await query.answer("Dossier de saison introuvable.", show_alert=True)

            session_q = await db.execute(
                select(BotSession).where(BotSession.telegram_user_id == query.from_user.id)
            )
            session = session_q.scalar_one_or_none()
            if session:
                session.current_state = "receiving_files"
                session.selected_folder_id = season_folder_id
                session.selected_season = season_number
                await db.commit()

        await query.message.edit_text(
            f"Saison {season_number} sélectionnée.\n"
            f"Prêt à recevoir les fichiers vidéo.\n"
            f"/cancel pour terminer."
        )

    @bot.on_callback_query(filters.regex(r"^confirm_replace:"))
    async def cb_confirm_replace(client: Client, query: CallbackQuery):
        if not is_admin(query.from_user.id):
            return await query.answer("Accès non autorisé.", show_alert=True)

        _, episode_number, answer = query.data.split(":", 2)
        if answer == "no":
            return await query.message.edit_text(f"Épisode {episode_number} ignoré.")
        await query.message.edit_text(
            f"Remplacement de l'épisode {episode_number} en cours..."
        )
