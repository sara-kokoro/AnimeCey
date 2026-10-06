"""/add <titre> : ajoute un film ou une série avec de vrais acteurs (Deadpool, The Boys, Squid Game...).

  /add Deadpool            cherche sur TMDB (live-action en premier) et te laisse choisir
  /add tv:136315           ajoute directement la fiche TMDB (tv: série, movie: film)

TMDB sait si c'est un film ou une série : le bot crée la fiche (affiche, synopsis, genres, note,
bande-annonce, saisons). Ensuite, /movie <n°> pour envoyer les fichiers, comme /anime pour les animés.
"""

from __future__ import annotations

import logging

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.handlers.admin import is_admin
from bot.handlers.ajouter import _DIRECT, MAX_RESULTS, _create, _name, _year
from database import async_session
from services import tmdb

logger = logging.getLogger(__name__)


def _rank(r: dict) -> int:
    return 1 if 16 in (r.get("genre_ids") or []) else 0  # l'animation passe après (c'est le rôle de /ajouter)


def register(bot: Client):

    @bot.on_message(filters.private & filters.command("add"))
    async def cmd_add(client: Client, message: Message):
        if not message.from_user or not is_admin(message.from_user.id):
            return
        rest = " ".join(message.command[1:]).strip()
        if not rest:
            return await message.reply(
                "Usage : /add <titre>\nEx. /add Deadpool ou /add The Boys\n"
                "Ou directement une fiche TMDB : /add tv:136315\n"
                "(Pour un animé, utilise /ajouter.)"
            )
        direct = _DIRECT.match(rest)
        if direct:
            try:
                return await message.reply(await _create(direct.group(1).lower(), int(direct.group(2)), "live"))
            except ValueError as exc:
                return await message.reply(f"❌ {exc}")
            except Exception as exc:  # noqa: BLE001
                logger.exception("/add direct en échec")
                return await message.reply(f"❌ Erreur : {exc}")

        try:
            async with async_session() as db:
                results = await tmdb.search(rest, db)
        except Exception as exc:  # noqa: BLE001
            logger.exception("/add : recherche TMDB en échec")
            return await message.reply(f"❌ Recherche TMDB impossible : {exc}")
        results = sorted(results, key=_rank)[:MAX_RESULTS]
        if not results:
            return await message.reply(f"Aucun résultat pour « {rest} ». Essaie le titre anglais.")

        lines, buttons = [f"Résultats pour « {rest} » — choisis :", ""], []
        for i, r in enumerate(results, start=1):
            media = "movie" if r.get("media_type") == "movie" else "tv"
            tags = ["Film" if media == "movie" else "Série"]
            if 16 in (r.get("genre_ids") or []):
                tags.append("animation")
            over = (r.get("overview") or "").strip().replace("\n", " ")
            lines.append(f"{i}. {_name(r)} ({_year(r)}) · {' · '.join(tags)}")
            if over:
                lines.append(f"   {over[:90]}{'…' if len(over) > 90 else ''}")
            buttons.append(InlineKeyboardButton(str(i), callback_data=f"addl:{media}:{r['id']}"))
        rows = [buttons[i : i + 4] for i in range(0, len(buttons), 4)]
        rows.append([InlineKeyboardButton("❌ Annuler", callback_data="addl:cancel")])
        await message.reply("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows))

    @bot.on_callback_query(filters.regex(r"^addl:"))
    async def cb_add(client: Client, query: CallbackQuery):
        if not is_admin(query.from_user.id):
            return await query.answer("Accès non autorisé.", show_alert=True)
        parts = query.data.split(":")
        if parts[1] == "cancel":
            await query.message.edit_text("Annulé.")
            return await query.answer()
        try:
            _, media, tmdb_id = parts
            await query.answer("Ajout en cours…")
            text = await _create(media, int(tmdb_id), "live")
        except ValueError as exc:
            text = f"❌ {exc}"
        except Exception as exc:  # noqa: BLE001
            logger.exception("ajout live en échec")
            text = f"❌ Erreur : {exc}"
        await query.message.edit_text(text)
