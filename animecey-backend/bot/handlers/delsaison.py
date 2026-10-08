"""/delsaison : supprime UNE saison (ou saga, film...) d'un animé, sans toucher aux autres.

  /delsaison 16 S02            supprime « Saison 2 » de l'animé 16 (pas « Saison 2 Partie 1 »)
  /delsaison S02               idem, sur l'animé fixé avec /anime
  /delsaison 16 S02 P1         supprime « Saison 2 Partie 1 »
  /delsaison 16 Saga 2 / Arc 3 / Film 1 / OAV

Le bot résume ce qui va disparaître et demande confirmation avec des boutons.
"""

from __future__ import annotations

import logging
import time

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import delete, func, select

from bot.handlers import quick_upload
from bot.handlers.admin import is_admin
from bot.handlers.supprimer import _delete_channel_messages
from database import async_session
from models import Anime, Episode, Folder, FolderType, TmcooperSource
from models_catalog import AnimeSeason
from services.caption_parser import command_args, parse_anime_args, pretty_label

logger = logging.getLogger(__name__)


async def _find_season(db, anime_id: int, key: str) -> AnimeSeason | None:
    """Saison dont la clé est EXACTEMENT `key` (« saison2 » ne trouve pas « saison2partie1 »)."""
    seasons = (await db.execute(select(AnimeSeason).where(AnimeSeason.anime_id == anime_id))).scalars().all()
    for s in seasons:
        if s.api_season == key:
            return s
    starts = [s for s in seasons if s.api_season.startswith(key + "(")]  # « saga2 » = « saga2(alabasta) »
    return starts[0] if len(starts) == 1 else None


async def _episodes_info(db, anime_id: int, season_number: int) -> tuple[dict[str, int], list[int]]:
    rows = (
        await db.execute(
            select(Episode.language, Episode.servcey1_msg_id, Episode.thumb_msg_id).where(
                Episode.anime_id == anime_id, Episode.season_number == season_number
            )
        )
    ).all()
    per_lang: dict[str, int] = {}
    msgs: set[int] = set()
    for lang, m1, m2 in rows:
        name = getattr(lang, "value", str(lang))
        per_lang[name] = per_lang.get(name, 0) + 1
        msgs.update(m for m in (m1, m2) if m)
    return per_lang, sorted(msgs)


async def _delete_season(client: Client, anime_id: int, season_number: int, with_channel: bool) -> str:
    async with async_session() as db:
        anime = await db.get(Anime, anime_id)
        season = (
            await db.execute(
                select(AnimeSeason).where(AnimeSeason.anime_id == anime_id, AnimeSeason.season_number == season_number)
            )
        ).scalars().first()
        if anime is None or season is None:
            return "Cette saison n'existe plus."
        label, api_season = season.label, season.api_season
        per_lang, msg_ids = await _episodes_info(db, anime_id, season_number)
        nb_eps = sum(per_lang.values())

        # likes, commentaires et serveurs des épisodes partent avec eux (suppression en cascade)
        await db.execute(delete(Episode).where(Episode.anime_id == anime_id, Episode.season_number == season_number))
        await db.execute(
            delete(Folder).where(
                Folder.anime_id == anime_id,
                Folder.folder_type == FolderType.season,
                Folder.season_number == season_number,
            )
        )
        await db.execute(
            delete(TmcooperSource).where(TmcooperSource.anime_id == anime_id, TmcooperSource.season == api_season)
        )
        await db.delete(season)
        await db.commit()

    text = f"🗑 « {label} » supprimée de « {anime.title} » ({nb_eps} épisode(s))."
    if with_channel and msg_ids:
        done = await _delete_channel_messages(client, msg_ids)
        text += f"\nCanal : {done}/{len(msg_ids)} message(s) effacé(s)."
        if done < len(msg_ids):
            text += "\n(Le bot doit avoir le droit « Supprimer les messages » dans le canal.)"
    elif msg_ids:
        text += f"\nLes {len(msg_ids)} fichier(s) restent dans le canal."
    return text


