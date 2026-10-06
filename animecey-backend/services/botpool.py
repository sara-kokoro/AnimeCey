"""Pool de bots Telegram pour le streaming vidéo.

Principe : le canal de stockage contient les vidéos ; plusieurs bots (tous admins du canal) les lisent
à tour de rôle. Chaque lecture est confiée au bot le moins occupé ; si un bot échoue (FLOOD_WAIT,
erreur Telegram), la lecture bascule automatiquement sur un autre AVANT d'envoyer la moindre donnée
au spectateur. Sans HELPER_BOT_TOKENS, c'est le bot principal qui sert la vidéo (comme avant).

Variables d'environnement :
  HELPER_BOT_TOKENS   jetons des bots d'aide, séparés par des virgules, espaces ou retours à la ligne
  HELPER_SESSION_DIR  dossier des sessions (défaut « helper_sessions », à garder entre deux démarrages)
  HELPER_IN_MEMORY    true = pas de fichier de session (hébergeur sans disque persistant)

Chaque bot d'aide doit être ADMIN du canal. L'access_hash du canal est propre à chaque bot : il est
mémorisé en base (table app_kv) dès qu'un message arrive dans le canal, puis réinjecté à chaque démarrage.
Commande admin dans le bot principal : /pool (état des bots).
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
import weakref
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Callable

from config import settings

logger = logging.getLogger("animecey.botpool")


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    return default if raw is None else raw.strip().lower() in ("1", "true", "yes", "on")


HELPER_TOKENS: list[str] = [t for t in re.split(r"[\s,;]+", os.getenv("HELPER_BOT_TOKENS", "")) if t]
SESSION_DIR = os.getenv("HELPER_SESSION_DIR", "helper_sessions")
IN_MEMORY = _env_bool("HELPER_IN_MEMORY", False)

MSG_TTL = 600        # secondes de cache d'un message Telegram (évite un appel Telegram par Range)
CACHE_MAX = 1500     # messages gardés en cache, tous bots confondus
MAX_TRIES = 3        # bots essayés avant d'abandonner
_KV_MAIN_KEY = "telegram_channel_access_hash"   # clé du bot principal (voir bot/channel_peer.py)


class PoolUnavailable(Exception):
    """Aucun bot n'a pu ouvrir la vidéo."""


class MediaMissing(Exception):
    """Le message n'existe plus dans le canal ou n'a pas de fichier."""


class RangeError(Exception):
    """Plage d'octets demandée invalide (HTTP 416)."""

    def __init__(self, size: int):
        super().__init__("range invalide")
        self.size = size


@dataclass
class StreamHandle:
    body: AsyncGenerator[bytes, None]
    from_bytes: int
    until_bytes: int
    file_size: int
    mime_type: str
    file_name: str


@dataclass(eq=False)
class _Helper:
    index: int                     # -1 = bot principal
    client: Any = None
    bot_id: int = 0
    label: str = "?"
    ready: bool = False
    started: bool = False
    error: str = ""
    active: int = 0                # flux en cours de lecture
    served: int = 0
    fail_streak: int = 0
    cooldown_until: float = 0.0    # time.monotonic()
    hash_seen: str = ""

    @property
    def kv_key(self) -> str:
        return f"{_KV_MAIN_KEY}:{self.bot_id}"


class _Lease:
    """Réserve un bot pendant une lecture ; release() est sans danger si appelé plusieurs fois."""

    def __init__(self, helper: _Helper):
        self.helper = helper
        self.done = False
        helper.active += 1

    def release(self) -> None:
        if not self.done:
            self.done = True
            self.helper.active = max(0, self.helper.active - 1)


# ── Base de données (access_hash du canal, propre à chaque bot) ─────────────


async def _kv_get(key: str) -> str:
    try:
        from sqlalchemy import text
        from database import async_session

        async with async_session() as db:
            await db.execute(text("CREATE TABLE IF NOT EXISTS app_kv (key VARCHAR(100) PRIMARY KEY, value TEXT NOT NULL)"))
            row = (await db.execute(text("SELECT value FROM app_kv WHERE key = :k"), {"k": key})).first()
            await db.commit()
            return row[0] if row else ""
    except Exception as exc:  # noqa: BLE001
        logger.error("Lecture de %s en base impossible : %s", key, exc)
        return ""


