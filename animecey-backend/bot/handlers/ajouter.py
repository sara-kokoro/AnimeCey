"""/ajouter <titre> : ajoute un animé qui n'est pas dans le catalogue (ex. Punchline).

  /ajouter Punchline            cherche sur TMDB (animation japonaise en premier)
  /ajouter tv:123456            ajoute directement la fiche TMDB (tv: série, movie: film)

Le bot crée l'animé avec l'affiche, le synopsis, les genres, la note et la bande-annonce (TMDB +
AniList), puis les saisons « Saison 1, 2... » de la fiche (ou « Film 1 » pour un film). Aucune
source externe n'est nécessaire : tu envoies ensuite tes épisodes au bot comme d'habitude.
"""

from __future__ import annotations

import logging
import re

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import func, select

from bot.handlers.admin import is_admin
from database import async_session
from models import Anime, AnimeStatus, AnimeType
from models_catalog import AnimeSeason
from services import aliases, catalog_meta, tmdb

logger = logging.getLogger(__name__)

_DIRECT = re.compile(r"^(tv|movie):(\d+)$", re.I)
MAX_RESULTS = 8
MAX_SEASONS = 15


def _year(r: dict) -> str:
    d = r.get("first_air_date") or r.get("release_date") or ""
    return d[:4] if len(d) >= 4 else "?"


def _name(r: dict) -> str:
    return r.get("name") or r.get("title") or r.get("original_name") or r.get("original_title") or "?"


def _rank(r: dict) -> tuple[int, int]:
    return (0 if 16 in (r.get("genre_ids") or []) else 1, 0 if r.get("original_language") == "ja" else 1)


def season_slots(details: dict, media: str) -> list[tuple[str, str]]:
    """[('saison1', 'Saison 1'), ...] d'après la fiche TMDB ; un film = « Film 1 »."""
    if media == "movie":
        return [("film1", "Film 1")]
    numbers = sorted(
        {
            int(s["season_number"])
            for s in details.get("seasons") or []
            if int(s.get("season_number") or 0) >= 1 and (s.get("episode_count") or 0) > 0
        }
    )[:MAX_SEASONS]
    return [(f"saison{n}", f"Saison {n}") for n in (numbers or [1])]


async def _create(media: str, tmdb_id: int, category: str = "anime") -> str:
    """Crée la fiche (category « anime » ou « live »). Lève ValueError(message) si impossible."""
    async with async_session() as db:
        taken = (await db.execute(select(Anime.id, Anime.title).where(Anime.tmdb_id == tmdb_id))).first()
        if taken:
            raise ValueError(f"Déjà ajouté : « {taken.title} » (n°{taken.id}).")

        details = dict(await tmdb.get_details(tmdb_id, media, db) or {})
        details.setdefault("id", tmdb_id)
        title = (details.get("name") or details.get("title") or details.get("original_name") or "").strip()
        if not title:
            raise ValueError("Cette fiche TMDB n'a pas de titre.")
        same = (await db.execute(select(Anime.id).where(func.lower(Anime.title) == title.lower()))).first()
        if same:
            raise ValueError(f"Un animé « {title} » existe déjà (n°{same[0]}). Utilise /fiche {same[0]} pour changer sa fiche.")

        al = None
        # Films et séries live-action : pas de recherche AniList (risque de fausse correspondance)
        for name in () if category == "live" else (details.get("original_name") or details.get("original_title"), title):
            if not name:
                continue
            try:
                al = await catalog_meta._anilist_lookup(name, db)  # noqa: SLF001
            except Exception:  # noqa: BLE001
                al = None
            if al:
                break
        meta = catalog_meta.merge_metadata(details, media, al, None)
        if meta.get("anilist_id") and (
            await db.execute(select(Anime.id).where(Anime.anilist_id == meta["anilist_id"]))
        ).first():
            meta["anilist_id"] = None

        slots = season_slots(details, media)
        is_film = media == "movie" or bool(meta.get("is_film"))
        anime = Anime(
            title=title[:255],
            title_jp=meta.get("title_jp"),
            type=AnimeType.film if is_film and len(slots) == 1 else AnimeType.serie,
            status=AnimeStatus(meta.get("status") or "completed"),
            synopsis=meta.get("synopsis"),
            poster_url=meta.get("poster_url"),
            banner_url=meta.get("banner_url"),
            genres=meta.get("genres") or [],
            score=meta.get("score") or 0.0,
            year=meta.get("year"),
            tmdb_id=tmdb_id,
            anilist_id=meta.get("anilist_id"),
            trailer_url=meta.get("trailer_url"),
            category=category,
        )
        db.add(anime)
        await db.flush()
        for number, (key, label) in enumerate(slots, start=1):
            db.add(
                AnimeSeason(
                    anime_id=anime.id, season_number=number, api_season=key, label=label,
                    kind="film" if key.startswith("film") else "saison",
                )
            )
        await db.commit()
        names = ", ".join(label for _, label in slots)
        anime_id, anime_title, anime_type = anime.id, anime.title, anime.type
        original = (details.get("original_name") or details.get("original_title") or "").strip()

    # Autres noms pour la recherche (titre d'origine ; AniList pour les animés)
    if category == "live":
        await aliases.add_aliases(anime_id, [anime_title, original])
        if anime_type == AnimeType.film:
            return (
                f"✅ Film « {anime_title} » ajouté (n°{anime_id}).\n"
                f"Envoie le fichier : /movie {anime_id} VF (ou VOSTFR), puis envoie ou transfère la vidéo."
            )
        return (
            f"✅ Série « {anime_title} » ajoutée (n°{anime_id}) — {names}.\n"
            f"Envoie les épisodes : /movie {anime_id}, puis les fichiers avec une légende du genre "
            f"« {anime_title} S01E01 VF »."
        )
    aliases.schedule_sync(anime_id)
    return (
        f"✅ « {anime_title} » ajouté (n°{anime_id}) — {names}.\n"
        f"Envoie maintenant tes épisodes : /anime {anime_id} puis les fichiers, "
        f"ou une légende du genre « {anime_title} S01E01 VOSTFR »."
    )


