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
from typing import AsyncIterator, Awaitable, Callable

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


# ── Vignette de l'épisode ───────────────────────────────────────────────
# L'image est toujours prise dans la vidéo elle-même, à 15 % de sa durée : la miniature que Telegram
# attache à un fichier (parfois personnalisée par celui qui l'a partagé) n'est jamais utilisée.

THUMB_POINTS = (0.15, 0.25, 0.40)  # 15 % d'abord ; les suivants servent seulement si l'image est quasi noire
THUMB_MIN_BYTES = 8_000            # un JPEG 640 px plus léger que ça est presque uniforme (noir, fondu...)


async def _run_quick(*cmd: str, timeout: int) -> tuple[int, bytes]:
    """Lance une commande courte en priorité basse ; elle est tuée en cas de délai dépassé ou d'annulation."""
    nice = shutil.which("nice")
    full = ([nice, "-n", "19"] if nice else []) + list(cmd)
    proc = await asyncio.create_subprocess_exec(
        *full, stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode, out
    except asyncio.TimeoutError:
        raise MediaError("ffmpeg a dépassé le temps maximum")
    finally:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()


async def _grab_frame(src: str, seconds: int, *, remote: bool) -> bytes | None:
    """Une image JPEG (640 px de large) à `seconds` ; `src` = fichier local ou adresse http."""
    import tempfile

    with tempfile.TemporaryDirectory(prefix="thumb_") as tmp:
        out = os.path.join(tmp, "thumb.jpg")
        cmd = ["ffmpeg", "-y", "-nostdin", "-loglevel", "error"]
        if remote:
            cmd += ["-rw_timeout", "30000000"]  # 30 s sans réponse -> abandon
        cmd += ["-ss", str(seconds), "-i", src, "-frames:v", "1", "-vf", "scale=640:-2", "-q:v", "4", out]
        code, _ = await _run_quick(*cmd, timeout=120)
        if code != 0 or not os.path.exists(out):
            return None
        with open(out, "rb") as fh:
            return fh.read() or None


async def _remote_duration(url: str) -> float | None:
    try:
        code, out = await _run_quick(
            "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", url,
            timeout=90,
        )
        return float(out.decode().strip()) if code == 0 and out.strip() else None
    except (MediaError, ValueError):
        return None


async def extract_frame(src: str, duration: int | None, *, remote: bool = False) -> bytes | None:
    """Image JPEG prise à 15 % de la vidéo (fichier local, ou adresse http si remote=True). None si impossible.

    Si l'image est presque noire (fondu, écran de titre), on réessaie à 25 % puis 40 %.
    """
    base = float(duration) if duration and duration > 0 else None
    if base is None and remote:
        base = await _remote_duration(src)
    times = [max(1, int(base * f)) for f in THUMB_POINTS] if base else [30, 60, 120]
    best: bytes | None = None
    for t in dict.fromkeys(times):
        try:
            data = await _grab_frame(src, t, remote=remote)
        except MediaError:
            continue
        if not data:
            continue
        if len(data) >= THUMB_MIN_BYTES:
            return data
        if best is None or len(data) > len(best):
            best = data
    return best


# Lecture à distance : ffmpeg lit la vidéo rangée dans le canal Telegram par morceaux (requêtes « Range »),
# donc seuls les quelques Mo autour de l'image voulue sont téléchargés, jamais l'épisode entier.

RangeFetch = Callable[[int, int], Awaitable["AsyncIterator[bytes]"]]  # (début, fin incluse) -> flux d'octets


class _RangeServer:
    """Mini-serveur HTTP local (127.0.0.1, port libre) qui sert un fichier distant à ffmpeg."""

    def __init__(self, size: int, fetch: RangeFetch) -> None:
        self.size = size
        self._fetch = fetch
        self._server: asyncio.AbstractServer | None = None
        self._writers: set[asyncio.StreamWriter] = set()
        self.url = ""
        self.bytes_served = 0

    async def __aenter__(self) -> "_RangeServer":
        self._server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        self.url = f"http://127.0.0.1:{self._server.sockets[0].getsockname()[1]}/video.mp4"
        return self

    async def __aexit__(self, *exc) -> None:
        if self._server is not None:
            self._server.close()
        for w in list(self._writers):
            w.close()
        if self._server is not None:
            try:
                await asyncio.wait_for(self._server.wait_closed(), 2)
            except (asyncio.TimeoutError, Exception):  # noqa: BLE001
                pass

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self._writers.add(writer)
        gen = None
        try:
            try:
                head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 15)
            except (asyncio.TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError):
                return
            lines = head.decode("latin-1").split("\r\n")
            method = lines[0].split(" ")[0].upper()
            hdr = {}
            for ln in lines[1:]:
                k, _, v = ln.partition(":")
                if v:
                    hdr[k.strip().lower()] = v.strip()
            start, end, partial = 0, self.size - 1, False
            rng = hdr.get("range", "")
            if rng.lower().startswith("bytes="):
                a, _, b = rng[6:].split(",")[0].partition("-")
                try:
                    if a == "":
                        start = max(self.size - int(b), 0)
                    else:
                        start = int(a)
                        end = min(int(b), self.size - 1) if b else self.size - 1
                except ValueError:
                    start, end = self.size, 0
                partial = True
            if start >= self.size or end < start:
                writer.write(
                    f"HTTP/1.1 416 Range Not Satisfiable\r\nContent-Range: bytes */{self.size}\r\n"
                    "Content-Length: 0\r\nConnection: close\r\n\r\n".encode()
                )
                await writer.drain()
                return
            resp = [
                "HTTP/1.1 206 Partial Content" if partial else "HTTP/1.1 200 OK",
                "Content-Type: video/mp4", "Accept-Ranges: bytes",
                f"Content-Length: {end - start + 1}", "Connection: close",
            ]
            if partial:
                resp.append(f"Content-Range: bytes {start}-{end}/{self.size}")
            writer.write(("\r\n".join(resp) + "\r\n\r\n").encode())
            await writer.drain()
            if method == "HEAD":
                return
            gen = await self._fetch(start, end)
            async for chunk in gen:
                writer.write(chunk)
                self.bytes_served += len(chunk)
                await writer.drain()
        except (ConnectionError, asyncio.CancelledError):
            pass  # ffmpeg a fermé la connexion (il a eu ce qu'il voulait) ou l'envoi est annulé
        except Exception:  # noqa: BLE001
            logger.debug("lecture à distance interrompue", exc_info=True)
        finally:
            aclose = getattr(gen, "aclose", None)
            if aclose is not None:
                try:
                    await aclose()
                except Exception:  # noqa: BLE001
                    pass
            self._writers.discard(writer)
            writer.close()


async def extract_frame_remote(fetch: RangeFetch, size: int, duration: int | None) -> bytes | None:
    """Image à 15 % d'une vidéo qui n'est pas sur le disque (fichier du canal Telegram). Ne lève jamais d'erreur."""
    if not size or size <= 0:
        return None
    try:
        async with _RangeServer(size, fetch) as srv:
            data = await extract_frame(srv.url, duration, remote=True)
            logger.info("vignette distante : %.1f Mo lus sur %.0f Mo", srv.bytes_served / 1e6, size / 1e6)
            return data
    except asyncio.CancelledError:
        raise
    except Exception:  # noqa: BLE001 — une vignette ratée ne doit jamais faire échouer l'envoi
        logger.warning("vignette distante impossible", exc_info=True)
        return None
