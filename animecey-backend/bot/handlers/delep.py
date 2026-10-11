"""/delep : supprime UN épisode précis (et son fichier dans le canal, si tu le veux).

  /delep 16 5              épisode 5 de l'animé 16 (plusieurs langues ou saisons : le bot te laisse choisir)
  /delep 16 5 VF           épisode 5, en VF
  /delep 16 12 S02 VOSTFR  épisode 12 de la saison 2, en VOSTFR
  /delep 16 S02E12 VF      pareil
  /delep 16 1 Film 2       le film 2 (un film est toujours « épisode 1 »)
  /delep E5                épisode 5 de l'animé fixé avec /anime

Rien n'est effacé avant ta confirmation (boutons). Les signalements ouverts sur cet épisode passent en « résolu ».
Le bouton « 🗑 Supprimer cet épisode » des signalements (/signalements) ouvre la même confirmation.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import delete, or_, select, update

from bot.handlers import quick_upload
from bot.handlers.admin import is_admin
from bot.handlers.delsaison import _find_season
from bot.handlers.supprimer import _delete_channel_messages
from database import async_session
from models import Anime, Episode, LanguageEnum
from models_catalog import AnimeSeason
from models_reports import Report
from services import report_notify, thumbs
from services.caption_parser import command_args, parse_anime_args, pretty_label

logger = logging.getLogger(__name__)

USAGE = (
    "Usage : /delep <n° animé> <n° épisode> [VF|VOSTFR] [saison]\n"
    "Ex. : /delep 16 5 → épisode 5 de l'animé 16\n"
    "/delep 16 5 VF → seulement la VF\n"
    "/delep 16 12 S02 VOSTFR → saison 2, VOSTFR\n"
    "/delep 16 S02E12 VF → pareil\n"
    "/delep 16 1 Film 2 → le film 2\n"
    "/delep E5 → épisode 5 de l'animé fixé avec /anime\n"
    "Le n° de l'animé : /list <titre>. Ce qui est en ligne : /bilan <n°>."
)

# « 5 », « E5 », « ep5 », « épisode 5 », « S02E05 »  (« S02 » tout seul n'est PAS un épisode)
_EP = re.compile(r"^(?:s(?P<s>\d{1,2})(?:e|ep|episode|épisode)|(?:e|ep|episode|épisode)?)(?P<e>\d{1,4})$", re.I)


def parse_args(raw: str, current_anime: int | None) -> dict | None:
    """-> {anime_id, episode, lang, slot} ou None si la commande n'est pas comprise."""
    tokens = raw.split()
    if not tokens:
        return None
    first = tokens[0]
    if first.isdigit():
        anime_id = int(first)
        rest_all = tokens[1:]
        if not rest_all:
            return None
        # l'épisode est soit juste après le n° d'animé, soit en dernier
        candidates = [(rest_all[0], rest_all[1:]), (rest_all[-1], rest_all[:-1])]
    elif current_anime and _EP.match(first):
        anime_id = current_anime
        candidates = [(first, tokens[1:])]
    else:
        return None

    for ep_tok, rest in candidates:
        m = _EP.match(ep_tok)
        if not m:
            continue
        leftover, lang, slot = parse_anime_args(" ".join(rest))
        if leftover:
            continue
        if slot is None and m.group("s"):
            slot = f"saison{int(m.group('s'))}"
        return {"anime_id": anime_id, "episode": int(m.group("e")), "lang": lang, "slot": slot}
    return None


def _ep_label(ep: Episode, labels: dict[int, str]) -> str:
    season = labels.get(ep.season_number) or f"Saison {ep.season_number}"
    lang = getattr(ep.language, "value", str(ep.language))
    return f"{season} · Épisode {ep.episode_number} · {lang}"