async def _kv_set(key: str, value: str) -> None:
    try:
        from sqlalchemy import text
        from database import async_session

        async with async_session() as db:
            await db.execute(text("CREATE TABLE IF NOT EXISTS app_kv (key VARCHAR(100) PRIMARY KEY, value TEXT NOT NULL)"))
            await db.execute(
                text("INSERT INTO app_kv (key, value) VALUES (:k, :v) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"),
                {"k": key, "v": value},
            )
            await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.error("Sauvegarde de %s en base impossible : %s", key, exc)


def _raw_channel_id() -> int:
    return abs(settings.TELEGRAM_CHANNEL_ID) - 10**12   # -1003340962000 -> 3340962000


def _filestream():
    """Chargé à la demande (services.filestream importe tout Pyrogram)."""
    from services import filestream

    return filestream


# ── Le pool ─────────────────────────────────────────────────────────────────


class BotPool:
    def __init__(self) -> None:
        self.helpers: list[_Helper] = []
        self._main: _Helper | None = None
        self._cache: dict[tuple[int, int], tuple[float, Any]] = {}
        self._task: asyncio.Task | None = None

    # ---- démarrage / arrêt ------------------------------------------------

    def start_background(self) -> None:
        """Démarre les bots en arrière-plan : l'API répond tout de suite, les bots deviennent prêts au fil de l'eau."""
        if HELPER_TOKENS and self._task is None:
            self._task = asyncio.create_task(self.start())

    async def stop_background(self) -> None:
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
        await self.stop()

    async def start(self) -> None:
        if not HELPER_TOKENS:
            logger.info("Aucun bot d'aide (HELPER_BOT_TOKENS) : le bot principal sert la vidéo.")
            return
        # Importer bot.client applique le correctif des ids de canaux récents (Pyrogram 2.0.106)
        import bot.client  # noqa: F401

        os.makedirs(SESSION_DIR, exist_ok=True)
        gate = asyncio.Semaphore(3)   # connexions échelonnées : évite les FLOOD_WAIT à l'ouverture des sessions

        async def one(i: int, token: str) -> None:
            async with gate:
                await self._start_one(i, token)
                await asyncio.sleep(0.4)

        await asyncio.gather(*(one(i, t) for i, t in enumerate(HELPER_TOKENS)), return_exceptions=True)
        ready = sum(1 for h in self.helpers if h.ready)
        logger.info("Bots de streaming : %s/%s prêts.", ready, len(self.helpers))

    async def stop(self) -> None:
        for h in self.helpers:
            if h.started and h.client is not None:
                try:
                    await h.client.stop()
                except Exception:  # noqa: BLE001
                    logger.debug("arrêt de %s impossible", h.label, exc_info=True)
            h.started = h.ready = False

    async def _start_one(self, index: int, token: str) -> None:
        from pyrogram import Client
        from pyrogram.enums import ParseMode

        try:
            bot_id = int(token.split(":")[0])
        except ValueError:
            bot_id = 0
        h = _Helper(index=index, bot_id=bot_id, label=f"bot {bot_id or index}")
        self.helpers.append(h)
        try:
            h.client = Client(
                f"helper_{bot_id or index}",
                api_id=settings.TELEGRAM_API_ID,
                api_hash=settings.TELEGRAM_API_HASH,
                bot_token=token,
                workdir=SESSION_DIR,
                in_memory=IN_MEMORY,
                sleep_threshold=60,
                parse_mode=ParseMode.DISABLED,
            )
            self._register_learner(h)
            await h.client.start()
            h.started = True
            me = h.client.me or await h.client.get_me()
            h.bot_id = me.id
            h.label = f"@{me.username}" if getattr(me, "username", None) else f"bot {me.id}"
            await self._ensure_peer(h)
        except Exception as exc:  # noqa: BLE001
            h.ready = False
            h.error = f"démarrage impossible : {exc}"
            logger.warning("%s : %s", h.label, h.error)

    def _register_learner(self, h: _Helper) -> None:
        """Un message arrive dans le canal : le bot en retire son access_hash, le mémorise et devient prêt."""
        from pyrogram import filters
        from pyrogram.handlers import MessageHandler

        async def _learn(client, message) -> None:  # noqa: ANN001
            try:
                peer = await client.resolve_peer(message.chat.id)
                value = str(peer.access_hash)
                if value != h.hash_seen:
                    h.hash_seen = value
                    await _kv_set(h.kv_key, value)
                if not h.ready:
                    await self._verify(h)
            except Exception as exc:  # noqa: BLE001
                logger.debug("%s : apprentissage du canal impossible : %s", h.label, exc)

        h.client.add_handler(
            MessageHandler(_learn, filters.channel & filters.chat(settings.TELEGRAM_CHANNEL_ID)), group=-5
        )

    async def _verify(self, h: _Helper) -> bool:
        try:
            await h.client.get_chat(settings.TELEGRAM_CHANNEL_ID)
        except Exception as exc:  # noqa: BLE001
            h.ready, h.error = False, f"canal inaccessible : {exc}"
            return False
        h.ready, h.error, h.fail_streak = True, "", 0
        logger.info("%s prêt.", h.label)
        return True

    async def _ensure_peer(self, h: _Helper) -> bool:
        from pyrogram import raw

        try:   # déjà connu (fichier de session) ?
            await h.client.resolve_peer(settings.TELEGRAM_CHANNEL_ID)
            if await self._verify(h):
                return True
        except Exception:  # noqa: BLE001
            pass

        seen: list[str] = []
        for value in ((await _kv_get(h.kv_key)), (await _kv_get(_KV_MAIN_KEY)), settings.TELEGRAM_CHANNEL_ACCESS_HASH):
            value = (value or "").strip()
            if value and value not in seen:
                seen.append(value)
        for value in seen:
            try:
                res = await h.client.invoke(
                    raw.functions.channels.GetChannels(
                        id=[raw.types.InputChannel(channel_id=_raw_channel_id(), access_hash=int(value))]
                    )
                )
                await h.client.fetch_peers(res.chats)
                await h.client.resolve_peer(settings.TELEGRAM_CHANNEL_ID)
                if await self._verify(h):
                    h.hash_seen = value
                    await _kv_set(h.kv_key, value)
                    return True
            except Exception as exc:  # noqa: BLE001
                h.error = f"access_hash refusé : {exc}"
        if not h.error:
            h.error = "canal inconnu : poste un message dans le canal (le bot l'apprendra) et vérifie qu'il en est admin"
        logger.warning("%s : %s", h.label, h.error)
        return False

    # ---- choix du bot ---------------------------------------------------------

    def _main_helper(self) -> _Helper | None:
        try:
            from bot.client import bot as main
        except Exception:  # noqa: BLE001
            return None
        if not getattr(main, "is_connected", False):
            return None
        if self._main is None:
            self._main = _Helper(index=-1, client=main, label="bot principal", ready=True, started=True)
        return self._main

    def _pick(self, tried: set[int]) -> _Helper | None:
        now = time.monotonic()
        usable = [h for h in self.helpers if h.ready and h.index not in tried and h.cooldown_until <= now]
        if not usable:
            return None
        return min(usable, key=lambda h: (h.active, h.served))   # le moins occupé, puis le moins sollicité

    def _next(self, tried: set[int]) -> _Helper | None:
        h = self._pick(tried)
        if h is None and -1 not in tried:
            h = self._main_helper()
        return h

    def any_client(self):
        """Un client Telegram prêt (pour les vignettes) ou None."""
        h = self._next(set())
        return h.client if h else None

    # ---- lecture ---------------------------------------------------------------

    async def _get_message(self, h: _Helper, msg_id: int):
        key = (h.index, msg_id)
        hit = self._cache.get(key)
        if hit and time.monotonic() - hit[0] < MSG_TTL:
            return hit[1]
        msg = await h.client.get_messages(settings.TELEGRAM_CHANNEL_ID, msg_id)
        if len(self._cache) >= CACHE_MAX:
            for old in list(self._cache)[: CACHE_MAX // 4]:
                self._cache.pop(old, None)
        self._cache[key] = (time.monotonic(), msg)
        return msg

    def _forget(self, h: _Helper, msg_id: int) -> None:
        self._cache.pop((h.index, msg_id), None)

    def _penalize(self, h: _Helper, exc: Exception, msg_id: int) -> None:
        from pyrogram.errors import FloodWait

        self._forget(h, msg_id)
        h.fail_streak += 1
        if isinstance(exc, FloodWait):
            wait = min(int(getattr(exc, "value", 30) or 30) + 1, 300)
            h.cooldown_until = time.monotonic() + wait
            logger.warning("%s : FLOOD_WAIT %s s, mis de côté.", h.label, wait)
        elif h.fail_streak >= 3:
            h.cooldown_until = time.monotonic() + 60
            logger.warning("%s : 3 échecs de suite, mis de côté 60 s (%s).", h.label, exc)
        else:
            logger.info("%s : échec de lecture (%s), on essaie un autre bot.", h.label, exc)

    async def open_stream(
        self,
        msg_id: int,
        range_header: str | None,
        parse_range: Callable[[str | None, int], "tuple[int, int | None] | None"],
    ) -> StreamHandle:
        """Ouvre la lecture avec le bot le moins occupé ; bascule sur un autre bot si le premier échoue.

        Le premier bloc de données est lu AVANT de répondre au navigateur : une erreur Telegram devient
        donc un essai sur un autre bot, pas une vidéo coupée.
        """
        fs = _filestream()
        tried: set[int] = set()
        last_exc: Exception | None = None
        for _ in range(MAX_TRIES):
            h = self._next(tried)
            if h is None:
                break
            tried.add(h.index)
            lease = _Lease(h)
            try:
                msg = await self._get_message(h, msg_id)
                media = fs.get_media_from_message(msg) if msg else None
                if media is None:
                    raise MediaMissing("fichier non trouvé dans le canal")
                size = getattr(media, "file_size", 0) or 0
                parsed = parse_range(range_header, size)
                if parsed is None:
                    raise RangeError(size)
                body, from_b, until_b, file_size, mime, name = await fs.stream_media(h.client, msg, parsed[0], parsed[1])
                try:
                    first = await body.__anext__()
                except StopAsyncIteration:
                    first = b""
            except (MediaMissing, RangeError):
                lease.release()
                self._forget(h, msg_id)
                raise
            except Exception as exc:  # noqa: BLE001
                lease.release()
                last_exc = exc
                self._penalize(h, exc, msg_id)
                continue

            h.served += 1
            h.fail_streak = 0

            async def _gen(first=first, body=body, lease=lease) -> AsyncGenerator[bytes, None]:
                try:
                    if first:
                        yield first
                    async for chunk in body:
                        yield chunk
                finally:
                    lease.release()

            gen = _gen()
            weakref.finalize(gen, lease.release)   # filet de sécurité si le navigateur part avant la 1re lecture
            return StreamHandle(gen, from_b, until_b, file_size, mime, name)

        raise PoolUnavailable(str(last_exc) if last_exc else "aucun bot Telegram disponible")

    # ---- état -----------------------------------------------------------------------

    def status_text(self) -> str:
        helpers = sorted(self.helpers, key=lambda h: h.index)
        ready = [h for h in helpers if h.ready]
        if not helpers:
            return "🤖 Aucun bot d'aide configuré (HELPER_BOT_TOKENS) : le bot principal sert la vidéo."
        lines = [
            f"🤖 Bots de streaming : {len(ready)}/{len(helpers)} prêts · "
            f"{sum(h.active for h in helpers)} flux en cours · {sum(h.served for h in helpers)} lectures servies"
        ]
        now = time.monotonic()
        paused = [h for h in ready if h.cooldown_until > now]
        if paused:
            lines.append("⏸️ En pause : " + ", ".join(h.label for h in paused[:10]))
        busiest = sorted((h for h in ready if h.active), key=lambda h: -h.active)[:5]
        if busiest:
            lines.append("📈 Plus occupés : " + ", ".join(f"{h.label} ({h.active})" for h in busiest))
        bad = [h for h in helpers if not h.ready]
        for h in bad[:12]:
            lines.append(f"❌ {h.label} — {h.error or 'pas encore prêt'}")
        if len(bad) > 12:
            lines.append(f"… et {len(bad) - 12} autres bots non prêts")
        return "\n".join(lines)


pool = BotPool()


def start_background() -> None:
    pool.start_background()


async def stop_background() -> None:
    await pool.stop_background()


def register_pool_command(bot) -> None:  # noqa: ANN001
    """Ajoute /pool (état des bots de streaming) au bot principal, réservé aux admins."""
    from pyrogram import filters

    from bot.handlers.admin import is_admin

    @bot.on_message(filters.command("pool") & filters.private, group=-3)
    async def _pool_cmd(client, message):  # noqa: ANN001
        if not message.from_user or not is_admin(message.from_user.id):
            return message.continue_propagation()
        await message.reply(pool.status_text())
        message.stop_propagation()
