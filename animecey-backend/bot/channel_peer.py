"""Rend le canal de stockage Telegram « connu » du bot après chaque démarrage.

Pourquoi : le client Pyrogram tourne avec ``in_memory=True``, donc son cache de
peers est vide à chaque redémarrage. Un bot ne peut pas retrouver seul
l'``access_hash`` d'un canal : sans lui, Telegram répond CHANNEL_INVALID.

Solution : l'access_hash du canal est gardé dans la base Neon (table ``app_kv``)
et réinjecté automatiquement à chaque démarrage. Aucune action manuelle après
la toute première fois : il suffit qu'un message arrive une fois dans le canal.
(``TELEGRAM_CHANNEL_ACCESS_HASH`` reste utilisable comme valeur de secours.)
"""

from __future__ import annotations

import logging

from pyrogram import Client, filters, raw
from sqlalchemy import text

from config import settings
from database import async_session

logger = logging.getLogger("animecey.channel_peer")


_KV_KEY = "telegram_channel_access_hash"


async def _kv_get() -> str:
    try:
        async with async_session() as db:
            await db.execute(text(
                "CREATE TABLE IF NOT EXISTS app_kv (key VARCHAR(100) PRIMARY KEY, value TEXT NOT NULL)"
            ))
            row = (await db.execute(text("SELECT value FROM app_kv WHERE key = :k"), {"k": _KV_KEY})).first()
            await db.commit()
            return row[0] if row else ""
    except Exception as exc:  # noqa: BLE001
        logger.error("Lecture de l'access_hash en base impossible : %s", exc)
        return ""


async def _kv_set(value: str) -> None:
    try:
        async with async_session() as db:
            await db.execute(text(
                "CREATE TABLE IF NOT EXISTS app_kv (key VARCHAR(100) PRIMARY KEY, value TEXT NOT NULL)"
            ))
            await db.execute(
                text(
                    "INSERT INTO app_kv (key, value) VALUES (:k, :v) "
                    "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"
                ),
                {"k": _KV_KEY, "v": value},
            )
            await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.error("Sauvegarde de l'access_hash en base impossible : %s", exc)


def _raw_channel_id() -> int:
    # -1003340962000 -> 3340962000
    return abs(settings.TELEGRAM_CHANNEL_ID) - 10**12


async def _inject_from_hash(bot: Client, access_hash: int) -> None:
    """Demande le canal à Telegram avec le vrai access_hash puis le met en cache."""
    res = await bot.invoke(
        raw.functions.channels.GetChannels(
            id=[raw.types.InputChannel(channel_id=_raw_channel_id(), access_hash=access_hash)]
        )
    )
    await bot.fetch_peers(res.chats)


async def ensure_channel_peer(bot: Client) -> bool:
    """À appeler juste après ``bot.start()``. Renvoie True si le canal est utilisable."""
    # 1) Déjà connu ? (cas où le cache a été rempli par une mise à jour)
    try:
        await bot.resolve_peer(settings.TELEGRAM_CHANNEL_ID)
        logger.info("Canal %s déjà connu du bot.", settings.TELEGRAM_CHANNEL_ID)
        return True
    except Exception:  # noqa: BLE001
        pass

    # 2) Réinjection : base Neon d'abord, puis variable d'environnement en secours
    candidates = [h for h in ((await _kv_get()).strip(), (settings.TELEGRAM_CHANNEL_ACCESS_HASH or "").strip()) if h]
    if not candidates:
        logger.warning(
            "Canal %s inconnu du bot et aucun access_hash enregistré : "
            "poste un message dans le canal, il sera mémorisé automatiquement.",
            settings.TELEGRAM_CHANNEL_ID,
        )
        return False
    for raw_hash in candidates:
        try:
            await _inject_from_hash(bot, int(raw_hash))
            await bot.resolve_peer(settings.TELEGRAM_CHANNEL_ID)
            logger.info("Canal %s réinjecté dans le cache du bot.", settings.TELEGRAM_CHANNEL_ID)
            await _kv_set(raw_hash)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("Réinjection du canal impossible avec cet access_hash : %s", exc)
    return False


def register_channel_logger(bot: Client) -> None:
    """Quand un message arrive du canal, mémorise son access_hash en base (auto-réparation)."""

    @bot.on_message(filters.channel & filters.chat(settings.TELEGRAM_CHANNEL_ID), group=-5)
    async def _log_hash(client: Client, message):  # noqa: ANN001
        try:
            peer = await client.resolve_peer(message.chat.id)
            await _kv_set(str(peer.access_hash))
            logger.info("Canal reconnu : access_hash mémorisé en base.")
        except Exception as exc:  # noqa: BLE001
            logger.error("Impossible de lire l'access_hash du canal : %s", exc)
        message.continue_propagation()
