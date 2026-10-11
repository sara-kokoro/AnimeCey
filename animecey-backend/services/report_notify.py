"""Envoie les signalements du site aux admins Telegram (API HTTP des bots).

On passe par l'API HTTP et non par Pyrogram : l'API du site peut tourner sur un serveur où le bot
principal est désactivé (ENABLE_TELEGRAM_BOT=false). Les boutons (Résolu / Ignorer / Supprimer)
sont traités par le bot principal (bot/handlers/signalements.py et delep.py), avec le même jeton.
"""

from __future__ import annotations

import html
import logging

import httpx

from config import settings
from database import async_session
from models_reports import REPORT_KINDS, Report

logger = logging.getLogger(__name__)

_API = "https://api.telegram.org/bot{token}/{method}"
_STATUS_LINE = {"resolved": "✅ Résolu", "ignored": "🚫 Ignoré"}


def page_link(r: Report) -> str | None:
    if r.page_url and r.page_url.startswith(("http://", "https://")):
        return r.page_url
    base = settings.SITE_URL
    if r.episode_id:
        return f"{base}/watch/{r.episode_id}"
    if r.anime_id:
        return f"{base}/anime/{r.anime_id}"
    return None


def render(r: Report) -> tuple[str, list[list[dict]]]:
    """-> (texte HTML, clavier : liste de lignes de boutons {text, callback_data})."""
    lines = [f"🚩 <b>Signalement #{r.id}</b> — {html.escape(REPORT_KINDS.get(r.kind, r.kind))}"]
    if r.label:
        lines.append(f"📺 {html.escape(r.label)}")
    if r.message:
        lines.append(f"💬 « {html.escape(r.message[:400])} »")
    if r.contact:
        lines.append(f"✉️ {html.escape(r.contact)}")
    lines.append(f"👤 Utilisateur n°{r.user_id}" if r.user_id else "👤 Visiteur non inscrit")
    if (r.count or 1) > 1:
        lines.append(f"🔁 <b>{r.count}</b> signalements identiques")
    link = page_link(r)
    if link:
        lines.append(f"🔗 {html.escape(link)}")
    if r.status in _STATUS_LINE:
        lines.append("\n" + _STATUS_LINE[r.status])

    kb: list[list[dict]] = []
    if r.status == "open":
        kb.append(
            [
                {"text": "✅ Résolu", "callback_data": f"rpt:res:{r.id}"},
                {"text": "🚫 Ignorer", "callback_data": f"rpt:ign:{r.id}"},
            ]
        )
        if r.episode_id:
            kb.append([{"text": "🗑 Supprimer cet épisode", "callback_data": f"dep:ask:{r.episode_id}"}])
    return "\n".join(lines), kb


async def _call(method: str, payload: dict) -> dict | None:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return None
    try:
        async with httpx.AsyncClient(timeout=10) as http:
            resp = await http.post(_API.format(token=token, method=method), json=payload)
        data = resp.json()
    except Exception:  # noqa: BLE001
        logger.warning("Telegram %s : appel impossible", method, exc_info=True)
        return None
    if not data.get("ok"):
        # « message is not modified », admin qui n'a jamais lancé le bot... : sans gravité
        logger.info("Telegram %s refusé : %s", method, data.get("description"))
        return None
    return data.get("result")


async def notify(report_id: int, ping: bool = True) -> None:
    """ping=True : envoie un nouveau message à chaque admin. ping=False : met à jour les messages existants."""
    async with async_session() as db:
        r = await db.get(Report, report_id)
        if r is None:
            return
        text, kb = render(r)
        base = {"parse_mode": "HTML", "disable_web_page_preview": True, "reply_markup": {"inline_keyboard": kb}}
        sent = list(r.tg_messages or [])

        if ping or not sent:
            for admin_id in settings.TELEGRAM_ADMIN_IDS:
                res = await _call("sendMessage", {"chat_id": admin_id, "text": text, **base})
                if res and res.get("message_id"):
                    sent.append([admin_id, res["message_id"]])
            r.tg_messages = sent
            await db.commit()
            return

        for chat_id, message_id in sent:
            await _call("editMessageText", {"chat_id": chat_id, "message_id": message_id, "text": text, **base})
