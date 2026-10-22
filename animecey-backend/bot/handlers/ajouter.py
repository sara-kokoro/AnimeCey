"""/ajouter <titre> : ajoute un animé qui n'est pas dans le catalogue (ex. Punchline).

  /ajouter Punchline            cherche sur TMDB (animation japonaise en premier)
  /ajouter tv:123456            ajoute directement la fiche TMDB (tv: série, movie: film)
  /ajouter al <titre>           cherche directement sur AniList (quand TMDB n'a pas la fiche)
  /ajouter al:154587            ajoute directement la fiche AniList (n° AniList)

Sous les résultats TMDB, le bouton « Chercher sur AniList » relance la même recherche sur AniList.
TMDB n'est pas remplacé : AniList est une recherche en plus (fiche en anglais, pas de synopsis FR).

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
from services import aliases, anilist, calendar_sync, catalog_meta, tmdb

logger = logging.getLogger(__name__)

_DIRECT = re.compile(r"^(tv|movie):(\d+)$", re.I)
_DIRECT_AL = re.compile(r"^(?:al|anilist):(\d+)$", re.I)
_AL_WORD = re.compile(r"^(?:al|anilist)\s+(.+)$", re.I)

# Texte des recherches en attente : le bouton AniList ne peut pas contenir tout le titre (64 octets max)
_PENDING: dict[str, str] = {}
_PENDING_MAX = 200
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


def _remember(query: str) -> str:
    if len(_PENDING) >= _PENDING_MAX:
        _PENDING.pop(next(iter(_PENDING)))
    token = f"{abs(hash(query)) % 10**8:08d}"
    _PENDING[token] = query
    return token


def _al_title(m: dict) -> str:
    t = m.get("title") or {}
    return t.get("english") or t.get("romaji") or t.get("native") or "?"


async def _create_from_anilist(anilist_id: int) -> str:
    """Crée la fiche d'un animé à partir d'AniList seul. Lève ValueError(message) si impossible."""
    async with async_session() as db:
        taken = (await db.execute(select(Anime.id, Anime.title).where(Anime.anilist_id == anilist_id))).first()
        if taken:
            raise ValueError(f"Déjà ajouté : « {taken.title} » (n°{taken.id}).")
        details = dict(await anilist.get_details(anilist_id, db) or {})
        if not details.get("id"):
            raise ValueError("Fiche AniList introuvable.")
        title = _al_title(details).strip()
        same = (await db.execute(select(Anime.id).where(func.lower(Anime.title) == title.lower()))).first()
        if same:
            raise ValueError(f"Un animé « {title} » existe déjà (n°{same[0]}). Utilise /fiche {same[0]} pour changer sa fiche.")

        meta = catalog_meta.merge_metadata(None, None, details, None)
        is_film = details.get("format") == "MOVIE"
        if is_film:
            slot = ("film1", "Film 1")
        else:
            n = int(calendar_sync._anilist_season(  # noqa: SLF001
                [v for v in (details.get("title") or {}).values() if v] + list(details.get("synonyms") or [])
            ))
            slot = (f"saison{n}", f"Saison {n}")
        anime = Anime(
            title=title[:255],
            title_jp=meta.get("title_jp"),
            type=AnimeType.film if is_film else AnimeType.serie,
            status=AnimeStatus(meta.get("status") or "completed"),
            synopsis=meta.get("synopsis"),
            poster_url=meta.get("poster_url"),
            banner_url=meta.get("banner_url"),
            genres=meta.get("genres") or [],
            score=meta.get("score") or 0.0,
            year=meta.get("year"),
            tmdb_id=None,
            anilist_id=anilist_id,
            trailer_url=meta.get("trailer_url"),
            category="anime",
        )
        db.add(anime)
        await db.flush()
        db.add(
            AnimeSeason(
                anime_id=anime.id, season_number=1, api_season=slot[0], label=slot[1],
                kind="film" if is_film else "saison",
            )
        )
        await db.commit()
        anime_id, anime_title = anime.id, anime.title
        names = [n for n in ((details.get("title") or {}).get("native"), (details.get("title") or {}).get("romaji")) if n]

    await aliases.add_aliases(anime_id, [anime_title, *names])
    aliases.schedule_sync(anime_id)
    return (
        f"✅ « {anime_title} » ajouté depuis AniList (n°{anime_id}) — {slot[1]}.\n"
        f"Envoie maintenant tes épisodes : /anime {anime_id} puis les fichiers, "
        f"ou une légende du genre « {anime_title} S{slot[0][6:].zfill(2) if not is_film else '01'}E01 VOSTFR »."
    )


async def _anilist_results_reply(message_or_query, query: str, edit: bool) -> None:
    """Affiche les résultats AniList pour `query` (nouveau message, ou édition du message du bouton)."""
    try:
        async with async_session() as db:
            results = await anilist.search(query, db)
    except Exception as exc:  # noqa: BLE001
        logger.exception("/ajouter : recherche AniList en échec")
        text, markup = f"❌ Recherche AniList impossible : {exc}", None
    else:
        results = (results or [])[:MAX_RESULTS]
        if not results:
            text, markup = f"Aucun résultat AniList pour « {query} » non plus. Essaie le titre japonais (romaji).", None
        else:
            lines, buttons = [f"Résultats AniList pour « {query} » — choisis :", ""], []
            for i, r in enumerate(results, start=1):
                year = r.get("seasonYear") or (r.get("startDate") or {}).get("year") or "?"
                fmt = (r.get("format") or "").replace("_", " ").title()
                eps = f" · {r['episodes']} ép." if r.get("episodes") else ""
                lines.append(f"{i}. {_al_title(r)} ({year}) · {fmt}{eps}")
                buttons.append(InlineKeyboardButton(str(i), callback_data=f"add:al:{r['id']}"))
            rows = [buttons[i : i + 4] for i in range(0, len(buttons), 4)]
            rows.append([InlineKeyboardButton("❌ Annuler", callback_data="add:cancel")])
            text, markup = "\n".join(lines), InlineKeyboardMarkup(rows)
    if edit:
        await message_or_query.message.edit_text(text, reply_markup=markup)
    else:
        await message_or_query.reply(text, reply_markup=markup)


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
        direct_al = _DIRECT_AL.match(rest)
        if direct_al:
            try:
                return await message.reply(await _create_from_anilist(int(direct_al.group(1))))
            except ValueError as exc:
                return await message.reply(f"❌ {exc}")
            except Exception as exc:  # noqa: BLE001
                logger.exception("/ajouter AniList direct en échec")
                return await message.reply(f"❌ Erreur : {exc}")
        al_word = _AL_WORD.match(rest)
        if al_word:
            return await _anilist_results_reply(message, al_word.group(1).strip(), edit=False)
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
            await message.reply(f"Rien sur TMDB pour « {rest} » — je cherche sur AniList...")
            return await _anilist_results_reply(message, rest, edit=False)

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
        rows.append([InlineKeyboardButton("🔎 Chercher sur AniList", callback_data=f"add:alq:{_remember(rest)}")])
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
        if parts[1] == "alq":  # bouton « Chercher sur AniList »
            text = _PENDING.get(parts[2])
            if not text:
                await query.answer("Recherche expirée : relance /ajouter.", show_alert=True)
                return
            await query.answer("Recherche sur AniList…")
            return await _anilist_results_reply(query, text, edit=True)
        if parts[1] == "al":  # un résultat AniList choisi
            try:
                await query.answer("Ajout en cours…")
                text = await _create_from_anilist(int(parts[2]))
            except ValueError as exc:
                text = f"❌ {exc}"
            except Exception as exc:  # noqa: BLE001
                logger.exception("ajout AniList en échec")
                text = f"❌ Erreur : {exc}"
            return await query.message.edit_text(text)
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
