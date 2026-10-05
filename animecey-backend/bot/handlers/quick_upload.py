"""Envoi d'épisodes au bot : la légende peut être libre (voir services/caption_parser.py).

Le fichier est mis dans le canal Telegram privé (stockage), puis rattaché à l'épisode
(animé + emplacement + langue + numéro). L'emplacement est créé s'il n'existe pas.

Commande utile : /anime 42 (ou /anime Black Clover) fixe l'animé pour les envois suivants,
quand la légende ne contient pas le même nom que dans ta base (ex. « Kage no Jitsuryokusha »
pour « The Eminence in Shadow »).
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import re
import shutil
import tempfile
import time
from difflib import SequenceMatcher

from dataclasses import replace

from pyrogram import Client, StopPropagation, filters
from pyrogram.errors import FloodWait
from pyrogram.types import Message
from sqlalchemy import select

from bot.handlers.admin import is_admin
from config import settings
from database import async_session
from models import Anime, Episode, LanguageEnum
from models_catalog import AnimeSeason
from services import media as media_service
from services.caption_parser import Parsed, kind_of, merge_missing, norm, parse_caption, pretty_label
from services.filestream import get_media_from_message
from services.tmcooper_sync import _get_or_create_folder

logger = logging.getLogger(__name__)

VIDEO_EXT = (".mkv", ".mp4", ".avi", ".webm", ".mov", ".ts", ".m4v")
TMP_DIR = os.getenv("TELEGRAM_TMP_DIR", tempfile.gettempdir())
CURRENT_TTL = 3 * 3600  # /anime reste actif 3 h
# Mot à ajouter dans la légende pour remplacer un épisode déjà présent
_REPLACE_RE = re.compile(r"(?<![\w])(remplacer|remplace|replace|[ée]craser)(?![\w])", re.I)

_db_lock = asyncio.Lock()          # évite deux créations d'emplacement en même temps (envois groupés)
_job_lock = asyncio.Semaphore(1)   # un seul téléchargement + conversion à la fois
_current_anime: dict[int, tuple[int, float]] = {}  # admin_id -> (anime_id, horodatage)
_send_lock = asyncio.Lock()          # envois vers le canal un par un (évite les FLOOD_WAIT)
_tasks: set[asyncio.Task] = set()      # références aux traitements en cours (évite qu'ils soient ramassés)


class _Stop(Exception):
    """Arrête le traitement avec un message pour l'admin."""


# ── Choix de l'animé ────────────────────────────────────────────────────


