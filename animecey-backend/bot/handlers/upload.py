"""Handle /upload command and file reception."""

from __future__ import annotations

import asyncio
import logging

from pyrogram import Client, filters
from pyrogram.types import Message
from sqlalchemy import select

from bot.handlers.admin import is_admin
from bot.utils.episode_parser import parse_episode_number
from bot.utils.keyboards import (
    confirm_replace_keyboard,
    language_keyboard,
    season_keyboard,
)
from config import settings
from database import async_session
from models import BotSession, Episode, Folder, FolderType
from services import byse, telegram_stream

logger = logging.getLogger(__name__)


async def _get_or_create_session(db, telegram_user_id: int) -> BotSession:
    result = await db.execute(
        select(BotSession).where(BotSession.telegram_user_id == telegram_user_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        session = BotSession(telegram_user_id=telegram_user_id)
        db.add(session)
        await db.commit()
        await db.refresh(session)
    return session


def register(bot: Client):

    @bot.on_message(filters.command("upload") & filters.private)
    async def cmd_upload(client: Client, message: Message):
        if not is_admin(message.from_user.id):
            return await message.reply("Accès non autorisé.")

        parts = message.text.split()
        if len(parts) < 2 or not parts[1].isdigit():
            return await message.reply("Usage : /upload {folder_id}")

        folder_id = int(parts[1])
        async with async_session() as db:
            result = await db.execute(select(Folder).where(Folder.id == folder_id))
            folder = result.scalar_one_or_none()
            if not folder:
                return await message.reply(f"Dossier {folder_id} introuvable.")

            session = await _get_or_create_session(db, message.from_user.id)

            if folder.folder_type == FolderType.anime:
                children = await db.execute(
                    select(Folder).where(
                        Folder.parent_id == folder_id,
                        Folder.folder_type == FolderType.language,
                    )
                )
                langs = [f.language.value for f in children.scalars().all() if f.language]
                if not langs:
                    return await message.reply("Aucun sous-dossier de langue trouvé. Créez d'abord les dossiers VF/VOSTFR.")
                session.current_state = "select_language"
                session.selected_folder_id = folder_id
                await db.commit()
                return await message.reply(
                    f"📂 {folder.name}\nChoisissez la langue :",
                    reply_markup=language_keyboard(folder_id, langs),
                )

            elif folder.folder_type == FolderType.language:
                children = await db.execute(
                    select(Folder).where(
                        Folder.parent_id == folder_id,
                        Folder.folder_type == FolderType.season,
                    )
                )
                seasons = [
                    {"id": f.id, "season_number": f.season_number}
                    for f in children.scalars().all()
                    if f.season_number
                ]
                if not seasons:
                    return await message.reply("Aucun sous-dossier de saison trouvé.")
                session.current_state = "select_season"
                session.selected_folder_id = folder_id
                session.selected_language = folder.language.value if folder.language else None
                await db.commit()
                return await message.reply(
                    "Choisissez la saison :",
                    reply_markup=season_keyboard(seasons),
                )

            elif folder.folder_type == FolderType.season:
                session.current_state = "receiving_files"
                session.selected_folder_id = folder_id
                session.selected_language = folder.language.value if folder.language else None
                session.selected_season = folder.season_number
                await db.commit()
                return await message.reply(
                    f"Prêt. Envoie tes fichiers vidéo un par un ou tous ensemble.\n"
                    f"Dossier : {folder.name}\n"
                    f"/cancel pour terminer."
                )

    @bot.on_message(filters.private & (filters.video | filters.document | filters.audio))
    async def handle_file(client: Client, message: Message):
        if not is_admin(message.from_user.id):
            return

        async with async_session() as db:
            session = await _get_or_create_session(db, message.from_user.id)
            if session.current_state != "receiving_files" or not session.selected_folder_id:
                return

            media = message.video or message.document or message.audio
            if not media:
                return

            file_id = media.file_id
            file_name = getattr(media, "file_name", None) or f"file_{media.file_unique_id}"

            ep_number = parse_episode_number(file_name)
            if ep_number is None:
                session.current_state = "waiting_episode_number"
                await db.commit()
                return await message.reply(
                    f"Impossible de détecter le numéro d'épisode dans « {file_name} ».\n"
                    "Quel est le numéro de cet épisode ?"
                )

            folder = await db.execute(select(Folder).where(Folder.id == session.selected_folder_id))
            f = folder.scalar_one_or_none()
            if not f:
                return await message.reply("Erreur : dossier introuvable.")

            existing = await db.execute(
                select(Episode).where(
                    Episode.folder_id == session.selected_folder_id,
                    Episode.episode_number == ep_number,
                    Episode.language == session.selected_language,
                )
            )
            if existing.scalar_one_or_none():
                await message.reply(
                    f"L'épisode {ep_number} existe déjà dans ce dossier.\n"
                    "Veux-tu le remplacer ?",
                    reply_markup=confirm_replace_keyboard(ep_number),
                )
                return

            await _process_upload(client, message, db, session, f, file_id, file_name, ep_number)

    @bot.on_message(filters.private & filters.text & ~filters.command(["start", "upload", "status", "cancel", "list", "ep"]))
    async def handle_text(client: Client, message: Message):
        if not is_admin(message.from_user.id):
            return

        async with async_session() as db:
            session = await _get_or_create_session(db, message.from_user.id)
            if session.current_state == "waiting_episode_number":
                text = message.text.strip()
                if not text.isdigit():
                    return await message.reply("Envoie un numéro d'épisode valide.")
                ep_number = int(text)
                session.current_state = "receiving_files"
                await db.commit()
                await message.reply(f"Numéro d'épisode : {ep_number}. Traitement en cours...")


async def _process_upload(
    client: Client,
    message: Message,
    db,
    session: BotSession,
    folder: Folder,
    file_id: str,
    file_name: str,
    ep_number: int,
):
    progress_msg = await message.reply(
        f"Épisode {ep_number} reçu. Upload en cours vers ServCey 2..."
    )

    byse_file_code = None
    byse_ok = False

    try:
        token = settings.TELEGRAM_BOT_TOKEN
        tg_url = f"https://api.telegram.org/bot{token}/getFile"
        import httpx
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.get(tg_url, params={"file_id": file_id})
            data = resp.json()
        if data.get("ok"):
            file_path = data["result"]["file_path"]
            download_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
            result = await byse.remote_upload(download_url, file_name)
            byse_file_code = result.get("filecode")
            if byse_file_code:
                await progress_msg.edit_text(
                    f"Épisode {ep_number} — ServCey 2 : en cours..."
                )
                status = await byse.wait_for_upload(byse_file_code, poll_interval=5, max_wait=300)
                st = str(status.get("status", "")).upper()
                if st in ("COMPLETED", "OK", ""):
                    byse_ok = True
                    await progress_msg.edit_text(
                        f"Épisode {ep_number} — ServCey 2 : terminé."
                    )
                else:
                    await progress_msg.edit_text(
                        f"Épisode {ep_number} — ServCey 2 : échec ({status.get('error_msg', 'inconnu')})"
                    )
    except Exception as exc:
        logger.exception("Erreur upload byse.sx pour ep %s", ep_number)
        await progress_msg.edit_text(
            f"Épisode {ep_number} — ServCey 2 : erreur ({exc})"
        )

    anime_id = folder.anime_id
    episode = Episode(
        anime_id=anime_id,
        folder_id=folder.id,
        episode_number=ep_number,
        language=session.selected_language,
        season_number=session.selected_season or 1,
        servcey1_file_id=file_id,
        servcey1_available=True,
        servcey2_file_code=byse_file_code,
        servcey2_available=byse_ok,
    )
    db.add(episode)
    await db.commit()

    parent_path = ""
    if folder.parent_id:
        parent = await db.execute(select(Folder).where(Folder.id == folder.parent_id))
        p = parent.scalar_one_or_none()
        if p and p.parent_id:
            gp = await db.execute(select(Folder).where(Folder.id == p.parent_id))
            grandparent = gp.scalar_one_or_none()
            if grandparent:
                parent_path = f"{grandparent.name} › {p.name} › "
            else:
                parent_path = f"{p.name} › "
        elif p:
            parent_path = f"{p.name} › "

    s1_status = "disponible" if True else "indisponible"
    s2_status = "disponible" if byse_ok else "indisponible"
    await message.reply(
        f"✓ Épisode {ep_number} ajouté avec succès\n"
        f"  Dossier : {parent_path}{folder.name}\n"
        f"  ServCey 1 : {s1_status}\n"
        f"  ServCey 2 : {s2_status}\n\n"
        f"Envoie le prochain fichier ou /cancel pour terminer."
    )
