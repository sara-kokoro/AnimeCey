"""Affiches, logos et backdrops des titres, gérés depuis le bot.

  /poster <n°>               liste les affiches (la 1re est l'affiche principale)
  /poster <n°> + image       ajoute une affiche en plus (2e, 3e...) : envoie l'image avec « /poster 16 »
                             en légende, ou réponds à une image avec « /poster 16 », ou /poster 16 <lien https>
  /delposter <n°> <rang>     retire une affiche supplémentaire (rang vu dans /poster ; « tout » = toutes)
  /setposter <n°> [garder]   REMPLACE l'affiche principale (image, lien https, ou « tmdb » pour remettre celle de TMDB) ;
                             « garder » conserve l'ancienne comme affiche supplémentaire
  /setlogo <n°>              remplace le logo (image envoyée EN FICHIER pour garder la transparence, lien https,
                             « tmdb » pour reprendre celui de TMDB, « aucun » pour le retirer)
  /setbackdrop <n°>          remplace le backdrop (image large, lien https, ou « tmdb »)
  /logos <n°>                relit le logo TMDB d'un titre (français, sinon anglais...)
  /logos all [force]         relit les logos manquants de tous les titres (1 appel TMDB par titre, doucement)

Le logo s'affiche au-dessus du titre sur la fiche ; le backdrop sert de vignette aux épisodes.
Les anciens titres se mettent à jour tout seuls à leur première ouverture sur le site (pas besoin de /logos all).
"""

from __future__ import annotations

import asyncio
import logging

from pyrogram import Client, filters
from pyrogram.types import InputMediaPhoto, Message
from sqlalchemy import select

from bot.handlers.admin import is_admin
from database import async_session
from models import Anime, AnimeType
from services import httpcache, images, tmdb

logger = logging.getLogger(__name__)

MAX_POSTERS = 9  # affiches supplémentaires par titre
_URL_PREFIX = "https://"


def _clear() -> None:
    httpcache.clear()  # le site garde les réponses ~2 min : on les vide pour voir le changement tout de suite


def _media_of(message: Message) -> Message | None:
    """Le message qui porte l'image : celui-ci, ou celui auquel on répond."""
    for m in (message, message.reply_to_message):
        if m is None:
            continue
        if m.photo:
            return m
        if m.document and (m.document.mime_type or "").startswith("image/"):
            return m
    return None


async def _download(client: Client, m: Message) -> bytes:
    buf = await client.download_media(m, in_memory=True)
    return buf.getvalue()


def _parse(message: Message) -> tuple[int | None, list[str]]:
    args = message.command[1:]
    if not args or not args[0].isdigit():
        return None, []
    return int(args[0]), [a for a in args[1:]]


async def _tmdb_details(db, anime: Anime) -> dict:
    """Détails TMDB du titre (la fiche choisie avec /fiche). ValueError(message) s'il n'en a pas."""
    if not anime.tmdb_id:
        raise ValueError(f"« {anime.title} » n'a pas de fiche TMDB. Fais d'abord /fiche {anime.id}.")
    media = "movie" if anime.type == AnimeType.film else "tv"
    try:
        return dict(await tmdb.get_details(int(anime.tmdb_id), media, db) or {})
    except Exception:  # noqa: BLE001 — un film classé « série » (ou l'inverse) : on essaie l'autre type
        other = "tv" if media == "movie" else "movie"
        return dict(await tmdb.get_details(int(anime.tmdb_id), other, db) or {})


