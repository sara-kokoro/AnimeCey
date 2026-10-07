"""Envoi d'épisodes au bot : la légende peut être libre (voir services/caption_parser.py).

Le fichier est mis dans le canal Telegram privé (stockage), puis rattaché à l'épisode
(animé + emplacement + langue + numéro). L'emplacement est créé s'il n'existe pas.

Commande utile : /anime 42 (ou /anime Black Clover) fixe l'animé pour les envois suivants,
quand la légende ne contient pas le même nom que dans ta base (ex. « Kage no Jitsuryokusha »
pour « The Eminence in Shadow »).
Options facultatives, dans n'importe quel ordre : la langue (VF / VOSTFR) et l'emplacement
(S01, Saga 2, Film, OAV...) : « /anime 16 VF S01 » force VF + Saison 1 pour tous les envois suivants.
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
from models import Anime, AnimeType, Episode, LanguageEnum
from models_catalog import AnimeSeason
from services import media as media_service
from services.caption_parser import (
    Parsed, kind_of, merge_missing, norm, parse_anime_args, parse_caption, pretty_label,
)
from services.filestream import get_media_from_message
from services.tmcooper_sync import _get_or_create_folder

logger = logging.getLogger(__name__)

VIDEO_EXT = (".mkv", ".mp4", ".avi", ".webm", ".mov", ".ts", ".m4v", ".flv")
TMP_DIR = os.getenv("TELEGRAM_TMP_DIR", tempfile.gettempdir())
CURRENT_TTL = 3 * 3600  # /anime reste actif 3 h
# Mot à ajouter dans la légende pour remplacer un épisode déjà présent
_REPLACE_RE = re.compile(r"(?<![\w])(remplacer|remplace|replace|[ée]craser)(?![\w])", re.I)

_db_lock = asyncio.Lock()          # évite deux créations d'emplacement en même temps (envois groupés)
_job_lock = asyncio.Semaphore(1)   # un seul téléchargement + conversion à la fois
_current_anime: dict[int, tuple[int, float]] = {}  # admin_id -> (anime_id, horodatage)
# admin_id -> (langue forcée | None, emplacement forcé | None) ; vit aussi longtemps que /anime
_current_opts: dict[int, tuple[str | None, str | None]] = {}
# admin_id présents ici : /movie sur un film -> chaque fichier est l'épisode 1 du « Film 1 » (la légende peut être vide)
_current_movie: set[int] = set()
# admin_id présents ici : dernière commande = /movie (film, Netflix, Prime Video...) -> l'animé fixé passe AVANT le titre du fichier
_movie_pinned: set[int] = set()
_send_lock = asyncio.Lock()          # envois vers le canal un par un (évite les FLOOD_WAIT)
_tasks: set[asyncio.Task] = set()      # références aux traitements en cours (évite qu'ils soient ramassés)
_jobs: dict[int, set[asyncio.Task]] = {}   # traitements en cours ou en attente, par admin (pour /cancel)


def cancel_jobs(user_id: int) -> int:
    """Arrête les envois de cet admin : téléchargement, conversion, envoi, ou en file d'attente.

    Annuler une tâche interrompt l'opération en cours : le téléchargement s'arrête, ffmpeg est tué et
    le dossier temporaire est effacé (voir _process). Renvoie le nombre de traitements arrêtés.
    """
    tasks = [t for t in _jobs.get(user_id, ()) if not t.done()]
    for t in tasks:
        t.cancel()
    return len(tasks)


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


async def _fixed_anime(db, admin_id: int | None):
    """Animé fixé par /movie (encore actif), sinon None. Pour un film, le nom du fichier ne dit pas
    lequel c'est : « Deadpool.2.2018.avi » donne le titre « Deadpool », qui retomberait sur le
    film 1 alors que tu as fixé le film 2. /anime n'est pas concerné (la légende reste prioritaire)."""
    if not admin_id or admin_id not in _movie_pinned:
        return None
    cur = _current_anime.get(admin_id)
    if not cur or time.time() - cur[1] >= CURRENT_TTL:
        return None
    return (await db.execute(select(Anime.id, Anime.title, Anime.title_jp).where(Anime.id == cur[0]))).first()


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


def _size(n: float) -> str:
    return f"{n / 2**30:.2f} Go".replace(".", ",") if n >= 2**30 else f"{n / 2**20:.0f} Mo"


def _eta(seconds: float) -> str:
    s = int(max(seconds, 0))
    h, rest = divmod(s, 3600)
    m, sec = divmod(rest, 60)
    if h:
        return f"{h} h {m:02d} min"
    if m:
        return f"{m} min {sec:02d} s"
    return f"{sec} s"


