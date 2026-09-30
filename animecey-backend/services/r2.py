"""Cloudflare R2 (S3-compatible) storage for the full JSON document of each title.

Neon keeps only a light index (``catalog_titles``). The complete document
(rich metadata + seasons -> languages -> episodes -> links) lives in R2 under
``titles/<uuid>.json``.

boto3 is synchronous, so every call is offloaded with ``asyncio.to_thread`` and
bounded by a semaphore: a burst of refreshes cannot exhaust the HTTP pool or
the default thread pool.

Usage::

    from services.r2 import r2, R2NotFoundError

    await r2.put_title(title.id, document)
    try:
        document = await r2.get_title(title.id)
    except R2NotFoundError:
        ...  # index row exists but JSON is missing -> trigger a re-import
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import uuid
from datetime import date, datetime
from typing import Any, Callable, TypeVar

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

from config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")

TITLES_PREFIX = "titles/"
_JSON_CONTENT_TYPE = "application/json; charset=utf-8"
# Error codes meaning "this key/bucket does not exist" (get -> NoSuchKey, head -> 404).
_NOT_FOUND_CODES = frozenset({"NoSuchKey", "NotFound", "404"})


# ── Errors ─────────────────────────────────────────────────────────────


class R2Error(Exception):
    """Base class for every R2 failure."""


class R2NotConfiguredError(R2Error):
    """R2 environment variables are missing."""


class R2NotFoundError(R2Error):
    """The requested object (or bucket) does not exist."""

    def __init__(self, key: str) -> None:
        super().__init__(f"R2 object not found: {key}")
        self.key = key


class R2InvalidDocumentError(R2Error):
    """A document could not be serialised, or the stored object is not a JSON object."""


# ── Helpers ────────────────────────────────────────────────────────────


def title_key(title_id: uuid.UUID | str) -> str:
    """Return the R2 key of a title document.

    The id is round-tripped through ``uuid.UUID`` so a malformed value can never
    produce an unexpected key (``../``, extra slashes, ...). Raises ``ValueError``
    if ``title_id`` is not a valid UUID.
    """
    return f"{TITLES_PREFIX}{uuid.UUID(str(title_id))}.json"


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


# ── Storage ────────────────────────────────────────────────────────────


class R2Storage:
    """Thin async wrapper around boto3's S3 client pointed at Cloudflare R2."""

    def __init__(
        self,
        *,
        access_key_id: str,
        secret_access_key: str,
        bucket: str,
        endpoint_url: str,
        public_url: str = "",
        max_concurrency: int = 10,
    ) -> None:
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key
        self._bucket = bucket
        self._endpoint_url = endpoint_url
        self._public_url = public_url
        self._max_concurrency = max_concurrency
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._client: Any = None
        self._client_lock = threading.Lock()

    @classmethod
    def from_settings(cls) -> "R2Storage":
        return cls(
            access_key_id=settings.R2_ACCESS_KEY_ID,
            secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            bucket=settings.R2_BUCKET_NAME,
            endpoint_url=settings.R2_ENDPOINT_URL,
            public_url=settings.R2_PUBLIC_URL,
        )

    @property
    def is_configured(self) -> bool:
        return all(
            (self._access_key_id, self._secret_access_key, self._bucket, self._endpoint_url)
        )

    # -- client ---------------------------------------------------------

    def _get_client(self) -> Any:
        """Build the boto3 client lazily (thread-safe). boto3 clients are thread-safe."""
        client = self._client
        if client is not None:
            return client
        with self._client_lock:
            if self._client is None:
                if not self.is_configured:
                    raise R2NotConfiguredError(self._not_configured_message())
                config = BotoConfig(
                    signature_version="s3v4",
                    retries={"max_attempts": 3, "mode": "standard"},
                    connect_timeout=5,
                    read_timeout=20,
                    max_pool_connections=self._max_concurrency + 5,
                    s3={"addressing_style": "path"},
                    # boto3 >= 1.36 adds CRC32 checksums by default; only send/validate
                    # them when an operation requires it (keeps R2 compatibility).
                    request_checksum_calculation="when_required",
                    response_checksum_validation="when_required",
                )
                self._client = boto3.client(
                    "s3",
                    endpoint_url=self._endpoint_url,
                    aws_access_key_id=self._access_key_id,
                    aws_secret_access_key=self._secret_access_key,
                    region_name="auto",
                    config=config,
                )
                logger.info("R2 client initialised (bucket=%s)", self._bucket)
            return self._client

    @staticmethod
    def _not_configured_message() -> str:
        return (
            "R2 is not configured: set R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, "
            "R2_BUCKET_NAME and R2_ENDPOINT_URL."
        )

    async def _call(self, op: str, key: str, func: Callable[[Any], T]) -> T:
        """Run ``func(client)`` in a worker thread and translate errors to ``R2Error``."""
        if not self.is_configured:
            raise R2NotConfiguredError(self._not_configured_message())

        async with self._semaphore:
            try:
                return await asyncio.to_thread(lambda: func(self._get_client()))
            except R2Error:
                raise
            except ClientError as exc:
                code = str(exc.response.get("Error", {}).get("Code", ""))
                if code in _NOT_FOUND_CODES:
                    raise R2NotFoundError(key) from exc
                logger.error("R2 %s failed for %s: %s", op, key, code or exc)
                raise R2Error(f"R2 {op} failed for '{key}': {code or exc}") from exc
            except (BotoCoreError, OSError) as exc:
                logger.error("R2 %s network/client error for %s: %s", op, key, exc)
                raise R2Error(f"R2 {op} failed for '{key}': {exc}") from exc

    # -- generic JSON API ----------------------------------------------

    async def put_json(
        self,
        key: str,
        data: dict[str, Any],
        *,
        cache_control: str | None = None,
    ) -> int:
        """Serialise ``data`` and upload it (overwrites). Returns the payload size in bytes."""
        try:
            payload = json.dumps(
                data, ensure_ascii=False, separators=(",", ":"), default=_json_default
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise R2InvalidDocumentError(
                f"Document for '{key}' is not JSON-serialisable: {exc}"
            ) from exc

        extra: dict[str, Any] = {}
        if cache_control:
            extra["CacheControl"] = cache_control

        def _put(client: Any) -> None:
            client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=payload,
                ContentType=_JSON_CONTENT_TYPE,
                **extra,
            )

        await self._call("put", key, _put)
        logger.info("R2 put %s (%d bytes)", key, len(payload))
        return len(payload)

    async def get_json(self, key: str) -> dict[str, Any]:
        """Download and parse a JSON object. Raises ``R2NotFoundError`` if absent."""

        def _get(client: Any) -> bytes:
            response = client.get_object(Bucket=self._bucket, Key=key)
            body = response["Body"]
            try:
                return body.read()
            finally:
                body.close()

        raw: bytes = await self._call("get", key, _get)
        try:
            document = json.loads(raw)
        except ValueError as exc:  # JSONDecodeError and UnicodeDecodeError
            logger.error("R2 object %s is not valid JSON: %s", key, exc)
            raise R2InvalidDocumentError(f"R2 object '{key}' is not valid JSON: {exc}") from exc
        if not isinstance(document, dict):
            raise R2InvalidDocumentError(
                f"R2 object '{key}' must be a JSON object, got {type(document).__name__}"
            )
        return document

    async def delete(self, key: str) -> None:
        """Delete an object. Idempotent: deleting a missing key is not an error."""
        await self._call(
            "delete", key, lambda client: client.delete_object(Bucket=self._bucket, Key=key)
        )
        logger.info("R2 delete %s", key)

    async def exists(self, key: str) -> bool:
        try:
            await self._call(
                "head", key, lambda client: client.head_object(Bucket=self._bucket, Key=key)
            )
        except R2NotFoundError:
            return False
        return True

    async def ping(self) -> bool:
        """Return True if the bucket is reachable with the current credentials."""
        try:
            await self._call(
                "ping", self._bucket, lambda client: client.head_bucket(Bucket=self._bucket)
            )
        except R2Error as exc:
            logger.warning("R2 ping failed: %s", exc)
            return False
        return True

    def public_url_for(self, key: str) -> str | None:
        """Public URL of an object, if ``R2_PUBLIC_URL`` is configured."""
        return f"{self._public_url}/{key}" if self._public_url else None

    # -- title documents ------------------------------------------------

    async def put_title(self, title_id: uuid.UUID | str, document: dict[str, Any]) -> int:
        return await self.put_json(title_key(title_id), document)

    async def get_title(self, title_id: uuid.UUID | str) -> dict[str, Any]:
        return await self.get_json(title_key(title_id))

    async def delete_title(self, title_id: uuid.UUID | str) -> None:
        await self.delete(title_key(title_id))


r2 = R2Storage.from_settings()


def get_r2() -> R2Storage:
    """FastAPI dependency: ``r2: R2Storage = Depends(get_r2)``."""
    return r2
