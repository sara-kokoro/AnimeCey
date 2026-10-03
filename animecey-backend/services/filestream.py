"""Telegram FileStream — stream files directly from Telegram via MTProto.

Based on PyroFileStreamBot architecture:
  1. Get file metadata from a channel message
  2. Create/reuse media session for the correct DC
  3. Stream chunks via raw upload.GetFile (no size limit, supports Range)
"""

from __future__ import annotations

import asyncio
import logging
import math
from typing import AsyncGenerator

from pyrogram import Client, raw
from pyrogram.errors import AuthBytesInvalid
from pyrogram.file_id import FileId, FileType, ThumbnailSource
from pyrogram.session import Auth, Session
from pyrogram.types import Message

logger = logging.getLogger(__name__)

_session_locks: dict[int, asyncio.Lock] = {}


def _chunk_size(length: int) -> int:
    return 2 ** max(min(math.ceil(math.log2(length / 1024)), 10), 2) * 1024


def _offset_fix(offset: int, chunk: int) -> int:
    return offset - (offset % chunk)


def get_media_from_message(msg: Message):
    """Extract the media object from a Message."""
    for kind in ("video", "document", "audio", "animation", "voice", "video_note"):
        media = getattr(msg, kind, None)
        if media is not None:
            return media
    return None


def get_file_properties(msg: Message) -> FileId:
    """Decode file_id from a message and attach size/name metadata."""
    media = get_media_from_message(msg)
    if media is None:
        raise ValueError("Message has no downloadable media")

    fid = FileId.decode(media.file_id)
    fid.file_size = getattr(media, "file_size", 0)
    fid.mime_type = getattr(media, "mime_type", "video/mp4")
    fid.file_name = getattr(media, "file_name", "video.mp4")
    return fid


async def _get_media_session(client: Client, dc_id: int) -> Session:
    """Create or reuse a media session for a specific DC."""
    if dc_id not in _session_locks:
        _session_locks[dc_id] = asyncio.Lock()

    async with _session_locks[dc_id]:
        existing = client.media_sessions.get(dc_id)
        if existing is not None:
            return existing

        test_mode = await client.storage.test_mode()

        if dc_id != await client.storage.dc_id():
            # Different DC — create new session + export/import auth
            auth_key = await Auth(client, dc_id, test_mode).create()
            media_session = Session(client, dc_id, auth_key, test_mode, is_media=True)
            await media_session.start()

            for _ in range(6):
                exported = await client.invoke(
                    raw.functions.auth.ExportAuthorization(dc_id=dc_id)
                )
                try:
                    await media_session.send(
                        raw.functions.auth.ImportAuthorization(
                            id=exported.id, bytes=exported.bytes
                        )
                    )
                except AuthBytesInvalid:
                    continue
                else:
                    break
            else:
                await media_session.stop()
                raise AuthBytesInvalid
        else:
            # Same DC — reuse main session's auth key
            auth_key = await client.storage.auth_key()
            media_session = Session(client, dc_id, auth_key, test_mode, is_media=True)
            await media_session.start()

        client.media_sessions[dc_id] = media_session
        return media_session


def _get_location(fid: FileId):
    """Build InputFileLocation from a FileId."""
    if fid.file_type == FileType.PHOTO:
        return raw.types.InputPhotoFileLocation(
            id=fid.media_id,
            access_hash=fid.access_hash,
            file_reference=fid.file_reference,
            thumb_size=fid.thumbnail_size,
        )
    return raw.types.InputDocumentFileLocation(
        id=fid.media_id,
        access_hash=fid.access_hash,
        file_reference=fid.file_reference,
        thumb_size=fid.thumbnail_size,
    )


async def yield_file(
    client: Client,
    msg: Message,
    offset: int,
    first_part_cut: int,
    last_part_cut: int,
    part_count: int,
    chunk_sz: int,
) -> AsyncGenerator[bytes, None]:
    """Yield file chunks from Telegram servers via MTProto."""
    fid = get_file_properties(msg)
    media_session = await _get_media_session(client, fid.dc_id)
    location = _get_location(fid)

    r = await media_session.send(
        raw.functions.upload.GetFile(location=location, offset=offset, limit=chunk_sz)
    )
    if not isinstance(r, raw.types.upload.File):
        return

    for current_part in range(1, part_count + 1):
        chunk = r.bytes
        if not chunk:
            break

        if part_count == 1:
            yield chunk[first_part_cut:last_part_cut]
        elif current_part == 1:
            yield chunk[first_part_cut:]
        elif current_part == part_count:
            yield chunk[:last_part_cut]  # CORRECTIF : avant, le dernier morceau n'était pas coupé
        else:
            yield chunk

        if current_part < part_count:
            offset += chunk_sz
            r = await media_session.send(
                raw.functions.upload.GetFile(location=location, offset=offset, limit=chunk_sz)
            )


async def stream_media(
    client: Client,
    msg: Message,
    range_start: int = 0,
    range_end: int | None = None,
) -> tuple[AsyncGenerator[bytes, None], int, int, int, str, str]:
    """High-level streaming: handles Range parsing and returns generator + metadata.

    Returns:
        (body_generator, from_bytes, until_bytes, file_size, mime_type, file_name)
    """
    fid = get_file_properties(msg)
    file_size = fid.file_size
    mime_type = fid.mime_type or "video/mp4"
    file_name = fid.file_name or "video.mp4"

    if file_size == 0:
        raise ValueError("File size is 0 — cannot stream")

    from_bytes = range_start
    until_bytes = range_end if range_end is not None else file_size - 1
    until_bytes = min(until_bytes, file_size - 1)
    if from_bytes < 0 or from_bytes > until_bytes:
        raise ValueError("range invalide")

    req_length = until_bytes - from_bytes + 1
    chunk_sz = _chunk_size(req_length)
    offset = _offset_fix(from_bytes, chunk_sz)
    first_part_cut = from_bytes - offset
    last_part_cut = (until_bytes % chunk_sz) + 1
    # CORRECTIF : nombre de blocs réellement touchés (une petite plage peut chevaucher 2 blocs)
    part_count = until_bytes // chunk_sz - offset // chunk_sz + 1

    body = yield_file(client, msg, offset, first_part_cut, last_part_cut, part_count, chunk_sz)
    return body, from_bytes, until_bytes, file_size, mime_type, file_name
