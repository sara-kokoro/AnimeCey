"""Préparation des vidéos pour le navigateur.

- H.264 8 bits : MKV/AVI -> MP4 sans réencoder la vidéo (rapide, sans perte).
- Autre codec vidéo (mpeg4/Xvid, HEVC, H.264 10 bits...) : réencodage en H.264 8 bits (LENT : prévoir
  plusieurs heures sur un petit serveur ; désactivable avec ENCODE_ENABLED=false).
- Audio autre que AAC/MP3 (AC3, DTS...) : converti en AAC.

La progression est envoyée à un callback pour que le bot l'affiche dans Telegram.
Variables d'environnement facultatives : ENCODE_ENABLED, ENCODE_PRESET, ENCODE_CRF, ENCODE_TIMEOUT.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "") or default)
    except ValueError:
        return default


ENCODE_ENABLED = os.getenv("ENCODE_ENABLED", "true").strip().lower() in ("1", "true", "yes", "on")
ENCODE_PRESET = os.getenv("ENCODE_PRESET", "veryfast")  # ultrafast = plus rapide mais plus lourd ; slow = plus petit
ENCODE_CRF = str(_env_int("ENCODE_CRF", 23))             # 18 = très bonne qualité, 28 = léger
ENCODE_TIMEOUT = _env_int("ENCODE_TIMEOUT", 12 * 3600)   # secondes (réencodage / conversion du son)
COPY_TIMEOUT = 3600                                       # secondes (simple copie MKV -> MP4)

# (secondes traitées, durée totale, vitesse ffmpeg ou None, mode « copy » | « audio » | « encode »)
ProgressCb = Callable[[float, float, "float | None", str], Awaitable[None]]


class MediaError(Exception):
    """Fichier inutilisable tel quel (message affiché à l'admin)."""


async def _run(*cmd: str, timeout: int) -> tuple[int, bytes, bytes]:
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise MediaError("ffmpeg a dépassé le temps maximum")
    return proc.returncode, out, err


async def probe(path: str) -> dict:
    code, out, err = await _run(
        "ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", path,
        timeout=120,
    )
    if code != 0:
        raise MediaError(f"ffprobe a échoué : {err.decode(errors='ignore')[-200:]}")
    return json.loads(out or b"{}")


def _first(streams: list[dict], kind: str) -> dict | None:
    return next((s for s in streams if s.get("codec_type") == kind), None)


def _video_ok(video: dict) -> bool:
    return video.get("codec_name") == "h264" and video.get("pix_fmt") in (None, "yuv420p")


def _audio_ok(audio: dict | None) -> bool:
    return audio is None or audio.get("codec_name") in ("aac", "mp3")


def is_browser_ready(info: dict) -> bool | None:
    """True : lisible tel quel (H.264 8 bits + audio AAC/MP3). False : à convertir. None : pas de vidéo."""
    streams = info.get("streams", [])
    video = _first(streams, "video")
    if video is None:
        return None
    return _video_ok(video) and _audio_ok(_first(streams, "audio"))


async def _run_ffmpeg(
    cmd: list[str], *, total: float, mode: str, on_progress: ProgressCb | None, timeout: int
) -> None:
    """Lance ffmpeg en priorité basse (pour ne pas écraser le streaming) et suit sa progression."""
    nice = shutil.which("nice")
    full = ([nice, "-n", "19"] if nice else []) + cmd
    proc = await asyncio.create_subprocess_exec(
        *full, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    err_task = asyncio.create_task(proc.stderr.read())
    done = 0.0
    speed: float | None = None

    async def _pump() -> None:
        nonlocal done, speed
        async for raw in proc.stdout:
            key, _, val = raw.decode(errors="ignore").strip().partition("=")
            if key in ("out_time_us", "out_time_ms"):  # les deux sont en microsecondes
                try:
                    done = max(int(val), 0) / 1_000_000
                except ValueError:
                    pass
            elif key == "speed":
                try:
                    speed = float(val.strip().rstrip("x"))
                except ValueError:
                    speed = None
            elif key == "progress" and on_progress is not None:
                try:
                    await on_progress(done, total, speed, mode)
                except Exception:  # noqa: BLE001 — l'affichage ne doit jamais casser la conversion
                    logger.debug("callback de progression en échec", exc_info=True)
        await proc.wait()

    try:
        await asyncio.wait_for(_pump(), timeout=timeout)
    except asyncio.TimeoutError:
        raise MediaError("ffmpeg a dépassé le temps maximum")
    finally:
        if proc.returncode is None:  # timeout ou annulation : on n'abandonne pas un ffmpeg orphelin
            proc.kill()
            await proc.wait()
        err = await err_task
    if proc.returncode != 0:
        raise MediaError(f"ffmpeg a échoué : {err.decode(errors='ignore')[-300:]}")


async def remux_to_mp4(src: str, dst: str, on_progress: ProgressCb | None = None) -> dict:
    """Produit un MP4 lisible partout.

    Vidéo H.264 8 bits : copiée telle quelle. Sinon : réencodée en H.264 (si ENCODE_ENABLED).
    Audio AAC/MP3 : copié. Sinon : converti en AAC. L'index (moov) est placé au début.
    """
    info = await probe(src)
    streams = info.get("streams", [])
    video = _first(streams, "video")
    audio = _first(streams, "audio")
    subs = [s for s in streams if s.get("codec_type") == "subtitle"]
    if video is None:
        raise MediaError("Aucune piste vidéo trouvée.")

    duration = None
    try:
        duration = int(float(info.get("format", {}).get("duration") or 0)) or None
    except (TypeError, ValueError):
        pass

    encode_video = not _video_ok(video)
    reencode_audio = audio is not None and not _audio_ok(audio)
    if encode_video and not ENCODE_ENABLED:
        raise MediaError(
            f"Vidéo en {video.get('codec_name')} ({video.get('pix_fmt')}) : "
            "la plupart des navigateurs ne la lisent pas. Il faut du H.264 8 bits, "
            "ou réencoder sur ton PC (le réencodage par le bot est désactivé : ENCODE_ENABLED=false)."
        )

    cmd = [
        "ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-progress", "pipe:1", "-nostats",
        "-fflags", "+genpts", "-i", src, "-map", "0:v:0", "-map", "0:a:0?",
    ]
    if encode_video:
        cmd += [
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "-c:v", "libx264", "-preset", ENCODE_PRESET, "-crf", ENCODE_CRF,
            "-pix_fmt", "yuv420p", "-profile:v", "high", "-max_muxing_queue_size", "1024",
        ]
    else:
        cmd += ["-c:v", "copy"]
    cmd += ["-c:a", "aac", "-b:a", "192k"] if reencode_audio else ["-c:a", "copy"]
    cmd += ["-sn", "-dn", "-movflags", "+faststart", dst]

    mode = "encode" if encode_video else ("audio" if reencode_audio else "copy")
    await _run_ffmpeg(
        cmd,
        total=float(duration or 0),
        mode=mode,
        on_progress=on_progress,
        timeout=COPY_TIMEOUT if mode == "copy" else ENCODE_TIMEOUT,
    )
    return {
        "duration": duration,
        "subtitle_tracks": len(subs),
        "audio_reencoded": reencode_audio,
        "video_reencoded": encode_video,
    }


async def extract_frame(path: str, duration: int | None) -> bytes | None:
    """Une image JPEG (640 px de large) prise à ~20 % de la vidéo. None si impossible."""
    if duration and duration > 120:
        t = max(30, int(duration * 0.2))
    elif duration:
        t = int(duration * 0.3)
    else:
        t = 5
    out = path + ".thumb.jpg"
    try:
        code, _, _ = await _run(
            "ffmpeg", "-y", "-ss", str(t), "-i", path, "-frames:v", "1",
            "-vf", "scale=640:-2", "-q:v", "4", out,
            timeout=120,
        )
        if code != 0 or not os.path.exists(out):
            return None
        with open(out, "rb") as fh:
            return fh.read() or None
    except MediaError:
        return None
    finally:
        if os.path.exists(out):
            os.remove(out)
