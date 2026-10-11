"""/thumbsr2 : envoie sur Cloudflare R2 les vignettes d'épisodes qui sont encore dans le canal Telegram.

  /thumbsr2          lance la migration (en tâche de fond : tu peux continuer à utiliser le bot)
  /thumbsr2 etat     vignettes déjà sur R2 / restantes
  /thumbsr2 stop     arrête après la vignette en cours

Les nouvelles vignettes partent sur R2 toute seules à l'upload, et les anciennes y partent aussi à la
première visite d'une page : cette commande sert juste à tout migrer d'un coup. Sans risque : tu peux la
relancer, elle ne retraite que ce qui reste, et les vignettes restent dans Telegram.
"""

from __future__ import annotations

import asyncio
import logging

from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import Message
from sqlalchemy import func, or_, select

from bot.handlers.admin import is_admin
from config import settings
from database import async_session
from models import Episode
from services import thumbs

logger = logging.getLogger(__name__)

_running = False
_stop = False

NOT_CONFIGURED = (
    "R2 n'est pas configuré. Il faut sur le serveur : R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME, "
    "R2_ENDPOINT_URL et R2_PUBLIC_URL (et boto3 installé)."
)


async def _counts() -> tuple[int, int]:
    """-> (vignettes déjà sur R2, vignettes restantes dans Telegram)."""
    base = thumbs.public_base() + "/"
    async with async_session() as db:
        has_thumb = Episode.thumb_msg_id.is_not(None)
        done = (
            await db.execute(select(func.count()).select_from(Episode).where(has_thumb, Episode.thumbnail_url.startswith(base)))
        ).scalar() or 0
        todo = (
            await db.execute(
                select(func.count())
                .select_from(Episode)
                .where(has_thumb, or_(Episode.thumbnail_url.is_(None), ~Episode.thumbnail_url.startswith(base)))
            )
        ).scalar() or 0
    return done, todo


async def _todo_list() -> list[tuple[int, int]]:
    base = thumbs.public_base() + "/"
    async with async_session() as db:
        rows = await db.execute(
            select(Episode.id, Episode.thumb_msg_id)
            .where(
                Episode.thumb_msg_id.is_not(None),
                or_(Episode.thumbnail_url.is_(None), ~Episode.thumbnail_url.startswith(base)),
            )
            .order_by(Episode.id)
        )
        return [(r[0], r[1]) for r in rows.all()]


async def _migrate(client: Client, chat_id: int, todo: list[tuple[int, int]]) -> None:
    global _running, _stop
    ok = fail = 0
    try:
        for i, (ep_id, msg_id) in enumerate(todo, 1):
            if _stop:
                break
            done_this = False
            for _attempt in range(3):
                try:
                    msg = await client.get_messages(settings.TELEGRAM_CHANNEL_ID, msg_id)
                    if not msg or not msg.photo:
                        break  # message supprimé du canal : rien à migrer
                    buf = await client.download_media(msg, in_memory=True)
                    done_this = await thumbs.migrate_one(ep_id, buf.getvalue(), msg_id)
                    break
                except FloodWait as exc:
                    await asyncio.sleep(int(getattr(exc, "value", 10) or 10) + 1)
                except Exception:  # noqa: BLE001
                    logger.warning("migration R2 : épisode %s en échec", ep_id, exc_info=True)
                    break
            ok += 1 if done_this else 0
            fail += 0 if done_this else 1
            await asyncio.sleep(0.4)  # ménage Telegram et le serveur
            if i % 50 == 0:
                try:
                    await client.send_message(chat_id, f"⏳ Migration R2 : {i}/{len(todo)} traitées ({ok} ok, {fail} ignorées).")
                except Exception:  # noqa: BLE001
                    pass
        text = f"✅ Migration R2 terminée : {ok} vignette(s) migrée(s), {fail} ignorée(s) (message absent du canal ou erreur)."
        if _stop:
            text = f"⏹ Migration R2 arrêtée : {ok} migrée(s), {fail} ignorée(s)."
    finally:
        _running = False
        _stop = False
    try:
        await client.send_message(chat_id, text)
    except Exception:  # noqa: BLE001
        logger.warning("message de fin de migration non envoyé", exc_info=True)


def register(bot: Client):

    @bot.on_message(filters.private & filters.command(["thumbsr2", "vignettesr2"]))
    async def cmd_thumbsr2(client: Client, message: Message):
        global _running, _stop
        if not message.from_user or not is_admin(message.from_user.id):
            return
        if not thumbs.enabled():
            return await message.reply(NOT_CONFIGURED)

        arg = (message.command[1].lower() if len(message.command) > 1 else "")
        if arg in ("etat", "état", "status", "statut"):
            done, todo = await _counts()
            state = "en cours" if _running else "à l'arrêt"
            return await message.reply(f"🖼 Vignettes sur R2 : {done}\nRestantes dans Telegram : {todo}\nMigration : {state}")
        if arg == "stop":
            if not _running:
                return await message.reply("Aucune migration en cours.")
            _stop = True
            return await message.reply("⏹ Arrêt demandé : je m'arrête après la vignette en cours.")
        if _running:
            return await message.reply("Une migration est déjà en cours. /thumbsr2 etat pour la suivre.")

        todo = await _todo_list()
        if not todo:
            return await message.reply("✅ Toutes les vignettes sont déjà sur R2.")
        _running, _stop = True, False
        await message.reply(f"🚀 Migration lancée : {len(todo)} vignette(s). Tu recevras un point tous les 50 et un message à la fin.")
        asyncio.create_task(_migrate(client, message.chat.id, todo))