def _bar(pct: float, width: int = 10) -> str:
    n = max(0, min(width, round(width * pct / 100)))
    return "▰" * n + "▱" * (width - n)


class _StatusUpdater:
    """Met à jour le message d'état dans Telegram, au plus une fois toutes les 4 s (anti-FLOOD_WAIT)."""

    def __init__(self, status: Message, min_interval: float = 4.0):
        self.status = status
        self.min_interval = min_interval
        self._last = 0.0
        self._text = ""

    async def set(self, text: str, force: bool = False) -> None:
        now = time.monotonic()
        if text == self._text or (not force and now - self._last < self.min_interval):
            return
        self._last, self._text = now, text
        try:
            await self.status.edit_text(text)
        except Exception:  # noqa: BLE001 — un affichage raté ne doit jamais arrêter un envoi
            logger.debug("mise à jour du message d'état impossible", exc_info=True)


def _transfer_cb(ui: _StatusUpdater, label: str):
    """Callback de progression pour download_media / send_document."""
    t0 = time.monotonic()

    async def cb(current: int, total: int) -> None:
        if not total:
            return
        pct = current * 100 / total
        speed = current / max(time.monotonic() - t0, 0.001)
        eta = (total - current) / speed if speed else 0
        await ui.set(
            f"{label}\n{_bar(pct)} {pct:.0f} %\n{_size(current)} / {_size(total)} · {_size(speed)}/s · reste {_eta(eta)}",
            force=current >= total,
        )

    return cb


_CONVERT_LABELS = {
    "encode": "🎞️ Encodage en H.264 (vidéo illisible par les navigateurs, c'est long)",
    "audio": "🔊 Conversion du son en AAC (vidéo copiée)",
    "copy": "🔧 Conversion en MP4 (copie rapide)",
}


def _convert_cb(ui: _StatusUpdater):
    """Callback de progression pour media_service.remux_to_mp4."""

    async def cb(done: float, total: float, speed: float | None, mode: str) -> None:
        label = _CONVERT_LABELS.get(mode, "🔧 Conversion")
        if total <= 0:
            return await ui.set(f"{label}\nEn cours… {_eta(done)} de vidéo traitées")
        pct = min(done * 100 / total, 100)
        line = f"{_bar(pct)} {pct:.0f} %"
        if speed and speed > 0:
            line += f"\nvitesse ×{speed:.2f} · reste {_eta((total - done) / speed)}".replace(".", ",")
        await ui.set(f"{label}\n{line}")

    return cb


async def _mp4_ready(client: Client, message: Message) -> bool | None:
    """Analyse le début du MP4 sans le télécharger en entier.

    True : lisible tel quel (H.264 8 bits, audio AAC/MP3) ; False : à convertir ;
    None : impossible de savoir sans tout télécharger (index « moov » placé en fin de fichier).
    """
    try:
        with tempfile.TemporaryDirectory(dir=TMP_DIR) as tmp:
            head = os.path.join(tmp, "head.mp4")
            with open(head, "wb") as fh:
                async for chunk in client.stream_media(message, limit=16):  # 16 premiers Mo
                    fh.write(chunk)
            info = await media_service.probe(head)
    except Exception:  # noqa: BLE001
        logger.info("analyse rapide du MP4 impossible", exc_info=True)
        return None
    return media_service.is_browser_ready(info)


def _describe(p: Parsed) -> str:
    return f"titre={p.title or '?'} · emplacement={p.slot_key} · langue={p.lang or '?'} · épisode={p.episode if p.episode is not None else '?'}"