async def _source_image(client: Client, message: Message, extra: list[str], anime: Anime, kind: str, db) -> str | None:
    """L'adresse de l'image voulue : fichier joint, lien https, ou « tmdb ». ValueError(message) si impossible.

    None = pas d'image fournie.
    """
    words = [w.lower() for w in extra]
    link = next((w for w in extra if w.lower().startswith(_URL_PREFIX)), None)
    if link:
        return link[:500]
    if "tmdb" in words and kind != "extra":
        details = await _tmdb_details(db, anime)
        if kind == "poster":
            url = images.tmdb_url(details.get("poster_path"), "w500")
        elif kind == "backdrop":
            url = images.tmdb_url(details.get("best_backdrop_path") or details.get("backdrop_path"), "original")
        else:
            url = images.tmdb_url(details.get("logo_path"), "w500")
        if not url:
            raise ValueError(f"TMDB n'a pas de {'logo' if kind == 'logo' else kind} pour ce titre.")
        return url
    media = _media_of(message)
    if media is not None:
        data = await _download(client, media)
        return (await images.store_bytes(client, anime.id, kind, data))[:500]
    return None


def register(bot: Client):

    # ── /poster : liste ou ajoute une affiche supplémentaire ─────────────────────

    @bot.on_message(filters.private & filters.command("poster"))
    async def cmd_poster(client: Client, message: Message):
        if not message.from_user or not is_admin(message.from_user.id):
            return
        anime_id, extra = _parse(message)
        if anime_id is None:
            return await message.reply(
                "Usage : /poster <n° animé>\n"
                "• seul : liste les affiches\n"
                "• avec une image (légende « /poster 16 » ou en réponse à l'image) : ajoute une affiche en plus\n"
                "• ou /poster 16 <lien https>\n"
                "Pour remplacer l'affiche principale : /setposter. Retirer : /delposter."
            )
        try:
            async with async_session() as db:
                anime = await db.get(Anime, anime_id)
                if not anime:
                    return await message.reply("Animé introuvable.")
                current = list(anime.posters or [])
                if len(current) >= MAX_POSTERS and (_media_of(message) or extra):
                    return await message.reply(f"❌ {MAX_POSTERS} affiches supplémentaires au maximum. Retire-en une avec /delposter.")
                url = await _source_image(client, message, extra, anime, "extra", db)
                if url is None:  # pas d'image : on liste
                    lines = [f"Affiches de « {anime.title} » :", f"1. (principale) {anime.poster_url or '—'}"]
                    lines += [f"{i}. {u}" for i, u in enumerate(current, start=2)]
                    lines.append("\nAjouter : envoie une image avec « /poster " + str(anime_id) + " » en légende.")
                    await message.reply("\n".join(lines)[:4000], disable_web_page_preview=True)
                    shown = [u for u in [anime.poster_url, *current] if u][:10]
                    if len(shown) >= 2:
                        try:
                            await client.send_media_group(message.chat.id, [InputMediaPhoto(u) for u in shown])
                        except Exception:  # noqa: BLE001 — l'aperçu est un plus, la liste suffit
                            logger.info("aperçu des affiches impossible", exc_info=True)
                    return
                if url in current or url == anime.poster_url:
                    return await message.reply("Cette affiche est déjà enregistrée.")
                anime.posters = [*current, url]
                await db.commit()
                total = len(anime.posters) + 1
            _clear()
            await message.reply(f"✅ Affiche ajoutée à « {anime.title} » ({total} au total, n°{total}).")
        except ValueError as exc:
            await message.reply(f"❌ {exc}")
        except Exception as exc:  # noqa: BLE001
            logger.exception("/poster en échec")
            await message.reply(f"❌ Erreur : {exc}")

    # ── /delposter ───────────────────────────────────────────────────────────────

    @bot.on_message(filters.private & filters.command("delposter"))
    async def cmd_delposter(client: Client, message: Message):
        if not message.from_user or not is_admin(message.from_user.id):
            return
        anime_id, extra = _parse(message)
        if anime_id is None or not extra:
            return await message.reply(
                "Usage : /delposter <n° animé> <rang>\n"
                "Le rang est celui affiché par /poster <n°> (2, 3...). « /delposter 16 tout » retire toutes les "
                "affiches supplémentaires. L'affiche principale (rang 1) se remplace avec /setposter."
            )
        try:
            async with async_session() as db:
                anime = await db.get(Anime, anime_id)
                if not anime:
                    return await message.reply("Animé introuvable.")
                current = list(anime.posters or [])
                if extra[0].lower() in ("tout", "all"):
                    removed, keep = current, []
                elif extra[0].isdigit() and 2 <= int(extra[0]) <= len(current) + 1:
                    removed = [current[int(extra[0]) - 2]]
                    keep = [u for i, u in enumerate(current) if i != int(extra[0]) - 2]
                elif extra[0] == "1":
                    return await message.reply("Le rang 1 est l'affiche principale : utilise /setposter pour la remplacer.")
                else:
                    return await message.reply(f"Rang inconnu. « {anime.title} » a {len(current) + 1} affiche(s) : /poster {anime_id}.")
                anime.posters = keep
                await db.commit()
            for u in removed:
                await images.delete_stored(u)
            _clear()
            await message.reply(f"✅ {len(removed)} affiche(s) retirée(s) de « {anime.title} ».")
        except Exception as exc:  # noqa: BLE001
            logger.exception("/delposter en échec")
            await message.reply(f"❌ Erreur : {exc}")

    # ── /setposter /setlogo /setbackdrop : remplacer ─────────────────────────────

    async def _replace(client: Client, message: Message, kind: str):
        if not message.from_user or not is_admin(message.from_user.id):
            return
        label = {"poster": "l'affiche principale", "logo": "le logo", "backdrop": "le backdrop"}[kind]
        field = {"poster": "poster_url", "logo": "logo_url", "backdrop": "banner_url"}[kind]
        cmd = {"poster": "setposter", "logo": "setlogo", "backdrop": "setbackdrop"}[kind]
        anime_id, extra = _parse(message)
        if anime_id is None:
            hint = {
                "poster": "Envoie une image (légende « /setposter 16 »), réponds à une image, donne un lien https, "
                          "ou écris « tmdb » pour remettre l'affiche de TMDB. Ajoute « garder » pour conserver l'ancienne "
                          "comme affiche supplémentaire.",
                "logo": "Envoie l'image EN FICHIER (pas en photo) pour garder la transparence PNG, ou un lien https. "
                        "« tmdb » reprend le logo de TMDB, « aucun » retire le logo.",
                "backdrop": "Envoie une image large (légende « /setbackdrop 16 »), un lien https, ou « tmdb ».",
            }[kind]
            return await message.reply(f"Usage : /{cmd} <n° animé>\n{hint}")
        words = [w.lower() for w in extra]
        try:
            async with async_session() as db:
                anime = await db.get(Anime, anime_id)
                if not anime:
                    return await message.reply("Animé introuvable.")
                old = getattr(anime, field)
                if kind == "logo" and ("aucun" in words or "off" in words):
                    anime.logo_url = None
                    anime.images_synced = True  # ne pas le rechercher de nouveau tout seul
                    await db.commit()
                    await images.delete_stored(old)
                    _clear()
                    return await message.reply(f"✅ Logo retiré de « {anime.title} ».")
                url = await _source_image(client, message, extra, anime, kind, db)
                if url is None:
                    return await message.reply(f"❌ Pas d'image. Envoie-la avec « /{cmd} {anime_id} » en légende, ou en réponse, ou donne un lien https (ou « tmdb »).")
                if kind == "poster" and old and "garder" in words and old not in (anime.posters or []):
                    anime.posters = [*(anime.posters or []), old][:MAX_POSTERS]
                    old = None  # conservée : ne pas la supprimer
                setattr(anime, field, url)
                if kind in ("logo", "backdrop"):
                    anime.images_synced = True  # choix manuel : le rattrapage automatique n'y touchera pas
                await db.commit()
            if old and old != url:
                await images.delete_stored(old)
            _clear()
            await message.reply(f"✅ {label.capitalize()} de « {anime.title} » remplacé.")
        except ValueError as exc:
            await message.reply(f"❌ {exc}")
        except Exception as exc:  # noqa: BLE001
            logger.exception("/%s en échec", cmd)
            await message.reply(f"❌ Erreur : {exc}")

    @bot.on_message(filters.private & filters.command("setposter"))
    async def cmd_setposter(client: Client, message: Message):
        await _replace(client, message, "poster")

    @bot.on_message(filters.private & filters.command("setlogo"))
    async def cmd_setlogo(client: Client, message: Message):
        await _replace(client, message, "logo")

    @bot.on_message(filters.private & filters.command("setbackdrop"))
    async def cmd_setbackdrop(client: Client, message: Message):
        await _replace(client, message, "backdrop")

    # ── /logos : relire les logos TMDB ───────────────────────────────────────────

    @bot.on_message(filters.private & filters.command("logos"))
    async def cmd_logos(client: Client, message: Message):
        if not message.from_user or not is_admin(message.from_user.id):
            return
        args = [a.lower() for a in message.command[1:]]
        if not args:
            return await message.reply(
                "Usage :\n"
                "• /logos <n° animé> : relit le logo TMDB de ce titre (français, sinon anglais...)\n"
                "• /logos all : relit les logos manquants de tous les titres (1 appel TMDB par titre)\n"
                "• /logos all force : refait aussi ceux qui ont déjà un logo (écrase les logos posés à la main)\n"
                "Les anciens titres se mettent aussi à jour tout seuls à leur première ouverture sur le site."
            )
        force = "force" in args
        try:
            if args[0].isdigit():
                async with async_session() as db:
                    anime = await db.get(Anime, int(args[0]))
                    if not anime:
                        return await message.reply("Animé introuvable.")
                    details = await _tmdb_details(db, anime)
                    path = details.get("logo_path")
                    if not path:
                        anime.images_synced = True
                        await db.commit()
                        return await message.reply(f"TMDB n'a aucun logo pour « {anime.title} ».")
                    anime.logo_url = images.tmdb_url(path, "w500")
                    anime.images_synced = True
                    await db.commit()
                    url, lang = anime.logo_url, details.get("logo_lang")
                _clear()
                await message.reply(f"✅ Logo de « {anime.title} » mis à jour ({lang}).")
                try:
                    await client.send_photo(message.chat.id, url, caption=f"Logo : {anime.title}")
                except Exception:  # noqa: BLE001 — l'aperçu n'est qu'un plus
                    pass
                return
            if args[0] != "all":
                return await message.reply("Écris /logos <n° animé> ou /logos all.")

            async with async_session() as db:
                q = select(Anime.id).where(Anime.tmdb_id.is_not(None)).order_by(Anime.id)
                if not force:
                    q = q.where(Anime.logo_url.is_(None))
                ids = list((await db.execute(q)).scalars())
            if not ids:
                return await message.reply("Rien à faire : tous les titres avec une fiche TMDB ont déjà un logo.")
            status = await message.reply(f"⏳ {len(ids)} titre(s) à traiter (1 appel TMDB chacun, en douceur)…")
            found = missing = failed = 0
            for n, anime_id in enumerate(ids, start=1):
                res = await images.sync_anime(anime_id, force=True) if force else await _sync_missing(anime_id)
                if not res.get("ok"):
                    failed += 1
                elif res.get("logo"):
                    found += 1
                else:
                    missing += 1
                if n % 20 == 0:
                    try:
                        await status.edit_text(f"⏳ {n}/{len(ids)} — {found} logo(s) trouvé(s)…")
                    except Exception:  # noqa: BLE001
                        pass
                await asyncio.sleep(0.3)
            _clear()
            await status.edit_text(
                f"✅ Terminé : {found} logo(s) ajouté(s), {missing} titre(s) sans logo chez TMDB"
                + (f", {failed} en erreur (relance /logos all plus tard)" if failed else "")
                + "."
            )
        except ValueError as exc:
            await message.reply(f"❌ {exc}")
        except Exception as exc:  # noqa: BLE001
            logger.exception("/logos en échec")
            await message.reply(f"❌ Erreur : {exc}")


async def _sync_missing(anime_id: int) -> dict:
    """Comme sync_anime mais même si le titre est déjà marqué « synchronisé » (sans logo) ; ne remplace aucun logo."""
    return await images.sync_anime(anime_id, force=True, keep_logo=True)