def register(bot: Client):

    @bot.on_message(filters.private & filters.command(["delsaison", "supprimersaison"]))
    async def cmd_delsaison(client: Client, message: Message):
        if not message.from_user or not is_admin(message.from_user.id):
            return
        usage = (
            "Usage : /delsaison <n° animé> <saison>\n"
            "Ex. : /delsaison 16 S02 → supprime « Saison 2 » (pas « Saison 2 Partie 1 »)\n"
            "/delsaison 16 S02 P1 → supprime « Saison 2 Partie 1 »\n"
            "Autres : Saga 2, Arc 3, Film 1, OAV, Spécial, Récap, Bonus ou \"Nom libre\". Sans n°, l'animé fixé avec /anime est utilisé."
        )
        query, _lang, key = parse_anime_args(command_args(message.text) or " ".join(message.command[1:]))
        if not key:
            return await message.reply(usage)

        anime_id: int | None = int(query) if query.isdigit() else None
        if anime_id is None and not query:
            cur = quick_upload._current_anime.get(message.from_user.id)
            if cur and time.time() - cur[1] < quick_upload.CURRENT_TTL:
                anime_id = cur[0]
        if anime_id is None:
            return await message.reply("Précise le n° de l'animé (ou fixe-le avec /anime).\n\n" + usage)

        async with async_session() as db:
            anime = await db.get(Anime, anime_id)
            if anime is None:
                return await message.reply(f"Animé {anime_id} introuvable.")
            season = await _find_season(db, anime_id, key)
            if season is None:
                rows = (
                    await db.execute(
                        select(AnimeSeason.label).where(AnimeSeason.anime_id == anime_id).order_by(AnimeSeason.season_number)
                    )
                ).scalars().all()
                have = "\n".join(f"• {x}" for x in rows) or "(aucune)"
                return await message.reply(f"« {pretty_label(key)} » n'existe pas pour « {anime.title} ».\nSaisons :\n{have}")
            per_lang, msg_ids = await _episodes_info(db, anime_id, season.season_number)

        detail = ", ".join(f"{n} en {lang}" for lang, n in sorted(per_lang.items())) or "aucun épisode"
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🗑 Supprimer + fichiers du canal", callback_data=f"dsn:all:{anime_id}:{season.season_number}")],
                [InlineKeyboardButton("🗑 Site seulement (garder les fichiers)", callback_data=f"dsn:db:{anime_id}:{season.season_number}")],
                [InlineKeyboardButton("❌ Annuler", callback_data="dsn:cancel")],
            ]
        )
        await message.reply(
            f"⚠️ Supprimer « {season.label} » de « {anime.title} » ?\n"
            f"• Épisodes : {detail}\n"
            f"• {len(msg_ids)} message(s) dans le canal (vidéos + vignettes)\n"
            "Les autres saisons ne sont pas touchées. Les likes et commentaires de ces épisodes disparaissent. "
            "Action irréversible.",
            reply_markup=kb,
        )

    @bot.on_callback_query(filters.regex(r"^dsn:"))
    async def cb_delsaison(client: Client, query: CallbackQuery):
        if not is_admin(query.from_user.id):
            return await query.answer("Accès non autorisé.", show_alert=True)
        parts = query.data.split(":")
        if parts[1] == "cancel":
            await query.message.edit_text("Suppression annulée.")
            return await query.answer()
        try:
            await query.answer("Suppression en cours…")
            await query.message.edit_text("⏳ Suppression en cours…")
            text = await _delete_season(client, int(parts[2]), int(parts[3]), with_channel=parts[1] == "all")
        except Exception as exc:  # noqa: BLE001
            logger.exception("suppression de saison en échec")
            text = f"❌ Erreur : {exc}"
        await query.message.edit_text(text)
