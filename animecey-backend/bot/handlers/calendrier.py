"""Calendrier des sorties : /check, /calsync et le bouton « Vérifier si publié » des alertes.

  /check <n° animé>   sorties du calendrier de cet animé (3 jours passés, 8 jours à venir)
                      et état de chacune : publié, pas encore publié, autre saison...
  /check              les sorties des dernières 24 h qui ne sont pas encore publiées
  /calsync            relit tout de suite la page FRAnime (utile pour tester)

Mettre ce fichier dans bot/handlers/calendrier.py.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message
from sqlalchemy import select

from bot.handlers.admin import is_admin
from database import async_session
from models import Anime
from models_calendar import CalendarEntry
from services import calendar_sync as cal

logger = logging.getLogger(__name__)


def _when(entry: CalendarEntry) -> str:
    t = entry.release_at.astimezone(timezone.utc)
    return f"{cal.JOURS[t.weekday()][:3]}. {t:%d/%m} {t:%H:%M} UTC"


async def _status(db, entry: CalendarEntry, anime_id: int) -> dict:
    status = await cal.episode_status(db, anime_id, entry.season_raw, entry.episode_number, entry.language)
    if status["state"] == "published" and entry.pins and entry.unpinned_at is None:
        await cal.unpin_entry(entry)  # publié : plus besoin du message épinglé
        await db.commit()
    return status


def register(bot: Client):

    @bot.on_message(filters.private & filters.command("check"))
    async def cmd_check(client: Client, message: Message):
        if not message.from_user or not is_admin(message.from_user.id):
            return
        args = message.command[1:]
        now = datetime.now(timezone.utc)
        try:
            async with async_session() as db:
                if args:
                    if not args[0].isdigit():
                        return await message.reply("Usage : /check <n° animé>\nEx. /check 16 (le n° est affiché par /list)")
                    anime_id = int(args[0])
                    anime = await db.get(Anime, anime_id)
                    if not anime:
                        return await message.reply("Animé introuvable.")
                    entries = (
                        await db.execute(
                            select(CalendarEntry)
                            .where(
                                CalendarEntry.anime_id == anime_id,
                                CalendarEntry.release_at >= now - timedelta(days=3),
                                CalendarEntry.release_at <= now + timedelta(days=8),
                            )
                            .order_by(CalendarEntry.release_at)
                        )
                    ).scalars().all()
                    if not entries:
                        return await message.reply(
                            f"📅 {anime.title} (n°{anime_id}) : aucune sortie au calendrier pour le moment.\n"
                            "Si l'animé devrait y être, vérifie que son nom correspond (/alias)."
                        )
                    lines = [f"🔎 {anime.title} (n°{anime_id})", ""]
                    for e in entries:
                        status = await _status(db, e, anime_id)
                        lines.append(
                            f"• {e.language} · {cal.season_label(e.season_raw)} · Ép. {e.episode_number} · "
                            f"{_when(e)} → {cal.state_text(status)}"
                        )
                else:
                    entries = (
                        await db.execute(
                            select(CalendarEntry)
                            .where(CalendarEntry.release_at >= now - timedelta(hours=24), CalendarEntry.release_at <= now)
                            .order_by(CalendarEntry.release_at)
                        )
                    ).scalars().all()
                    pending, done = [], 0
                    for e in entries:
                        if e.anime_id is None:
                            pending.append(
                                f"• {e.title} · {e.language} · {cal.season_label(e.season_raw)} · Ép. {e.episode_number} · "
                                f"{_when(e)} → 🆔 pas dans le catalogue (/ajouter {e.title})"
                            )
                            continue
                        status = await _status(db, e, e.anime_id)
                        if status["state"] == "published":
                            done += 1
                            continue
                        pending.append(
                            f"• n°{e.anime_id} {e.title} · {e.language} · {cal.season_label(e.season_raw)} · "
                            f"Ép. {e.episode_number} · {_when(e)} → {cal.state_text(status)}"
                        )
                    lines = [f"📋 Sorties des dernières 24 h : {len(entries)} · déjà publiées : {done}", ""]
                    lines += pending or ["Tout est publié 🎉" if entries else "Aucune sortie dans les dernières 24 h."]
            await message.reply("\n".join(lines)[:4000])
        except Exception as exc:  # noqa: BLE001
            logger.exception("/check en échec")
            await message.reply(f"❌ Erreur : {exc}")

    @bot.on_message(filters.private & filters.command("calsync"))
    async def cmd_calsync(client: Client, message: Message):
        if not message.from_user or not is_admin(message.from_user.id):
            return
        wait = await message.reply("⏳ Lecture du calendrier FRAnime...")
        try:
            res = await cal.sync_calendar()
        except Exception as exc:  # noqa: BLE001
            logger.exception("/calsync en échec")
            return await wait.edit_text(f"❌ Erreur : {exc}")
        if res.get("ok"):
            await wait.edit_text(
                f"✅ {res['total']} sorties lues · {res['new']} nouvelles · "
                f"{res['updated']} mises à jour · {res['linked']} reliées à un animé du site."
            )
        else:
            extra = ""
            if "page_size" in res:
                extra = f"\nTaille de la page : {res['page_size']} octets · liens d'épisodes trouvés : {'oui' if res['has_anime_links'] else 'non'}"
            await wait.edit_text(f"❌ {res.get('error')}{extra}")

    @bot.on_callback_query(filters.regex(r"^cal:chk:\d+$"))
    async def cb_check(client: Client, query: CallbackQuery):
        if not is_admin(query.from_user.id):
            return await query.answer("Accès non autorisé.", show_alert=True)
        entry_id = int(query.data.split(":")[2])
        try:
            async with async_session() as db:
                entry = await db.get(CalendarEntry, entry_id)
                if not entry:
                    return await query.answer("Sortie introuvable (supprimée du calendrier).", show_alert=True)
                anime_id = entry.anime_id or (await cal.find_anime(db, entry.title))[0]
                if anime_id is None:
                    return await query.answer(
                        f"Pas de correspondance exacte dans le catalogue : /ajouter {entry.title}"[:190], show_alert=True
                    )
                status = await _status(db, entry, anime_id)
            await query.answer(cal.state_text(status)[:190], show_alert=True)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Bouton de vérification en échec")
            await query.answer(f"Erreur : {exc}"[:190], show_alert=True)
