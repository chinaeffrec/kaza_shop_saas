"""
Единый асинхронный Redis-клиент для всего приложения.

Режимы подключения:
  1. Standalone (по умолчанию):   REDIS_URL=redis://redis:6379/0
  2. Redis Sentinel (HA):          REDIS_SENTINEL_HOSTS=s1:26379,s2:26379,s3:26379
                                   REDIS_SENTINEL_MASTER=mymaster

Sentinel-режим активируется автоматически если REDIS_SENTINEL_HOSTS задан.
В обоих режимах клиент создаётся лениво при первом обращении и переиспользуется.
Все операции обёрнуты в try/except — Redis-недоступность не должна ронять основной функционал.
"""
import logging
from typing import Optional

import redis.asyncio as aioredis

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_client: Optional[aioredis.Redis] = None


def get_redis() -> Optional[aioredis.Redis]:
    """Возвращает Redis-клиент или None если соединение не установлено."""
    global _client
    if _client is not None:
        return _client

    cfg = get_settings()

    try:
        if cfg.redis_sentinel_hosts:
            _client = _build_sentinel_client(cfg)
        else:
            _client = _build_standalone_client(cfg)
    except Exception as exc:
        logger.warning("Redis client init failed: %s", exc)

    return _client


def _build_standalone_client(cfg) -> aioredis.Redis:
    logger.info("Redis: standalone mode → %s", cfg.redis_url)
    return aioredis.from_url(
        cfg.redis_url,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
        retry_on_timeout=False,
    )


def _build_sentinel_client(cfg) -> aioredis.Redis:
    """
    Создаёт клиент через Redis Sentinel.
    Sentinel автоматически переключает на нового мастера при failover.
    """
    sentinel_hosts = []
    for item in cfg.redis_sentinel_hosts.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" in item:
            host, port_str = item.rsplit(":", 1)
            sentinel_hosts.append((host.strip(), int(port_str.strip())))
        else:
            sentinel_hosts.append((item, 26379))

    sentinel_kwargs: dict = {"decode_responses": True}
    if cfg.redis_sentinel_password:
        sentinel_kwargs["password"] = cfg.redis_sentinel_password

    logger.info(
        "Redis: Sentinel mode → master='%s' sentinels=%s",
        cfg.redis_sentinel_master,
        sentinel_hosts,
    )

    sentinel = aioredis.Sentinel(
        sentinel_hosts,
        sentinel_kwargs=sentinel_kwargs,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
    return sentinel.master_for(
        cfg.redis_sentinel_master,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


# ── Helper wrappers ───────────────────────────────────────────────────────────

async def redis_get(key: str) -> Optional[str]:
    r = get_redis()
    if r is None:
        return None
    try:
        return await r.get(key)
    except Exception as exc:
        logger.warning("Redis GET %s failed: %s", key, exc)
        return None


async def redis_set(key: str, value: str, ex: int) -> bool:
    r = get_redis()
    if r is None:
        return False
    try:
        await r.set(key, value, ex=ex)
        return True
    except Exception as exc:
        logger.warning("Redis SET %s failed: %s", key, exc)
        return False


async def redis_delete(*keys: str) -> bool:
    r = get_redis()
    if r is None:
        return False
    try:
        await r.delete(*keys)
        return True
    except Exception as exc:
        logger.warning("Redis DEL %s failed: %s", keys, exc)
        return False


async def redis_incr(key: str) -> Optional[int]:
    r = get_redis()
    if r is None:
        return None
    try:
        return await r.incr(key)
    except Exception as exc:
        logger.warning("Redis INCR %s failed: %s", key, exc)
        return None


async def redis_expire(key: str, seconds: int) -> bool:
    r = get_redis()
    if r is None:
        return False
    try:
        await r.expire(key, seconds)
        return True
    except Exception as exc:
        logger.warning("Redis EXPIRE %s failed: %s", key, exc)
        return False


async def redis_ttl(key: str) -> int:
    r = get_redis()
    if r is None:
        return -2
    try:
        return await r.ttl(key)
    except Exception as exc:
        logger.warning("Redis TTL %s failed: %s", key, exc)
        return -2
