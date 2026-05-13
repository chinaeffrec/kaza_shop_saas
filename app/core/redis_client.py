"""
Единый асинхронный Redis-клиент для всего приложения.
Используется для rate limiting, refresh-токенов, инвалидации кеша.

Клиент создаётся лениво при первом обращении и переиспользуется
через всё время жизни процесса. Все операции выполняются с явным
try/except — Redis недоступность не должна ронять основной функционал
(в таких случаях вызывающий код падает на in-memory fallback или
пропускает операцию).
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
    if _client is None:
        try:
            _client = aioredis.from_url(
                get_settings().redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
                retry_on_timeout=False,
            )
        except Exception as exc:
            logger.warning("Redis client init failed: %s", exc)
    return _client


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
