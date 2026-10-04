"""Choisir toi-même la fiche TMDB d'un animé.

  /fiche 16                       cherche avec le titre de l'animé n°16
  /fiche 16 Kimetsu no Yaiba      cherche avec ce texte
  /fiche 16 tv:85937              applique directement la fiche TMDB (tv: série, movie: film)

Le bot propose les résultats (animation japonaise en premier) ; tu appuies sur le bon numéro et
l'affiche, le synopsis, les genres, l'année, la note et la bande-annonce sont remplacés.
"""

from __future__ import annotations

import logging
import re

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select

from bot.handlers.admin import is_admin
from database import async_session
from models import Anime
from services import catalog_meta, tmdb

logger = logging.getLogger(__name__)

_DIRECT = re.compile(r"^(tv|movie):(\d+)$", re.I)
MAX_RESULTS = 8


def _year(r: dict) -> str:
    d = r.get("first_air_date") or r.get("release_date") or ""
    return d[:4] if len(d) >= 4 else "?"


def _name(r: dict) -> str:
    return r.get("name") or r.get("title") or r.get("original_name") or r.get("original_title") or "?"


def _rank(r: dict) -> tuple[int, int]:
    return (0 if 16 in (r.get("genre_ids") or []) else 1, 0 if r.get("original_language") == "ja" else 1)


async def _apply(anime_id: int, media: str, tmdb_id: int) -> str:
    """Remplace la fiche de l'animé. Lève ValueError(message) si impossible."""
    async with async_session() as db:
        anime = await db.get(Anime, anime_id)
        if not anime:
            raise ValueError("Animé introuvable.")
        taken = (
            await db.execute(select(Anime.id, Anime.title).where(Anime.tmdb_id == tmdb_id, Anime.id != anime_id))
        ).first()
        if taken:
            raise ValueError(f"Cette fiche est déjà utilisée par « {taken.title} » (n°{taken.id}).")

        details = await tmdb.get_details(tmdb_id, media, db)
        details = dict(details or {})
        details.setdefault("id", tmdb_id)

        al = None
        for name in (
            details.get("original_name") or details.get("original_title"),
            details.get("name") or details.get("title"),
            anime.title,
        ):
            if not name:
                continue
            try:
                al = await catalog_meta._anilist_lookup(name, db)  # noqa: SLF001
            except Exception:  # noqa: BLE001
                al = None
            if al:
                break

        meta = catalog_meta.merge_metadata(details, media, al, anime.poster_url)
        await catalog_meta.apply_metadata(db, anime, meta)
        return f"✅ Fiche mise à jour pour « {anime.title} » : {_name(details)} ({meta.get('year') or '?'})."


def register(bot: Client):

    @bot.on_message(filters.private & filters.command("fiche"))
    async def cmd_fiche(client: Client, message: Message):
        if not message.from_user or not is_admin(message.from_user.id):
            return
        args = message.command[1:]
        if not args or not args[0].isdigit():
            return await message.reply(
                "Usage : /fiche <n° animé> [recherche]\n"
                "Ex. /fiche 16 Kimetsu no Yaiba\n"
                "Ou directement : /fiche 16 tv:85937\n"
                "(trouve le n° avec /list Titre)"
            )
        anime_id, rest = int(args[0]), " ".join(args[1:]).strip()

        try:
            async with async_session() as db:
                anime = await db.get(Anime, anime_id)
                if not anime:
                    return await message.reply("Animé introuvable.")
                direct = _DIRECT.match(rest)
                if direct:
                    pass
                else:
                    query = rest or anime.title
                    results = await tmdb.search(query, db)
            if direct:
                try:
                    return await message.reply(await _apply(anime_id, direct.group(1).lower(), int(direct.group(2))))
                except ValueError as exc:
                    return await message.reply(f"❌ {exc}")
        except Exception as exc:  # noqa: BLE001
            logger.exception("/fiche en échec")
            return await message.reply(f"❌ Recherche TMDB impossible : {exc}")

        results = sorted(results, key=_rank)[:MAX_RESULTS]
        if not results:
            return await message.reply(f"Aucun résultat pour « {query} ». Essaie le titre anglais ou japonais.")

        lines, buttons = [f"Fiche pour « {anime.title} » — choisis :", ""], []
        for i, r in enumerate(results, start=1):
            media = "movie" if r.get("media_type") == "movie" else "tv"
            tags = ["Film" if media == "movie" else "Série"]
            if 16 in (r.get("genre_ids") or []):
                tags.append("animation")
            if r.get("original_language"):
                tags.append(r["original_language"])
            over = (r.get("overview") or "").strip().replace("\n", " ")
            lines.append(f"{i}. {_name(r)} ({_year(r)}) · {' · '.join(tags)}")
            if over:
                lines.append(f"   {over[:90]}{'…' if len(over) > 90 else ''}")
            buttons.append(InlineKeyboardButton(str(i), callback_data=f"fiche:{anime_id}:{media}:{r['id']}"))
        rows = [buttons[i : i + 4] for i in range(0, len(buttons), 4)]
        rows.append([InlineKeyboardButton("❌ Annuler", callback_data="fiche:cancel")])
        await message.reply("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows))

    @bot.on_callback_query(filters.regex(r"^fiche:"))
    async def cb_fiche(client: Client, query: CallbackQuery):
        if not is_admin(query.from_user.id):
            return await query.answer("Accès non autorisé.", show_alert=True)
        parts = query.data.split(":")
        if parts[1] == "cancel":
            await query.message.edit_text("Annulé.")
            return await query.answer()
        try:
            _, anime_id, media, tmdb_id = parts
            await query.answer("Mise à jour…")
            text = await _apply(int(anime_id), media, int(tmdb_id))
        except ValueError as exc:
            text = f"❌ {exc}"
        except Exception as exc:  # noqa: BLE001
            logger.exception("choix de fiche en échec")
            text = f"❌ Erreur : {exc}"
        await query.message.edit_text(text)