def register(bot: Client):

    @bot.on_message(filters.private & filters.command("ajouter"))
    async def cmd_ajouter(client: Client, message: Message):
        if not message.from_user or not is_admin(message.from_user.id):
            return
        rest = " ".join(message.command[1:]).strip()
        if not rest:
            return await message.reply(
                "Usage : /ajouter <titre>\n"
                "Ex. /ajouter Punchline\n"
                "Ou directement une fiche TMDB : /ajouter tv:123456"
            )
        direct = _DIRECT.match(rest)
        if direct:
            try:
                return await message.reply(await _create(direct.group(1).lower(), int(direct.group(2))))
            except ValueError as exc:
                return await message.reply(f"❌ {exc}")
            except Exception as exc:  # noqa: BLE001
                logger.exception("/ajouter direct en échec")
                return await message.reply(f"❌ Erreur : {exc}")

        try:
            async with async_session() as db:
                results = await tmdb.search(rest, db)
        except Exception as exc:  # noqa: BLE001
            logger.exception("/ajouter : recherche TMDB en échec")
            return await message.reply(f"❌ Recherche TMDB impossible : {exc}")
        results = sorted(results, key=_rank)[:MAX_RESULTS]
        if not results:
            return await message.reply(f"Aucun résultat pour « {rest} ». Essaie le titre anglais ou japonais.")

        lines, buttons = [f"Résultats pour « {rest} » — choisis :", ""], []
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
            buttons.append(InlineKeyboardButton(str(i), callback_data=f"add:{media}:{r['id']}"))
        rows = [buttons[i : i + 4] for i in range(0, len(buttons), 4)]
        rows.append([InlineKeyboardButton("❌ Annuler", callback_data="add:cancel")])
        await message.reply("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows))

    @bot.on_callback_query(filters.regex(r"^add:"))
    async def cb_ajouter(client: Client, query: CallbackQuery):
        if not is_admin(query.from_user.id):
            return await query.answer("Accès non autorisé.", show_alert=True)
        parts = query.data.split(":")
        if parts[1] == "cancel":
            await query.message.edit_text("Annulé.")
            return await query.answer()
        try:
            _, media, tmdb_id = parts
            await query.answer("Ajout en cours…")
            text = await _create(media, int(tmdb_id))
        except ValueError as exc:
            text = f"❌ {exc}"
        except Exception as exc:  # noqa: BLE001
            logger.exception("ajout en échec")
            text = f"❌ Erreur : {exc}"
        await query.message.edit_text(text)
