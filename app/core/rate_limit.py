"""
Переиспользуемый Redis-based rate limiter для FastAPI-зависимостей.

Использование:
    # Некритичные эндпоинты (export/import) — fail-open: пропускает при недоступности Redis.
    @router.get("/export")
    async def export(
        _: None = Depends(rate_limit("export", max_requests=10, window=60)),
        ...
    ):

    # Критичные эндпоинты (auth, payments) — fail-closed: блокирует при недоступности Redis.
    @router.post("/login")
    async def login(
        _: None = Depends(rate_limit("login", max_requests=5, window=60, fail_open=False)),
        ...
    ):

Ключ включает IP-адрес клиента, что защищает от перегрузки со стороны
одного пользователя без блокировки всех остальных.

fail_open=True  — при недоступности Redis запрос пропускается (подходит для export/import).
fail_open=False — при недоступности Redis запрос блокируется с HTTP 503 (для auth/payments).
"""
import logging
from typing import Callable

from fastapi import Depends, HTTPException, Request

from app.core.redis_client import redis_expire, redis_incr, redis_ttl

logger = logging.getLogger(__name__)


def rate_limit(
    name: str,
    max_requests: int = 10,
    window: int = 60,
    *,
    fail_open: bool = True,
) -> Callable:
    """
    Возвращает FastAPI-зависимость, которая ограничивает число запросов.

    Args:
        name:         суффикс Redis-ключа (e.g. "export", "login")
        max_requests: максимальное количество запросов в window секунд
        window:       временное окно в секундах
        fail_open:    True  → пропустить запрос если Redis недоступен (некритичные ручки)
                      False → вернуть HTTP 503 если Redis недоступен (критичные ручки)
    """
    async def _check(request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        key = f"rl:{name}:{ip}"

        count = await redis_incr(key)
        if count is None:
            if fail_open:
                logger.warning("rate_limit: Redis unavailable, skipping check for %s", key)
                return
            logger.error("rate_limit: Redis unavailable, blocking request for %s (fail-closed)", key)
            raise HTTPException(
                status_code=503,
                detail="Сервис временно недоступен. Попробуйте позже.",
                headers={"Retry-After": "10"},
            )

        if count == 1:
            await redis_expire(key, window)

        if count > max_requests:
            ttl = max(await redis_ttl(key), 1)
            raise HTTPException(
                status_code=429,
                detail=f"Слишком много запросов. Повторите через {ttl} сек.",
                headers={"Retry-After": str(ttl)},
            )

    return Depends(_check)
