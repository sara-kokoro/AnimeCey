"""/sorties : sorties de films et séries lues sur TMDB (voir services/tmdb_releases.py).

  /sorties            les sorties des 14 prochains jours (enregistrées dans la base)
  /sorties 30         les 30 prochains jours (jusqu'à 90)
  /sorties etat       dernière lecture, prochaine lecture, nombre de sorties en mémoire
  /sorties maj        relit TMDB maintenant (refusé si la dernière lecture date de moins de 12 h ;
                      « /sorties maj force » passe outre)

L'alerte part toute seule le jour de la sortie : rien à faire.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from pyrogram import Client, filters
from pyrogram.types import Message
from sqlalchemy import func, select

from bot.handlers.admin import is_admin, split_message
from database import async_session
from models_calendar import TmdbRelease
from services import tmdb_releases as rel

logger = logging.getLogger(__name__)


def _line(r: TmdbRelease) -> str:
    if r.kind == "episode":
        what = f"S{r.season_number:02d}E{r.episode_number:02d}"
    else:
        what = rel.KIND_LABEL[r.kind]
    where = f"n°{r.anime_id}" if r.anime_id else f"{'movie' if r.media == 'movie' else 'tv'}:{r.tmdb_id}"
    mark = "🔔" if r.notified_at else "•"
    return f"{mark} {r.release_date:%d/%m} · {what} · {r.title} ({where})"


def register(bot: Client):

    @bot.on_message(filters.private & filters.command("sorties"))
    async def cmd_sorties(client: Client, message: Message):
        if not message.from_user or not is_admin(message.from_user.id):
            return
        args = [a.lower() for a in message.command[1:]]
        now = datetime.now(timezone.utc)

        if args and args[0] in ("etat", "état", "status"):
            last_ok, nxt = await rel._get_state("tmdb_rel_ok"), await rel.next_sync_at()
            async with async_session() as db:
                total = (await db.execute(select(func.count()).select_from(TmdbRelease))).scalar_one()
                waiting = (
                    await db.execute(
                        select(func.count()).select_from(TmdbRelease).where(
                            TmdbRelease.notified_at.is_(None), TmdbRelease.release_date >= now.date()
                        )
                    )
                ).scalar_one()
            return await message.reply(
                "📡 Sorties TMDB\n"
                + (f"• Dernière lecture : {last_ok:%d/%m/%Y %H:%M} UTC\n" if last_ok else "• Jamais lu pour l'instant\n")
                + f"• Prochaine lecture : {max(nxt, now):%d/%m/%Y %H:%M} UTC (tous les {rel.INTERVAL_DAYS} jours)\n"
                f"• {total} sortie(s) en mémoire, {waiting} à venir sans alerte envoyée\n"
                f"• Alerte le jour J à partir de {rel.ALERT_HOUR_UTC} h UTC"
                + ("" if rel.ENABLED else "\n⚠️ Désactivé (TMDB_RELEASES_ENABLED=false)")
            )

        if args and args[0] in ("maj", "sync", "update"):
            last_ok = await rel._get_state("tmdb_rel_ok")
            if last_ok and now - last_ok < timedelta(hours=12) and "force" not in args:
                return await message.reply(
                    f"Dernière lecture il y a {int((now - last_ok).total_seconds() // 3600)} h : inutile de déranger TMDB. "
                    "« /sorties maj force » pour relire quand même."
                )
            status = await message.reply("⏳ Lecture de TMDB…")
            res = await rel.sync_releases()
            if not res.get("ok"):
                return await status.edit_text(f"❌ {res.get('error')}")
            return await status.edit_text(
                f"✅ Lu : {res['movies']} films, {res['premieres']} nouvelles séries, {res['episodes']} épisodes de séries du catalogue "
                f"({res['new']} nouvelles sorties, {res['updated']} mises à jour). /sorties pour la liste."
            )

        days = 14
        if args and args[0].isdigit():
            days = min(90, max(1, int(args[0])))
        today = now.date()
        async with async_session() as db:
            rows = (
                await db.execute(
                    select(TmdbRelease)
                    .where(TmdbRelease.release_date >= today, TmdbRelease.release_date <= today + timedelta(days=days))
                    .order_by(TmdbRelease.release_date, TmdbRelease.popularity.desc())
                )
            ).scalars().all()
        if not rows:
            return await message.reply(
                f"Aucune sortie enregistrée pour les {days} prochains jours.\n"
                "La lecture se fait toute seule tous les 3 jours ; /sorties maj pour la lancer maintenant."
            )
        head = f"🎬 Sorties TMDB des {days} prochains jours ({len(rows)}) — 🔔 = alerte déjà envoyée\n"
        text = head + "\n" + "\n".join(_line(r) for r in rows[:120])
        for part in split_message(text):
            await message.reply(part, disable_web_page_preview=True)
