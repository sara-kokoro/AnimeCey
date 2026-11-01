"""/stats : les chiffres de Magi-Stream (appareils, lectures, titres les plus vus, pubs).

  /stats           les 7 derniers jours
  /stats 1         les dernières 24 h  (ou /stats 30 pour 30 jours)
  /stats tout      depuis le début du suivi

Les lectures et les appareils sont comptés depuis la mise en ligne du suivi (aucun historique avant).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from pyrogram import Client, filters
from pyrogram.types import Message
from sqlalchemy import case, func, select

from bot.handlers.admin import is_admin
from database import async_session
from models import Anime, AnimeType, Episode, User
from models_ads import AdCampaign, Device, ViewEvent

logger = logging.getLogger(__name__)

GROUPS = [
    ("🎌 Animés (séries)", "anime", AnimeType.serie),
    ("🎞 Films d'animation", "anime", AnimeType.film),
    ("🎬 Films", "live", AnimeType.film),
    ("📺 Séries", "live", AnimeType.serie),
]


async def _top(db, since, category, type_, limit=5):
    q = (
        select(Anime.id, Anime.title, func.count(ViewEvent.id).label("n"))
        .join(Anime, Anime.id == ViewEvent.anime_id)
        .where(Anime.category == category, Anime.type == type_)
    )
    if since:
        q = q.where(ViewEvent.created_at >= since)
    rows = (await db.execute(q.group_by(Anime.id, Anime.title).order_by(func.count(ViewEvent.id).desc()).limit(limit))).all()
    return rows


async def build_stats(days: int | None) -> str:
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days) if days else None
    label = "depuis le début du suivi" if days is None else (f"{days} dernier{'s' if days > 1 else ''} jour{'s' if days > 1 else ''}")
    d1, d7, d30 = (now - timedelta(days=n) for n in (1, 7, 30))
    out = [f"📊 Stats Magi-Stream — {label}", ""]
    async with async_session() as db:
        # appareils
        rows = (
            await db.execute(
                select(
                    Device.platform,
                    func.count(),
                    func.sum(case((Device.last_seen >= d1, 1), else_=0)),
                    func.sum(case((Device.last_seen >= d7, 1), else_=0)),
                    func.sum(case((Device.last_seen >= d30, 1), else_=0)),
                ).group_by(Device.platform)
            )
        ).all()
        by = {r[0]: r for r in rows}
        out.append("👥 PERSONNES (appareils distincts)")
        for plat, name in (("app", "📱 Application"), ("web", "🌐 Site web")):
            r = by.get(plat)
            if r:
                out.append(f"{name} : {r[1]} au total · {r[2] or 0} actifs 24 h · {r[3] or 0} sur 7 j · {r[4] or 0} sur 30 j")
            else:
                out.append(f"{name} : aucun appareil pour l'instant")
        # lectures
        total = (await db.execute(select(func.count()).select_from(ViewEvent))).scalar() or 0
        views = (
            await db.execute(
                select(
                    func.sum(case((ViewEvent.created_at >= d1, 1), else_=0)),
                    func.sum(case((ViewEvent.created_at >= d7, 1), else_=0)),
                    func.sum(case((ViewEvent.created_at >= d30, 1), else_=0)),
                )
            )
        ).one()
        out += ["", f"▶️ LECTURES (épisodes ouverts) : {views[0] or 0} en 24 h · {views[1] or 0} sur 7 j · {views[2] or 0} sur 30 j · {total} au total"]
        # top
        for title, cat, typ in GROUPS:
            top = await _top(db, since, cat, typ)
            if not top:
                continue
            out += ["", f"{title} les plus vus :"]
            out += [f"{i}. {r.title} — {r.n}" for i, r in enumerate(top, 1)]
        # catalogue
        n_anime = (await db.execute(select(func.count()).select_from(Anime))).scalar() or 0
        n_ep = (await db.execute(select(func.count()).select_from(Episode))).scalar() or 0
        n_users = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
        out += ["", f"📚 CATALOGUE : {n_anime} titres · {n_ep} épisodes · {n_users} comptes inscrits"]
        # pubs
        ads = (await db.execute(select(AdCampaign).order_by(AdCampaign.ends_at.desc()).limit(10))).scalars().all()
        out += ["", "📣 PUBS"]
        if not ads:
            out.append("Aucune pub créée (/pub).")
        for a in ads:
            live = a.active and a.starts_at <= now < a.ends_at
            ctr = f"{100 * a.clicks / a.views:.1f} %" if a.views else "—"
            out.append(f"#{a.id} {a.advertiser or 'sans nom'} {'🟢' if live else '⚪'} : {a.views} vues · {a.clicks} clics · {ctr}")
        total_views = sum(a.views for a in ads)
        total_clicks = sum(a.clicks for a in ads)
        out.append(f"Total : {total_views} vues · {total_clicks} clics")
    return "\n".join(out)


def register(bot: Client):

    @bot.on_message(filters.private & filters.command("stats"))
    async def cmd_stats(client: Client, message: Message):
        if not message.from_user or not is_admin(message.from_user.id):
            return
        arg = (message.command[1] if len(message.command) > 1 else "7").lower()
        days: int | None
        if arg in ("tout", "all", "total"):
            days = None
        elif arg.isdigit() and 1 <= int(arg) <= 365:
            days = int(arg)
        else:
            return await message.reply("Usage : /stats · /stats 1 · /stats 30 · /stats tout")
        try:
            text = await build_stats(days)
        except Exception as exc:  # noqa: BLE001
            logger.exception("/stats en échec")
            return await message.reply(f"❌ Erreur : {exc}")
        await message.reply(text[:4000])
