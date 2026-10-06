"""/supprimer <n° animé> : supprime un animé (saisons, épisodes, likes, commentaires...).

Rien n'est effacé tout de suite : le bot résume ce qui va disparaître et demande de choisir
avec des boutons (supprimer aussi les fichiers du canal, site seulement, ou annuler).
"""

from __future__ import annotations

import asyncio
import logging

from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import func, select

from bot.handlers import quick_upload
from bot.handlers.admin import is_admin
from config import settings
from database import async_session
from models import Anime, Episode
from models_catalog import AnimeSeason

logger = logging.getLogger(__name__)


async def _summary(anime_id: int) -> tuple[Anime | None, int, int, int]:
    """-> (animé, nb épisodes, nb saisons, nb messages du canal)."""
    async with async_session() as db:
        anime = await db.get(Anime, anime_id)
        if anime is None:
            return None, 0, 0, 0
        eps = (await db.execute(select(func.count()).select_from(Episode).where(Episode.anime_id == anime_id))).scalar() or 0
        seasons = (
            await db.execute(select(func.count()).select_from(AnimeSeason).where(AnimeSeason.anime_id == anime_id))
        ).scalar() or 0
        rows = (
            await db.execute(select(Episode.servcey1_msg_id, Episode.thumb_msg_id).where(Episode.anime_id == anime_id))
        ).all()
    msgs = {m for r in rows for m in r if m}
    return anime, eps, seasons, len(msgs)


async def _delete_channel_messages(client: Client, ids: list[int]) -> int:
    """Efface les messages du canal par paquets de 100 ; renvoie le nombre supprimé."""
    done = 0
    for i in range(0, len(ids), 100):
        chunk = ids[i : i + 100]
        for _ in range(3):
            try:
                done += int(await client.delete_messages(settings.TELEGRAM_CHANNEL_ID, chunk) or 0)
                break
            except FloodWait as exc:
                await asyncio.sleep(int(getattr(exc, "value", 10) or 10) + 1)
            except Exception:  # noqa: BLE001
                logger.warning("suppression de messages du canal impossible", exc_info=True)
                break
        await asyncio.sleep(1)
    return done


async def _delete_anime(client: Client, anime_id: int, with_channel: bool) -> str:
    async with async_session() as db:
        anime = await db.get(Anime, anime_id)
        if anime is None:
            return "Cet animé n'existe plus."
        title = anime.title
        rows = (
            await db.execute(select(Episode.servcey1_msg_id, Episode.thumb_msg_id).where(Episode.anime_id == anime_id))
        ).all()
        msg_ids = sorted({m for r in rows for m in r if m})
        await db.delete(anime)  # cascade : dossiers, épisodes, saisons, likes, commentaires...
        await db.commit()

    for uid, (aid, _) in list(quick_upload._current_anime.items()):
        if aid == anime_id:
            quick_upload._current_anime.pop(uid, None)
            quick_upload._current_opts.pop(uid, None)

    text = f"🗑 « {title} » supprimé du site."
    if with_channel and msg_ids:
        done = await _delete_channel_messages(client, msg_ids)
        text += f"\nCanal : {done}/{len(msg_ids)} message(s) effacé(s)."
        if done < len(msg_ids):
            text += "\n(Le bot doit avoir le droit « Supprimer les messages » dans le canal.)"
    elif msg_ids:
        text += f"\nLes {len(msg_ids)} fichier(s) restent dans le canal."
    return text


def register(bot: Client):

    @bot.on_message(filters.private & filters.command(["supprimer", "suppr"]))
    async def cmd_supprimer(client: Client, message: Message):
        if not message.from_user or not is_admin(message.from_user.id):
            return
        arg = " ".join(message.command[1:]).strip()
        if not arg.isdigit():
            return await message.reply(
                "Usage : /supprimer <n° de l'animé>\nTrouve le n° avec /list <titre>."
            )
        anime, eps, seasons, msgs = await _summary(int(arg))
        if anime is None:
            return await message.reply(f"Animé {arg} introuvable.")
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🗑 Supprimer + fichiers du canal", callback_data=f"del:all:{anime.id}")],
                [InlineKeyboardButton("🗑 Site seulement (garder les fichiers)", callback_data=f"del:db:{anime.id}")],
                [InlineKeyboardButton("❌ Annuler", callback_data="del:cancel")],
            ]
        )
        await message.reply(
            f"⚠️ Supprimer « {anime.title} » (n° {anime.id}) ?\n"
            f"• {eps} épisode(s), {seasons} saison(s)\n"
            f"• {msgs} message(s) dans le canal (vidéos + vignettes)\n"
            "Les likes, commentaires et favoris liés disparaissent aussi. Action irréversible.",
            reply_markup=kb,
        )

    @bot.on_callback_query(filters.regex(r"^del:"))
    async def cb_supprimer(client: Client, query: CallbackQuery):
        if not is_admin(query.from_user.id):
            return await query.answer("Accès non autorisé.", show_alert=True)
        parts = query.data.split(":")
        if parts[1] == "cancel":
            await query.message.edit_text("Suppression annulée.")
            return await query.answer()
        try:
            await query.answer("Suppression en cours…")
            await query.message.edit_text("⏳ Suppression en cours…")
            text = await _delete_anime(client, int(parts[2]), with_channel=parts[1] == "all")
        except Exception as exc:  # noqa: BLE001
            logger.exception("suppression d'animé en échec")
            text = f"❌ Erreur : {exc}"
        await query.message.edit_text(text)