def _confirm_text(ep: Episode, title: str, label: str) -> str:
    msgs = {m for m in (ep.servcey1_msg_id, ep.thumb_msg_id) if m}
    text = (
        "⚠️ Supprimer cet épisode ?\n"
        f"• « {title} » — {label}\n"
        f"• n° interne {ep.id}\n"
        f"• {len(msgs)} message(s) dans le canal (vidéo + vignette)\n"
        f"• {ep.likes_count or 0} like(s) et {ep.comments_count or 0} commentaire(s) disparaîtront aussi\n"
        "Action irréversible."
    )
    if not ep.servcey1_msg_id and ep.stream_url:
        text += (
            "\n\n⚠️ Cet épisode vient de la synchro automatique (TMCooper) : il peut être recréé "
            "à la prochaine synchro tant que la source le propose."
        )
    return text


def _confirm_kb(ep_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🗑 Supprimer + fichier du canal", callback_data=f"dep:all:{ep_id}")],
            [InlineKeyboardButton("🗑 Site seulement (garder le fichier)", callback_data=f"dep:db:{ep_id}")],
            [InlineKeyboardButton("❌ Annuler", callback_data="dep:cancel")],
        ]
    )


async def _delete_episode(client: Client, ep_id: int, with_channel: bool) -> str:
    resolved: list[int] = []
    async with async_session() as db:
        ep = await db.get(Episode, ep_id)
        if ep is None:
            return "Cet épisode n'existe plus."
        anime = await db.get(Anime, ep.anime_id)
        season = (
            await db.execute(
                select(AnimeSeason).where(
                    AnimeSeason.anime_id == ep.anime_id, AnimeSeason.season_number == ep.season_number
                )
            )
        ).scalars().first()
        label = _ep_label(ep, {ep.season_number: season.label} if season else {})
        title = anime.title if anime else f"animé {ep.anime_id}"

        thumb_version = ep.thumb_msg_id  # sert à retrouver la vignette sur R2
        msgs = {m for m in (ep.servcey1_msg_id, ep.thumb_msg_id) if m}
        if msgs:  # ne jamais effacer un message du canal encore utilisé par un autre épisode
            others = (
                await db.execute(
                    select(Episode.servcey1_msg_id, Episode.thumb_msg_id).where(
                        Episode.id != ep_id,
                        or_(Episode.servcey1_msg_id.in_(msgs), Episode.thumb_msg_id.in_(msgs)),
                    )
                )
            ).all()
            msgs -= {m for row in others for m in row if m}

        resolved = list(
            (await db.execute(select(Report.id).where(Report.episode_id == ep_id, Report.status == "open")))
            .scalars()
            .all()
        )
        if resolved:
            await db.execute(
                update(Report)
                .where(Report.id.in_(resolved))
                .values(status="resolved", resolved_at=datetime.now(timezone.utc))
            )
        # likes et commentaires partent avec l'épisode (suppression en cascade côté base)
        await db.execute(delete(Episode).where(Episode.id == ep_id))
        await db.commit()

    await thumbs.delete(ep_id, thumb_version)  # vignette R2 (sans effet si R2 n'est pas configuré)
    text = f"🗑 {label} supprimé de « {title} »."
    if with_channel and msgs:
        done = await _delete_channel_messages(client, sorted(msgs))
        text += f"\nCanal : {done}/{len(msgs)} message(s) effacé(s)."
        if done < len(msgs):
            text += "\n(Le bot doit avoir le droit « Supprimer les messages » dans le canal.)"
    elif msgs:
        text += f"\nLe fichier ({len(msgs)} message(s)) reste dans le canal."
    if resolved:
        text += f"\n✅ {len(resolved)} signalement(s) lié(s) passé(s) en « résolu »."
        for rid in resolved:
            try:
                await report_notify.notify(rid, ping=False)
            except Exception:  # noqa: BLE001
                logger.warning("mise à jour du signalement %s impossible", rid, exc_info=True)
    return text


