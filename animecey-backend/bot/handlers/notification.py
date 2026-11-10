"""/notification : envoie une notification à tous les utilisateurs de l'application.

  /notification   le bot demande, une étape à la fois : image (facultative), titre, texte, page ouverte au clic
                  (accueil, téléchargements, catalogue, calendrier, don, la fiche d'un animé par son numéro, ou un lien externe).

L'application récupère les nouvelles notifications toutes les ~15 minutes, même fermée.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta, timezone

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import func, select

from bot.handlers.admin import is_admin
from database import async_session
from models import Anime
from models_ads import APP_PAGES, AppNotification, Device
from services import fcm

logger = logging.getLogger(__name__)

_PATHS = {"home": "/", "downloads": "/telechargements", "catalogue": "/catalogue", "calendar": "/calendrier", "donate": "/don"}
_flows: dict[int, dict] = {}


def _norm_url(text: str) -> str | None:
    """Lien externe : https://…, t.me/…, x.com/…, ou tout autre site (https:// ajouté si absent)."""
    text = text.strip()
    if re.match(r"^https?://\S+$", text, re.I):
        return text[:1000]
    if re.match(r"^(t\.me|www\.)\S+$", text, re.I) or re.match(r"^[\w.-]+\.[a-z]{2,}(/\S*)?$", text, re.I):
        return ("https://" + text)[:1000]
    return None


def _in_flow_filter(_, __, m: Message) -> bool:
    return bool(m.from_user and m.from_user.id in _flows)


in_flow = filters.create(_in_flow_filter)


def _pages_markup() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(label, callback_data=f"notif:page:{key}")] for key, label in APP_PAGES.items()]
    rows.append([InlineKeyboardButton("🎬 La fiche d'un animé / film / série", callback_data="notif:page:anime")])
    rows.append([InlineKeyboardButton("🔗 Un lien externe (Telegram, X, site…)", callback_data="notif:page:ext")])
    return InlineKeyboardMarkup(rows)


async def _finish(message: Message, flow: dict) -> None:
    async with async_session() as db:
        n = AppNotification(
            title=flow["title"], body=flow["body"], image=flow.get("image"), image_mime=flow.get("image_mime"), path=flow["path"]
        )
        db.add(n)
        await db.commit()
        await db.refresh(n)
        since = datetime.now(timezone.utc) - timedelta(days=30)
        devices = (
            await db.execute(select(func.count()).select_from(Device).where(Device.platform == "app", Device.last_seen >= since))
        ).scalar() or 0
    image_url = None
    if flow.get("image"):
        base = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
        image_url = f"{base}/api/app-notifications/{n.id}/image" if base else None
    sent, total = await fcm.send_app_notification(n.id, n.title, n.body, n.path, image_url)
    if sent:
        delivery = f"⚡ Envoyée par Firebase à {sent}/{total} téléphones (reçue en quelques secondes). Les autres l'auront sous ~15 minutes."
    elif fcm.is_enabled():
        delivery = f"Firebase : aucun téléphone enregistré pour l'instant. Les appareils l'affichent sous ~15 minutes (environ {devices} appareils actifs ces 30 derniers jours)."
    else:
        delivery = f"Les appareils de l'app l'affichent sous ~15 minutes (environ {devices} appareils actifs ces 30 derniers jours)."
    await message.reply(f"✅ Notification #{n.id} envoyée.\n{delivery}\nAu clic : {flow['path']}")


