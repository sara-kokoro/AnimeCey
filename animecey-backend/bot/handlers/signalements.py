"""/signalements : liste des problèmes signalés par les visiteurs du site + boutons Résolu / Ignorer.

Les nouveaux signalements arrivent tout seuls dans ce chat (envoyés par services/report_notify.py).
  /signalements        les 10 signalements ouverts les plus répétés
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.errors import MessageNotModified
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import func, select

from bot.handlers.admin import is_admin
from database import async_session
from models_reports import Report
from services import report_notify

logger = logging.getLogger(__name__)


def _markup(rows: list[list[dict]]) -> InlineKeyboardMarkup | None:
    if not rows:
        return None
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(b["text"], callback_data=b.get("callback_data"), url=b.get("url")) for b in row] for row in rows]
    )


def register(bot: Client):

    @bot.on_message(filters.private & filters.command(["signalements", "reports"]))
    async def cmd_signalements(client: Client, message: Message):
        if not message.from_user or not is_admin(message.from_user.id):
            return
        async with async_session() as db:
            total = (
                await db.execute(select(func.count()).select_from(Report).where(Report.status == "open"))
            ).scalar() or 0
            rows = (
                await db.execute(
                    select(Report)
                    .where(Report.status == "open")
                    .order_by(Report.count.desc(), Report.id.desc())
                    .limit(10)
                )
            ).scalars().all()
        if not rows:
            return await message.reply("✅ Aucun signalement ouvert.")
        await message.reply(f"🚩 {total} signalement(s) ouvert(s) — voici les {len(rows)} les plus signalés :")
        for r in rows:
            text, kb = report_notify.render(r)
            await message.reply(
                text, parse_mode=ParseMode.HTML, disable_web_page_preview=True, reply_markup=_markup(kb)
            )

    @bot.on_callback_query(filters.regex(r"^rpt:"))
    async def cb_signalement(client: Client, query: CallbackQuery):
        if not is_admin(query.from_user.id):
            return await query.answer("Accès non autorisé.", show_alert=True)
        _, action, raw_id = query.data.split(":")
        status = "resolved" if action == "res" else "ignored"
        async with async_session() as db:
            r = await db.get(Report, int(raw_id))
            if r is None:
                return await query.answer("Signalement introuvable.", show_alert=True)
            r.status = status
            r.resolved_at = datetime.now(timezone.utc)
            await db.commit()
            await db.refresh(r)
            text, kb = report_notify.render(r)
        try:
            await query.message.edit_text(
                text, parse_mode=ParseMode.HTML, disable_web_page_preview=True, reply_markup=_markup(kb)
            )
        except MessageNotModified:
            pass
        await query.answer("✅ Marqué comme résolu" if status == "resolved" else "🚫 Ignoré")
        try:  # met à jour les copies reçues par les autres admins
            await report_notify.notify(r.id, ping=False)
        except Exception:  # noqa: BLE001
            logger.warning("synchro des messages du signalement %s impossible", raw_id, exc_info=True)