def register(bot: Client):

    @bot.on_message(filters.private & filters.command(["delep", "supprimerep"]))
    async def cmd_delep(client: Client, message: Message):
        if not message.from_user or not is_admin(message.from_user.id):
            return

        current = None
        cur = quick_upload._current_anime.get(message.from_user.id)
        if cur and time.time() - cur[1] < quick_upload.CURRENT_TTL:
            current = cur[0]

        args = parse_args(command_args(message.text) or " ".join(message.command[1:]), current)
        if args is None:
            return await message.reply(USAGE)

        async with async_session() as db:
            anime = await db.get(Anime, args["anime_id"])
            if anime is None:
                return await message.reply(f"Animé {args['anime_id']} introuvable.")
            stmt = select(Episode).where(
                Episode.anime_id == anime.id, Episode.episode_number == args["episode"]
            )
            if args["slot"]:
                season = await _find_season(db, anime.id, args["slot"])
                if season is None:
                    rows = (
                        await db.execute(
                            select(AnimeSeason.label)
                            .where(AnimeSeason.anime_id == anime.id)
                            .order_by(AnimeSeason.season_number)
                        )
                    ).scalars().all()
                    have = "\n".join(f"• {x}" for x in rows) or "(aucune)"
                    return await message.reply(
                        f"« {pretty_label(args['slot'])} » n'existe pas pour « {anime.title} ».\nSaisons :\n{have}"
                    )
                stmt = stmt.where(Episode.season_number == season.season_number)
            if args["lang"]:
                stmt = stmt.where(Episode.language == LanguageEnum(args["lang"]))
            eps = list(
                (await db.execute(stmt.order_by(Episode.season_number, Episode.language))).scalars().all()
            )
            labels = {
                s.season_number: s.label
                for s in (
                    await db.execute(select(AnimeSeason).where(AnimeSeason.anime_id == anime.id))
                ).scalars().all()
            }

        if not eps:
            return await message.reply(
                f"Aucun épisode {args['episode']} trouvé pour « {anime.title} » avec ces critères.\n"
                f"Regarde ce qui est en ligne avec /bilan {anime.id}."
            )
        if len(eps) == 1:
            return await message.reply(
                _confirm_text(eps[0], anime.title, _ep_label(eps[0], labels)), reply_markup=_confirm_kb(eps[0].id)
            )
        if len(eps) > 12:
            return await message.reply("Plus de 12 correspondances : précise la langue et/ou la saison.")
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton(_ep_label(e, labels), callback_data=f"dep:ask:{e.id}")] for e in eps]
            + [[InlineKeyboardButton("❌ Annuler", callback_data="dep:cancel")]]
        )
        await message.reply(
            f"« {anime.title} » : {len(eps)} épisodes correspondent. Lequel supprimer ?", reply_markup=kb
        )

    @bot.on_callback_query(filters.regex(r"^dep:"))
    async def cb_delep(client: Client, query: CallbackQuery):
        if not is_admin(query.from_user.id):
            return await query.answer("Accès non autorisé.", show_alert=True)
        parts = query.data.split(":")
        action = parts[1]
        if action == "cancel":
            await query.message.edit_text("Suppression annulée.")
            return await query.answer()

        ep_id = int(parts[2])
        if action == "ask":
            async with async_session() as db:
                ep = await db.get(Episode, ep_id)
                if ep is None:
                    return await query.answer("Cet épisode n'existe plus.", show_alert=True)
                anime = await db.get(Anime, ep.anime_id)
                labels = {
                    s.season_number: s.label
                    for s in (
                        await db.execute(select(AnimeSeason).where(AnimeSeason.anime_id == ep.anime_id))
                    ).scalars().all()
                }
            await query.message.reply(
                _confirm_text(ep, anime.title if anime else f"animé {ep.anime_id}", _ep_label(ep, labels)),
                reply_markup=_confirm_kb(ep.id),
            )
            return await query.answer()

        try:
            await query.answer("Suppression en cours…")
            await query.message.edit_text("⏳ Suppression en cours…")
            text = await _delete_episode(client, ep_id, with_channel=action == "all")
        except Exception as exc:  # noqa: BLE001
            logger.exception("suppression d'épisode en échec")
            text = f"❌ Erreur : {exc}"
        await query.message.edit_text(text)
