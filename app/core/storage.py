"""
Pluggable media storage backends.

  LocalStorage (default) — writes to /app/media, serves via /media/<filename>.
    Compatible with all existing single-host setups; no extra dependencies.

  S3Storage — uploads to any S3-compatible service (AWS S3, MinIO,
    Yandex Object Storage, Cloudflare R2, etc.).
    Requires boto3 and: S3_ENDPOINT, S3_BUCKET, S3_ACCESS_KEY, S3_SECRET_KEY.
    Enables true horizontal scaling — multiple app replicas share one bucket.

Switch backends via STORAGE_BACKEND env var: "local" (default) or "s3".
"""
from __future__ import annotations

import asyncio
import logging
from functools import lru_cache
from pathlib import Path

import aiofiles

logger = logging.getLogger(__name__)


class LocalStorage:
    """Saves files to the local media directory. Default backend."""

    def __init__(self, media_dir: str = "/app/media", url_prefix: str = "/media") -> None:
        self._dir = Path(media_dir)
        self._prefix = url_prefix.rstrip("/")

    async def save(self, filename: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        self._dir.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(self._dir / filename, "wb") as f:
            await f.write(data)
        return self.url(filename)

    async def delete(self, filename: str) -> None:
        (self._dir / filename).unlink(missing_ok=True)

    def url(self, filename: str) -> str:
        return f"{self._prefix}/{filename}"

    def path(self, filename: str) -> Path:
        """Return the absolute local Path (for background compression tasks)."""
        return self._dir / filename


class S3Storage:
    """
    S3-compatible storage backend.
    Uses boto3 in a thread executor to keep the event loop non-blocking.
    Files are served directly from S3 (or CDN) via s3_public_url.
    """

    def __init__(
        self,
        endpoint: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        public_url: str = "",
    ) -> None:
        self._endpoint = endpoint
        self._bucket = bucket
        self._access_key = access_key
        self._secret_key = secret_key
        self._public_url = public_url.rstrip("/") or f"{endpoint.rstrip('/')}/{bucket}"

    def _client(self):
        import boto3  # noqa: PLC0415  (optional dep — only required for S3 backend)
        return boto3.client(
            "s3",
            endpoint_url=self._endpoint,
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
        )

    async def save(self, filename: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        client = self._client()
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: client.put_object(
                Bucket=self._bucket,
                Key=filename,
                Body=data,
                ContentType=content_type,
                # Files are content-addressed (UUID in name) — safe to cache aggressively.
                CacheControl="public, max-age=31536000, immutable",
            ),
        )
        return self.url(filename)

    async def delete(self, filename: str) -> None:
        client = self._client()
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.delete_object(Bucket=self._bucket, Key=filename),
            )
        except Exception as exc:
            logger.warning("S3Storage.delete(%s): %s", filename, exc)

    def url(self, filename: str) -> str:
        return f"{self._public_url}/{filename}"


@lru_cache(maxsize=1)
def get_storage() -> LocalStorage | S3Storage:
    from app.core.config import get_settings  # local import avoids circular dependency
    cfg = get_settings()
    if cfg.storage_backend == "s3":
        if not all([cfg.s3_endpoint, cfg.s3_bucket, cfg.s3_access_key, cfg.s3_secret_key]):
            raise ValueError(
                "STORAGE_BACKEND=s3 requires S3_ENDPOINT, S3_BUCKET, "
                "S3_ACCESS_KEY, and S3_SECRET_KEY to be set."
            )
        logger.info("Storage: S3 → %s / %s", cfg.s3_endpoint, cfg.s3_bucket)
        return S3Storage(
            endpoint=cfg.s3_endpoint,
            bucket=cfg.s3_bucket,
            access_key=cfg.s3_access_key,
            secret_key=cfg.s3_secret_key,
            public_url=cfg.s3_public_url,
        )
    logger.info("Storage: local → %s", cfg.media_dir)
    return LocalStorage(media_dir=cfg.media_dir)
