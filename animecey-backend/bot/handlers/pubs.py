"""/pub : créer une pub vendue à la main ; /pubs : la liste, avec vues, clics, et boutons Arrêter / Supprimer.

  /pub     le bot te demande, une étape à la fois : image ou GIF, lien, annonceur, texte (facultatif),
           bouton (facultatif, avec son lien), emplacements (un, plusieurs ou tous), durée en jours.
  /pubs    toutes les pubs (en cours en premier)
  /cancel  abandonne la création en cours

La pub apparaît tout de suite sur le site et dans l'application, jusqu'à la fin de la durée choisie.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select

from bot.handlers.admin import is_admin
from database import async_session
from models_ads import AD_SLOTS, AdCampaign

logger = logging.getLogger(__name__)

MAX_BYTES = 8 * 1024 * 1024
OK_MIME = ("image/jpeg", "image/png", "image/webp", "image/gif", "video/mp4")

# admin Telegram -> état de la création en cours
_flows: dict[int, dict] = {}


def _in_flow_filter(_, __, m: Message) -> bool:
    return bool(m.from_user and m.from_user.id in _flows)


in_flow = filters.create(_in_flow_filter)


def _slots_markup(selected: set[str]) -> InlineKeyboardMarkup:
    rows = []
    for key, label in AD_SLOTS.items():
        rows.append([InlineKeyboardButton(("✅ " if key in selected else "▫️ ") + label, callback_data=f"pub:slot:{key}")])
    rows.append([InlineKeyboardButton(("✅ " if "all" in selected else "▫️ ") + "TOUS les emplacements", callback_data="pub:slot:all")])
    rows.append([InlineKeyboardButton("➡️ Continuer", callback_data="pub:slots_ok")])
    return InlineKeyboardMarkup(rows)


def _days_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(f"{d} j", callback_data=f"pub:days:{d}") for d in (3, 7, 14, 30)]]
    )


def _norm_url(text: str) -> str | None:
    text = text.strip()
    if re.match(r"^https?://\S+$", text, re.I):
        return text
    if re.match(r"^(t\.me|www\.)\S+$", text, re.I) or re.match(r"^[\w.-]+\.[a-z]{2,}(/\S*)?$", text, re.I):
        return "https://" + text
    return None


def _summary(flow: dict) -> str:
    places = flow.get("placements") or []
    where = "tous les emplacements" if "all" in places else ", ".join(AD_SLOTS[p] for p in places)
    return (
        f"Annonceur : {flow.get('advertiser') or '—'}\n"
        f"Lien : {flow['link']}\n"
        f"Texte : {flow.get('text') or '—'}\n"
        f"Bouton : {flow.get('button_text') or '—'}"
        + (f" → {flow['button_url']}" if flow.get("button_text") else "")
        + f"\nEmplacements : {where}"
    )


async def _create(flow: dict, days: int) -> AdCampaign:
    now = datetime.now(timezone.utc)
    ad = AdCampaign(
        advertiser=flow.get("advertiser"),
        media=flow["media"],
        mime=flow["mime"],
        link_url=flow["link"],
        text=flow.get("text"),
        button_text=flow.get("button_text"),
        button_url=flow.get("button_url"),
        placements=flow["placements"],
        starts_at=now,
        ends_at=now + timedelta(days=days),
        active=True,
    )
    async with async_session() as db:
        db.add(ad)
        await db.commit()
        await db.refresh(ad)
    return ad


def register(bot: Client):

    @bot.on_message(filters.private & filters.command("pub"))
    async def cmd_pub(client: Client, message: Message):
        if not message.from_user or not is_admin(message.from_user.id):
            return
        from bot.handlers import notification as _notif  # une seule création à la fois par admin

        _notif._flows.pop(message.from_user.id, None)
        _flows[message.from_user.id] = {"step": "media"}
        await message.reply(
            "📣 Nouvelle pub — étape 1/7\n"
            "Envoie l'image ou le GIF de la pub (photo, GIF/animation ou fichier, 8 Mo maximum).\n"
            "/cancel pour abandonner."
        )

    @bot.on_message(filters.private & filters.command("cancel") & in_flow, group=-6)
    async def cancel_flow(client: Client, message: Message):
        _flows.pop(message.from_user.id, None)
        await message.reply("Création annulée.")
        message.stop_propagation()

    @bot.on_message(filters.private & in_flow & ~filters.command(["cancel", "pub", "pubs", "notification", "stats"]), group=-5)
    async def flow_message(client: Client, message: Message):
        uid = message.from_user.id
        if not is_admin(uid):
            return
        flow = _flows[uid]
        step = flow["step"]
        text = (message.text or "").strip()

        if step == "media":
            media = message.photo or message.animation or message.video or message.document
            if not media:
                await message.reply("Envoie une image ou un GIF (pas du texte).")
                return message.stop_propagation()
            mime = "image/jpeg" if message.photo else (getattr(media, "mime_type", None) or "")
            if mime == "video/mpeg4" or (message.animation and not mime):
                mime = "video/mp4"
            if mime not in OK_MIME:
                await message.reply("Format non pris en charge. Envoie une photo, un GIF ou un MP4 court.")
                return message.stop_propagation()
            size = getattr(media, "file_size", 0) or 0
            if size > MAX_BYTES:
                await message.reply("Fichier trop lourd (8 Mo maximum). Compresse-le ou envoie-en un plus léger.")
                return message.stop_propagation()
            buf = await client.download_media(message, in_memory=True)
            data = buf.getvalue() if buf else b""
            if not data or len(data) > MAX_BYTES:
                await message.reply("Impossible de récupérer ce fichier. Réessaie.")
                return message.stop_propagation()
            flow.update(media=data, mime=mime, step="link")
            await message.reply("Étape 2/7 — Envoie le lien de la pub (https://…, t.me/…).")
        elif step == "link":
            url = _norm_url(text)
            if not url:
                await message.reply("Ce lien ne ressemble pas à une adresse. Exemple : https://exemple.com ou t.me/canal")
                return message.stop_propagation()
            flow.update(link=url, step="advertiser")
            await message.reply("Étape 3/7 — Nom de l'annonceur (pour tes stats). Envoie - pour passer.")
        elif step == "advertiser":
            flow.update(advertiser=None if text in ("", "-") else text[:120], step="text")
            await message.reply(
                "Étape 4/7 — Texte sous l'image (facultatif, 400 caractères max). Il s'affiche dans une citation. Envoie - pour passer."
            )
        elif step == "text":
            flow.update(text=None if text in ("", "-") else text[:400], step="button")
            await message.reply("Étape 5/7 — Texte du bouton (ex. Rejoindre). Envoie - pour aucun bouton.")
        elif step == "button":
            if text in ("", "-"):
                flow.update(button_text=None, button_url=None, step="slots", placements=[])
                await message.reply("Étape 6/7 — Où afficher la pub ? Coche un ou plusieurs emplacements :", reply_markup=_slots_markup(set()))
            else:
                flow.update(button_text=text[:40], step="button_url")
                await message.reply("Lien du bouton ? Envoie - pour utiliser le même lien que la pub.")
        elif step == "button_url":
            if text in ("", "-"):
                flow["button_url"] = flow["link"]
            else:
                url = _norm_url(text)
                if not url:
                    await message.reply("Ce lien ne ressemble pas à une adresse. Réessaie, ou envoie - pour le même lien.")
                    return message.stop_propagation()
                flow["button_url"] = url
            flow.update(step="slots", placements=[])
            await message.reply("Étape 6/7 — Où afficher la pub ? Coche un ou plusieurs emplacements :", reply_markup=_slots_markup(set()))
        elif step == "slots":
            await message.reply("Utilise les boutons ci-dessus pour choisir les emplacements, puis « Continuer ».")
        elif step == "days":
            if not re.fullmatch(r"\d{1,3}", text) or int(text) < 1:
                await message.reply("Envoie un nombre de jours (ex. 7), ou touche un bouton.")
                return message.stop_propagation()
            ad = await _create(flow, int(text))
            _flows.pop(uid, None)
            await message.reply(_done_text(ad))
        message.stop_propagation()

    def _done_text(ad: AdCampaign) -> str:
        return (
            f"✅ Pub #{ad.id} en ligne sur le site et l'application jusqu'au {ad.ends_at.strftime('%d/%m/%Y %H:%M')} UTC.\n"
            "/pubs pour voir les vues et les clics."
        )

    @bot.on_callback_query(filters.regex(r"^pub:"))
    async def pub_callbacks(client: Client, cq: CallbackQuery):
        uid = cq.from_user.id
        if not is_admin(uid):
            return await cq.answer()
        flow = _flows.get(uid)
        if not flow:
            return await cq.answer("Cette création est terminée ou annulée.", show_alert=True)
        parts = cq.data.split(":")
        action = parts[1]
        if action == "slot" and flow.get("step") == "slots":
            key = parts[2]
            chosen: list = flow["placements"]
            if key == "all":
                flow["placements"] = [] if "all" in chosen else ["all"]
            elif key in AD_SLOTS:
                chosen = [c for c in chosen if c != "all"]
                flow["placements"] = [c for c in chosen if c != key] if key in chosen else chosen + [key]
            await cq.message.edit_reply_markup(_slots_markup(set(flow["placements"])))
            return await cq.answer()
        if action == "slots_ok" and flow.get("step") == "slots":
            if not flow["placements"]:
                return await cq.answer("Choisis au moins un emplacement.", show_alert=True)
            flow["step"] = "days"
            await cq.message.reply(
                "Étape 7/7 — Combien de jours la pub reste-t-elle affichée ? Touche un bouton ou envoie un nombre.\n\n" + _summary(flow),
                reply_markup=_days_markup(),
            )
            return await cq.answer()
        if action == "days" and flow.get("step") == "days":
            ad = await _create(flow, int(parts[2]))
            _flows.pop(uid, None)
            await cq.message.reply(_done_text(ad))
            return await cq.answer("Pub créée")
        await cq.answer()

    # ── /pubs ──────────────────────────────────────────────────────────

    def _ad_text(ad: AdCampaign, now: datetime) -> str:
        left = ad.ends_at - now
        if not ad.active:
            state = "⏸ arrêtée"
        elif left.total_seconds() <= 0:
            state = "⌛ terminée"
        else:
            state = f"🟢 en cours · {left.days} j {left.seconds // 3600} h restants"
        places = ad.placements or []
        where = "tous" if "all" in places else ", ".join(AD_SLOTS.get(p, p) for p in places)
        ctr = f"{100 * ad.clicks / ad.views:.1f} %" if ad.views else "—"
        return (
            f"#{ad.id} · {ad.advertiser or 'sans nom'} · {state}\n"
            f"👁 {ad.views} vues · 👆 {ad.clicks} clics · taux {ctr}\n"
            f"📍 {where}\n🔗 {ad.link_url}"
        )

    def _ad_markup(ad: AdCampaign) -> InlineKeyboardMarkup:
        toggle = "⏸ Arrêter" if ad.active else "▶️ Reprendre"
        return InlineKeyboardMarkup(
            [[InlineKeyboardButton(toggle, callback_data=f"pubs:toggle:{ad.id}"),
              InlineKeyboardButton("🗑 Supprimer", callback_data=f"pubs:del:{ad.id}")]]
        )

    @bot.on_message(filters.private & filters.command("pubs"))
    async def cmd_pubs(client: Client, message: Message):
        if not message.from_user or not is_admin(message.from_user.id):
            return
        now = datetime.now(timezone.utc)
        async with async_session() as db:
            ads = (await db.execute(select(AdCampaign).order_by(AdCampaign.ends_at.desc()).limit(15))).scalars().all()
        if not ads:
            return await message.reply("Aucune pub pour le moment. /pub pour en créer une.")
        live = sorted((a for a in ads if a.active and a.ends_at > now), key=lambda a: a.ends_at)
        rest = [a for a in ads if a not in live]
        for ad in live + rest:
            await message.reply(_ad_text(ad, now), reply_markup=_ad_markup(ad), disable_web_page_preview=True)

    @bot.on_callback_query(filters.regex(r"^pubs:"))
    async def pubs_callbacks(client: Client, cq: CallbackQuery):
        if not is_admin(cq.from_user.id):
            return await cq.answer()
        _, action, sid = cq.data.split(":")
        async with async_session() as db:
            ad = (await db.execute(select(AdCampaign).where(AdCampaign.id == int(sid)))).scalar_one_or_none()
            if not ad:
                await cq.message.edit_text("Cette pub n'existe plus.")
                return await cq.answer()
            if action == "toggle":
                ad.active = not ad.active
                await db.commit()
                await db.refresh(ad)
                await cq.message.edit_text(_ad_text(ad, datetime.now(timezone.utc)), reply_markup=_ad_markup(ad), disable_web_page_preview=True)
                return await cq.answer("Arrêtée" if not ad.active else "Reprise")
            if action == "del":
                await db.delete(ad)
                await db.commit()
                await cq.message.edit_text(f"🗑 Pub #{sid} supprimée.")
                return await cq.answer()
        await cq.answer()