async def _prepare(admin_id: int, p: Parsed) -> dict:
    async with _db_lock:
        async with async_session() as db:
            row, candidates = await _fixed_anime(db, admin_id), []
            if row is None:
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

    @bot.on_message(filters.private & filters.command(["anime", "movie"]))
    async def cmd_anime(client: Client, message: Message):
        if not message.from_user or not is_admin(message.from_user.id):
            return
        raw_arg = " ".join(message.command[1:]).strip()
        uid = message.from_user.id
        query, lang, slot = parse_anime_args(raw_arg)

        def _opts_text(l: str | None, sl: str | None) -> str:
            parts = []
            if l:
                parts.append(f"langue : {l}")
            if sl:
                parts.append(f"emplacement : {pretty_label(sl)}")
            return (" · " + " · ".join(parts)) if parts else " · langue et emplacement lus dans la légende"

        cur = _current_anime.get(uid)
        active = bool(cur and time.time() - cur[1] < CURRENT_TTL)

        if not raw_arg:
            if active:
                async with async_session() as db:
                    a = await db.get(Anime, cur[0])
                l, sl = _current_opts.get(uid, (None, None))
                return await message.reply(f"Animé actuel : {a.title if a else cur[0]}{_opts_text(l, sl)}")
            return await message.reply(
                "Aucun animé fixé. Usage : /anime <id ou titre> [VF|VOSTFR] [S01|Saga 2|Film|OAV]"
            )

        # « /anime VF S02 » : on garde l'animé déjà fixé et on change seulement les options
        if not query:
            if not active:
                return await message.reply("Aucun animé fixé. Commence par /anime <id ou titre>.")
            _current_anime[uid] = (cur[0], time.time())
            _current_opts[uid] = (lang, slot)
            async with async_session() as db:
                a = await db.get(Anime, cur[0])
            return await message.reply(f"✅ Options mises à jour : {a.title if a else cur[0]}{_opts_text(lang, slot)}")

        async with async_session() as db:
            if query.isdigit():
                a = await db.get(Anime, int(query))
                row = a and type("R", (), {"id": a.id, "title": a.title})
                candidates = []
            else:
                row, candidates = await _resolve_anime(db, query, None)
        if row is None:
            names = "\n".join(f"• {c.id} — {c.title}" for c in candidates)
            return await message.reply("Animé introuvable." + (f" Proches :\n{names}" if names else ""))
        _current_anime[uid] = (row.id, time.time())
        _current_movie.discard(uid)
        _movie_pinned.discard(uid)
        movie = False
        if message.command[0].lower() == "movie":
            _movie_pinned.add(uid)
            async with async_session() as db:
                a = await db.get(Anime, row.id)
            if a is not None and a.type == AnimeType.film:
                movie = True
                slot = slot or "film1"
                _current_movie.add(uid)
        _current_opts[uid] = (lang, slot)
        if movie:
            return await message.reply(
                f"✅ Film fixé : {row.title} (3 h){_opts_text(lang, None)}. "
                "Envoie ou transfère la vidéo : elle sera rangée toute seule (VF ou VOSTFR, "
                "lis la légende, ou refais /movie " + str(row.id) + " VF)."
            )
        await message.reply(f"✅ {'Titre' if message.command[0].lower() == 'movie' else 'Animé'} fixé : {row.title} (3 h){_opts_text(lang, slot)}. Envoie tes fichiers.")

    async def _process(client: Client, message: Message):
        media = message.video or message.document
        fname = getattr(media, "file_name", None) or ""

        raw_caption = message.caption or ""
        replace_ok = bool(_REPLACE_RE.search(raw_caption))
        p = parse_caption(_REPLACE_RE.sub(" ", raw_caption))
        if p.episode is None or p.lang is None or p.title is None or p.slot_defaulted:
            p = merge_missing(p, parse_caption(os.path.splitext(fname)[0], is_filename=True))

        # Options de /anime (langue / emplacement forcés), tant que l'animé fixé est actif
        uid = message.from_user.id
        cur = _current_anime.get(uid)
        if cur and time.time() - cur[1] < CURRENT_TTL:
            forced_lang, forced_slot = _current_opts.get(uid, (None, None))
            if forced_lang:
                p = replace(p, lang=forced_lang, multi=False)
            if uid in _current_movie:  # film : un seul fichier par langue = épisode 1
                p = replace(p, slot_key="film1", slot_defaulted=False, episode=1)
            elif forced_slot:
                p = replace(p, slot_key=forced_slot, slot_defaulted=False)
                if kind_of(forced_slot) == "film" and p.episode is None:
                    p = replace(p, episode=1)

        if p.slot_defaulted and (getattr(media, "duration", None) or 0) >= 4200:
            p = replace(p, slot_key="film1", slot_defaulted=False, episode=1)  # > 70 min : c'est un film

        status = await message.reply("⏳ Analyse…")
        sent = None            # message envoyé dans le canal
        thumb_msg_id = None    # vignette envoyée dans le canal
        saved = False          # enregistré en base ?
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

            ui = _StatusUpdater(status)
            is_mp4 = fname.lower().endswith(".mp4") or (getattr(media, "mime_type", "") == "video/mp4")
            duration = getattr(media, "duration", None)
            size = getattr(media, "file_size", 0) or 0
            subs = 0
            reencoded = False
            unverified = False
            thumb_bytes: bytes | None = None

            # Un MP4 n'est copié tel quel que s'il est vraiment lisible (H.264 8 bits + audio AAC/MP3).
            direct = False
            if is_mp4:
                await ui.set("🔎 Vérification du format de la vidéo…", force=True)
                ready = await _mp4_ready(client, message)
                if ready is True:
                    direct = True
                elif ready is None and size * 2.2 > shutil.disk_usage(TMP_DIR).free:
                    direct = True      # impossible à vérifier sans tout télécharger, et pas assez de disque
                    unverified = True

            if direct:
                # Déjà au bon format : copie directe dans le canal (sans retélécharger).
                sent = await _channel_send(lambda: message.copy(chat_id=settings.TELEGRAM_CHANNEL_ID, caption=caption))
                thumb_bytes = await _telegram_thumb(client, media)
            else:
                free = shutil.disk_usage(TMP_DIR).free
                if size * 2.2 > free:
                    raise _Stop(
                        f"Pas assez de disque pour convertir ({size // 2**20} Mo, il reste {free // 2**20} Mo). "
                        "Convertis-le en MP4 sur ton PC (ffmpeg -i in.mkv -c copy -movflags +faststart out.mp4) et renvoie-le."
                    )
                if _job_lock.locked():
                    await ui.set("⏳ En file d'attente (un fichier est en cours de traitement)…", force=True)
                async with _job_lock:
                    # Tout le dossier temporaire (source + MP4 converti) est effacé à la sortie du bloc.
                    with tempfile.TemporaryDirectory(dir=TMP_DIR) as tmp:
                        await ui.set("⬇️ Téléchargement…", force=True)
                        src = await client.download_media(
                            message, file_name=os.path.join(tmp, "src"), progress=_transfer_cb(ui, "⬇️ Téléchargement")
                        )
                        dst = os.path.join(tmp, f"{p.episode:03d}.mp4")
                        info = await media_service.remux_to_mp4(src, dst, on_progress=_convert_cb(ui))
                        os.remove(src)  # libère le disque dès la conversion finie
                        duration, subs, reencoded = info["duration"], info["subtitle_tracks"], info["video_reencoded"]
                        thumb_bytes = await media_service.extract_frame(dst, duration)
                        await ui.set("⬆️ Envoi dans le canal…", force=True)
                        sent = await _channel_send(
                            lambda: client.send_document(
                                settings.TELEGRAM_CHANNEL_ID, dst, caption=caption, force_document=True,
                                progress=_transfer_cb(ui, "⬆️ Envoi dans le canal"),
                            )
                        )

            thumb_msg_id = await _store_thumb(client, thumb_bytes)
            replaced = await _save_episode(
                ctx, language, p.episode, sent, duration, allow_replace=replace_ok, thumb_msg_id=thumb_msg_id
            )
            saved = True

            notes = []
            if p.multi:
                notes.append(f"Multi rangé en {p.lang}")
            if p.slot_defaulted:
                notes.append("aucun emplacement dans la légende : Saison 1")
            if subs:
                notes.append("pistes de sous-titres séparées ignorées")
            if reencoded:
                notes.append("vidéo réencodée en H.264")
            if unverified:
                notes.append("⚠️ format non vérifié (fichier trop gros pour l'analyser) : si le lecteur affiche une erreur, réencode-le")
            await status.edit_text(
                f"✅ {ctx['anime_title']} — {ctx['season_label']} — {p.lang} — épisode {p.episode}"
                f"{' (remplacé)' if replaced else ''}" + (f"\nℹ️ {' · '.join(notes)}" if notes else "")
            )
        except asyncio.CancelledError:
            # /cancel : tout s'est arrêté (téléchargement, ffmpeg, envoi). Si un fichier est déjà parti dans
            # le canal sans être enregistré en base, on le retire pour ne pas laisser d'orphelin.
            if not saved:
                for orphan in (sent.id if sent is not None else None, thumb_msg_id):
                    if orphan:
                        try:
                            await client.delete_messages(settings.TELEGRAM_CHANNEL_ID, orphan)
                        except Exception:  # noqa: BLE001
                            logger.warning("message orphelin %s non supprimé", orphan, exc_info=True)
            try:
                await status.edit_text("🛑 Annulé : traitement arrêté, fichiers temporaires effacés.")
            except Exception:  # noqa: BLE001
                pass
            raise
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
        uid = message.from_user.id
        task = asyncio.create_task(_process(client, message))
        _tasks.add(task)
        _jobs.setdefault(uid, set()).add(task)

        def _finished(t: asyncio.Task, uid: int = uid) -> None:
            _tasks.discard(t)
            mine = _jobs.get(uid)
            if mine is not None:
                mine.discard(t)
                if not mine:
                    _jobs.pop(uid, None)

        task.add_done_callback(_finished)
        raise StopPropagation  # empêche l'ancien système /upload de retraiter le fichier