def _score(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if min(len(a), len(b)) >= 4 and (a in b or b in a):
        return 0.9
    return SequenceMatcher(None, a, b).ratio()


async def _resolve_anime(db, title: str | None, admin_id: int | None):
    """-> (ligne animé | None, candidats proches)."""
    rows = (await db.execute(select(Anime.id, Anime.title, Anime.title_jp))).all()
    candidates = []
    if title:
        q = norm(title)
        scored = sorted(
            ((max(_score(q, norm(r.title)), _score(q, norm(r.title_jp))), r) for r in rows),
            key=lambda x: -x[0],
        )
        if scored and scored[0][0] >= 0.82 and (
            scored[0][0] == 1.0 or len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.05
        ):
            return scored[0][1], []
        candidates = [r for s, r in scored[:5] if s >= 0.5]
    cur = _current_anime.get(admin_id) if admin_id else None
    if cur and time.time() - cur[1] < CURRENT_TTL:
        row = next((r for r in rows if r.id == cur[0]), None)
        if row:
            return row, []
    return None, candidates


async def _find_or_create_season(db, anime_id: int, key: str) -> AnimeSeason:
    seasons = (await db.execute(select(AnimeSeason).where(AnimeSeason.anime_id == anime_id))).scalars().all()
    for s in seasons:
        if s.api_season == key:
            return s
    # « saga2 » doit retrouver « saga2(alabasta) »
    starts = [s for s in seasons if s.api_season.startswith(key + "(")]
    if len(starts) == 1:
        return starts[0]
    # un seul film / OAV / spécial existant : c'est lui
    if key in ("film1", "oav", "special"):
        same = [s for s in seasons if s.api_season.startswith(key.rstrip("1"))]
        if len(same) == 1:
            return same[0]
    season = AnimeSeason(
        anime_id=anime_id,
        season_number=max([s.season_number for s in seasons], default=0) + 1,
        api_season=key[:50],
        label=pretty_label(key)[:255],
        kind=kind_of(key),
    )
    db.add(season)
    await db.flush()
    return season


# ── Étapes de traitement ────────────────────────────────────────────────


async def _channel_send(factory):
    """Exécute un envoi vers le canal, un à la fois, avec une courte pause ; si Telegram répond
    FLOOD_WAIT, on attend la durée demandée puis on réessaie (jusqu'à 5 fois)."""
    async with _send_lock:
        for attempt in range(5):
            try:
                return await factory()
            except FloodWait as exc:
                wait = int(getattr(exc, "value", 10) or 10) + 1
                logger.warning("FLOOD_WAIT : attente de %s s (essai %s/5)", wait, attempt + 1)
                await asyncio.sleep(wait)
            finally:
                await asyncio.sleep(1.2)
        return await factory()


async def _telegram_thumb(client: Client, media) -> bytes | None:
    """Miniature déjà fournie par Telegram pour cette vidéo (fichiers MP4 transférés)."""
    thumbs = getattr(media, "thumbs", None) or []
    if not thumbs:
        return None
    try:
        buf = await client.download_media(thumbs[-1].file_id, in_memory=True)
        return buf.getvalue() if buf else None
    except Exception:  # noqa: BLE001
        logger.warning("miniature Telegram indisponible", exc_info=True)
        return None


async def _store_thumb(client: Client, data: bytes | None) -> int | None:
    """Range la vignette dans le canal de stockage ; renvoie l'id du message (jamais d'exception)."""
    if not data:
        return None
    try:
        bio = io.BytesIO(data)
        bio.name = "thumb.jpg"
        m = await _channel_send(lambda: client.send_photo(settings.TELEGRAM_CHANNEL_ID, bio, caption="vignette"))
        return m.id
    except Exception:  # noqa: BLE001
        logger.warning("vignette non enregistrée", exc_info=True)
        return None


def _describe(p: Parsed) -> str:
    return f"titre={p.title or '?'} · emplacement={p.slot_key} · langue={p.lang or '?'} · épisode={p.episode if p.episode is not None else '?'}"


async def _prepare(admin_id: int, p: Parsed) -> dict:
    async with _db_lock:
        async with async_session() as db:
            row, candidates = await _resolve_anime(db, p.title, admin_id)
            if row is None:
                if candidates:
                    names = "\n".join(f"• {c.id} — {c.title}" for c in candidates)
                    raise _Stop(f"Animé « {p.title} » introuvable. Proches :\n{names}\nUtilise /anime <id> puis renvoie le fichier.")
                if p.title:
                    raise _Stop(
                        f"Animé « {p.title} » introuvable dans ta base. Ouvre-le d'abord sur le site, "
                        "ou utilise /anime <id> puis renvoie le fichier."
                    )
                raise _Stop("Aucun titre dans la légende. Utilise /anime <id> avant d'envoyer, ou ajoute le titre.")
            season = await _find_or_create_season(db, row.id, p.slot_key)
            await db.commit()
            return {
                "anime_id": row.id, "anime_title": row.title,
                "season_number": season.season_number, "season_label": season.label,
            }


async def _save_episode(
    ctx: dict,
    language: LanguageEnum,
    num: int,
    sent,
    duration: int | None,
    allow_replace: bool = False,
    thumb_msg_id: int | None = None,
) -> bool:
    sent_media = get_media_from_message(sent)
    if sent_media is None:
        raise RuntimeError("Le canal n'a renvoyé aucun média.")
    async with _db_lock:
        async with async_session() as db:
            anime = await db.get(Anime, ctx["anime_id"])
            folder = await _get_or_create_folder(db, anime, language, ctx["season_number"])
            if ctx["season_label"] and folder.name != ctx["season_label"]:
                folder.name = ctx["season_label"][:255]
            ep = (
                await db.execute(
                    select(Episode).where(
                        Episode.anime_id == anime.id,
                        Episode.language == language,
                        Episode.season_number == ctx["season_number"],
                        Episode.episode_number == num,
                    )
                )
            ).scalars().first()
            replaced = bool(ep and ep.servcey1_file_id)
            if replaced and not allow_replace:
                raise _Stop(_duplicate_message(ctx, language, num))
            if ep is None:
                ep = Episode(
                    anime_id=anime.id, folder_id=folder.id, episode_number=num,
                    language=language, season_number=ctx["season_number"],
                )
                db.add(ep)
            ep.servcey1_file_id = sent_media.file_id
            ep.servcey1_msg_id = sent.id
            ep.servcey1_available = True
            if duration:
                ep.duration = duration
            await db.flush()  # pour avoir ep.id
            base = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
            if thumb_msg_id and base:
                ep.thumb_msg_id = thumb_msg_id
                ep.thumbnail_url = f"{base}/api/episodes/{ep.id}/thumb?v={thumb_msg_id}"
            await db.commit()
            return replaced


def _duplicate_message(ctx: dict, language: LanguageEnum, num: int) -> str:
    return (
        f"⚠️ Déjà existant : {ctx['anime_title']} — {ctx['season_label']} — {language.value} — épisode {num}.\n"
        "Je n'ai rien modifié. Pour le remplacer, renvoie le fichier avec le mot REMPLACER dans la légende."
    )


async def _already_there(ctx: dict, language: LanguageEnum, num: int) -> bool:
    """Un fichier ServCey 1 existe-t-il déjà pour cet épisode ?"""
    async with async_session() as db:
        found = (
            await db.execute(
                select(Episode.id).where(
                    Episode.anime_id == ctx["anime_id"],
                    Episode.language == language,
                    Episode.season_number == ctx["season_number"],
                    Episode.episode_number == num,
                    Episode.servcey1_file_id.isnot(None),
                )
            )
        ).first()
    return found is not None


def _is_video(message: Message) -> bool:
    if message.video:
        return True
    d = message.document
    return bool(d and ((d.mime_type or "").startswith("video/") or (d.file_name or "").lower().endswith(VIDEO_EXT)))


def register(bot: Client):

    @bot.on_message(filters.private & filters.command("anime"))
    async def cmd_anime(client: Client, message: Message):
        if not message.from_user or not is_admin(message.from_user.id):
            return
        arg = " ".join(message.command[1:]).strip()
        uid = message.from_user.id
        if not arg:
            cur = _current_anime.get(uid)
            if cur and time.time() - cur[1] < CURRENT_TTL:
                async with async_session() as db:
                    a = await db.get(Anime, cur[0])
                return await message.reply(f"Animé actuel : {a.title if a else cur[0]}")
            return await message.reply("Aucun animé fixé. Usage : /anime <id ou titre>")
        async with async_session() as db:
            if arg.isdigit():
                a = await db.get(Anime, int(arg))
                row = a and type("R", (), {"id": a.id, "title": a.title})
                candidates = []
            else:
                row, candidates = await _resolve_anime(db, arg, None)
        if row is None:
            names = "\n".join(f"• {c.id} — {c.title}" for c in candidates)
            return await message.reply("Animé introuvable." + (f" Proches :\n{names}" if names else ""))
        _current_anime[uid] = (row.id, time.time())
        await message.reply(f"✅ Animé fixé : {row.title} (3 h). Envoie tes fichiers.")

    async def _process(client: Client, message: Message):
        media = message.video or message.document
        fname = getattr(media, "file_name", None) or ""

        raw_caption = message.caption or ""
        replace_ok = bool(_REPLACE_RE.search(raw_caption))
        p = parse_caption(_REPLACE_RE.sub(" ", raw_caption))
        if p.episode is None or p.lang is None or p.title is None or p.slot_defaulted:
            p = merge_missing(p, parse_caption(os.path.splitext(fname)[0], is_filename=True))

        if p.slot_defaulted and (getattr(media, "duration", None) or 0) >= 4200:
            p = replace(p, slot_key="film1", slot_defaulted=False, episode=1)  # > 70 min : c'est un film

        status = await message.reply("⏳ Analyse…")
        try:
            if p.episode is None:
                raise _Stop(f"Numéro d'épisode introuvable.\nCompris : {_describe(p)}")
            if p.lang is None:
                raise _Stop(f"Langue introuvable (VF ou VOSTFR ?).\nCompris : {_describe(p)}")

            language = LanguageEnum.VF if p.lang == "VF" else LanguageEnum.VOSTFR
            ctx = await _prepare(message.from_user.id, p)
            if not replace_ok and await _already_there(ctx, language, p.episode):
                raise _Stop(_duplicate_message(ctx, language, p.episode))
            caption = f"{ctx['anime_title']} | {p.slot_key} | {p.lang} | {p.episode}"

            is_mp4 = fname.lower().endswith(".mp4") or (getattr(media, "mime_type", "") == "video/mp4")
            duration = getattr(media, "duration", None)
            subs = 0
            thumb_bytes: bytes | None = None

            if is_mp4:
                # Déjà au bon format : copie directe dans le canal (sans retélécharger).
                sent = await _channel_send(lambda: message.copy(chat_id=settings.TELEGRAM_CHANNEL_ID, caption=caption))
                thumb_bytes = await _telegram_thumb(client, media)
            else:
                size = getattr(media, "file_size", 0) or 0
                free = shutil.disk_usage(TMP_DIR).free
                if size * 2.2 > free:
                    raise _Stop(
                        f"Pas assez de disque pour convertir ({size // 2**20} Mo, il reste {free // 2**20} Mo). "
                        "Convertis-le en MP4 sur ton PC (ffmpeg -i in.mkv -c copy -movflags +faststart out.mp4) et renvoie-le."
                    )
                if _job_lock.locked():
                    await status.edit_text("⏳ En file d'attente (un fichier est en cours de conversion)…")
                async with _job_lock:
                    with tempfile.TemporaryDirectory(dir=TMP_DIR) as tmp:
                        await status.edit_text("⬇️ Téléchargement…")
                        src = await client.download_media(message, file_name=os.path.join(tmp, "src"))
                        await status.edit_text("🔧 Conversion en MP4…")
                        dst = os.path.join(tmp, f"{p.episode:03d}.mp4")
                        info = await media_service.remux_to_mp4(src, dst)
                        os.remove(src)
                        duration, subs = info["duration"], info["subtitle_tracks"]
                        thumb_bytes = await media_service.extract_frame(dst, duration)
                        await status.edit_text("⬆️ Envoi dans le canal…")
                        sent = await _channel_send(
                            lambda: client.send_document(
                                settings.TELEGRAM_CHANNEL_ID, dst, caption=caption, force_document=True
                            )
                        )

            thumb_msg_id = await _store_thumb(client, thumb_bytes)
            replaced = await _save_episode(
                ctx, language, p.episode, sent, duration, allow_replace=replace_ok, thumb_msg_id=thumb_msg_id
            )

            notes = []
            if p.multi:
                notes.append(f"Multi rangé en {p.lang}")
            if p.slot_defaulted:
                notes.append("aucun emplacement dans la légende : Saison 1")
            if subs:
                notes.append("pistes de sous-titres séparées ignorées")
            await status.edit_text(
                f"✅ {ctx['anime_title']} — {ctx['season_label']} — {p.lang} — épisode {p.episode}"
                f"{' (remplacé)' if replaced else ''}" + (f"\nℹ️ {' · '.join(notes)}" if notes else "")
            )
        except _Stop as stop:
            await status.edit_text(str(stop))
        except media_service.MediaError as exc:
            await status.edit_text(f"❌ {exc}")
        except Exception as exc:  # noqa: BLE001
            logger.exception("envoi d'épisode en échec")
            await status.edit_text(f"❌ Erreur : {exc}")

    @bot.on_message(filters.private & (filters.video | filters.document), group=-1)
    async def handle_media(client: Client, message: Message):
        if not message.from_user or not is_admin(message.from_user.id) or not _is_video(message):
            return
        # Traitement en tâche de fond : sinon les fichiers en attente occupent tous les
        # « workers » du bot et il ne répond plus aux autres commandes.
        task = asyncio.create_task(_process(client, message))
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)
        raise StopPropagation  # empêche l'ancien système /upload de retraiter le fichier
