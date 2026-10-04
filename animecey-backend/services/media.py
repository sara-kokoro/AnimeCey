"""Préparation des vidéos pour le navigateur : MKV -> MP4 (H.264 + AAC) sans réencoder la vidéo."""

from __future__ import annotations

import asyncio
import json
import logging
import os

logger = logging.getLogger(__name__)


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


async def remux_to_mp4(src: str, dst: str) -> dict:
    """Copie la vidéo H.264 telle quelle, passe l'audio en AAC si besoin, place le moov au début."""
    info = await probe(src)
    streams = info.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    subs = [s for s in streams if s.get("codec_type") == "subtitle"]
    if video is None:
        raise MediaError("Aucune piste vidéo trouvée.")
    if video.get("codec_name") != "h264" or video.get("pix_fmt") not in (None, "yuv420p"):
        raise MediaError(
            f"Vidéo en {video.get('codec_name')} ({video.get('pix_fmt')}) : "
            "la plupart des navigateurs ne la lisent pas. Il faut du H.264 8 bits, "
            "ou réencoder sur ton PC."
        )

    audio_codec = "copy" if audio and audio.get("codec_name") in ("aac", "mp3") else "aac"
    cmd = ["ffmpeg", "-y", "-i", src, "-map", "0:v:0", "-map", "0:a:0?", "-c:v", "copy", "-c:a", audio_codec]
    if audio_codec == "aac":
        cmd += ["-b:a", "192k"]
    cmd += ["-sn", "-dn", "-movflags", "+faststart", dst]
    code, _, err = await _run(*cmd, timeout=3600)
    if code != 0:
        raise MediaError(f"ffmpeg a échoué : {err.decode(errors='ignore')[-300:]}")

    duration = None
    try:
        duration = int(float(info.get("format", {}).get("duration") or 0)) or None
    except (TypeError, ValueError):
        pass
    return {"duration": duration, "subtitle_tracks": len(subs), "audio_reencoded": audio_codec == "aac"}


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