def register(bot: Client):

    @bot.on_message(filters.private & filters.command("notification"))
    async def cmd_notification(client: Client, message: Message):
        if not message.from_user or not is_admin(message.from_user.id):
            return
        from bot.handlers import pubs as _pubs  # une seule création à la fois par admin

        _pubs._flows.pop(message.from_user.id, None)
        _flows[message.from_user.id] = {"step": "image"}
        await message.reply(
            "🔔 Nouvelle notification pour l'app — étape 1/4\n"
            "Envoie une image (facultatif), ou - pour une notification sans image.\n/cancel pour abandonner."
        )

    @bot.on_message(filters.private & filters.command("cancel") & in_flow, group=-7)
    async def cancel_flow(client: Client, message: Message):
        _flows.pop(message.from_user.id, None)
        await message.reply("Notification annulée.")
        message.stop_propagation()

    @bot.on_message(filters.private & in_flow & ~filters.command(["cancel", "pub", "pubs", "notification", "stats"]), group=-4)
    async def flow_message(client: Client, message: Message):
        uid = message.from_user.id
        if not is_admin(uid):
            return
        flow = _flows[uid]
        step = flow["step"]
        text = (message.text or "").strip()

        if step == "image":
            if message.photo:
                buf = await client.download_media(message, in_memory=True)
                data = buf.getvalue() if buf else b""
                if not data or len(data) > 4 * 1024 * 1024:
                    await message.reply("Image illisible ou trop lourde (4 Mo max). Réessaie.")
                    return message.stop_propagation()
                flow.update(image=data, image_mime="image/jpeg", step="title")
            elif text == "-":
                flow.update(image=None, image_mime=None, step="title")
            else:
                await message.reply("Envoie une photo, ou - pour passer.")
                return message.stop_propagation()
            await message.reply("Étape 2/4 — Titre de la notification (120 caractères max).")
        elif step == "title":
            if not text:
                await message.reply("Envoie le titre en texte.")
                return message.stop_propagation()
            flow.update(title=text[:120], step="body")
            await message.reply("Étape 3/4 — Texte de la notification.")
        elif step == "body":
            if not text:
                await message.reply("Envoie le texte.")
                return message.stop_propagation()
            flow.update(body=text[:1000], step="page")
            await message.reply("Étape 4/4 — Où mène le clic sur la notification ?", reply_markup=_pages_markup())
        elif step == "anime_id":
            if not re.fullmatch(r"\d{1,9}", text):
                await message.reply("Envoie le numéro de l'animé (le même que pour /anime).")
                return message.stop_propagation()
            async with async_session() as db:
                anime = (await db.execute(select(Anime).where(Anime.id == int(text)))).scalar_one_or_none()
            if not anime:
                await message.reply("Aucun titre avec ce numéro. Réessaie.")
                return message.stop_propagation()
            flow["path"] = f"/anime/{anime.id}"
            _flows.pop(uid, None)
            await _finish(message, flow)
        elif step == "ext_url":
            url = _norm_url(text)
            if not url:
                await message.reply("Ce lien ne ressemble pas à une adresse. Exemple : https://t.me/MagiStream ou https://x.com/…")
                return message.stop_propagation()
            flow["path"] = url
            _flows.pop(uid, None)
            await _finish(message, flow)
        elif step == "page":
            await message.reply("Choisis une page avec les boutons ci-dessus.")
        message.stop_propagation()

    @bot.on_callback_query(filters.regex(r"^notif:"))
    async def notif_callbacks(client: Client, cq: CallbackQuery):
        uid = cq.from_user.id
        if not is_admin(uid):
            return await cq.answer()
        flow = _flows.get(uid)
        if not flow or flow.get("step") != "page":
            return await cq.answer("Cette notification est terminée ou annulée.", show_alert=True)
        key = cq.data.split(":")[2]
        if key == "anime":
            flow["step"] = "anime_id"
            await cq.message.reply("Envoie le numéro de l'animé / film / série (le même que pour /anime).")
            return await cq.answer()
        if key == "ext":
            flow["step"] = "ext_url"
            await cq.message.reply("Envoie le lien : https://t.me/MagiStream, t.me/…, https://x.com/…, ou tout autre site.")
            return await cq.answer()
        if key in _PATHS:
            flow["path"] = _PATHS[key]
            _flows.pop(uid, None)
            await _finish(cq.message, flow)
        await cq.answer()
