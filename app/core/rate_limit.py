"""
Переиспользуемый Redis-based rate limiter для FastAPI-зависимостей.

Использование:
    @router.get("/export")
    async def export(
        _: None = Depends(rate_limit("export", max_requests=10, window=60)),
        ...
    ):

Ключ включает IP-адрес клиента, что защищает от перегрузки со стороны
одного пользователя без блокировки всех остальных.

Если Redis недоступен — запрос пропускается (fail-open), логируется warning.
Это осознанное решение: export/import не являются критичными security-эндпоинтами,
и отказ rate limiter не должен лишать всех пользователей доступа к экспорту.
"""
import logging
from typing import Callable

from fastapi import Depends, HTTPException, Request

from app.core.redis_client import redis_expire, redis_incr, redis_ttl

logger = logging.getLogger(__name__)


def rate_limit(name: str, max_requests: int = 10, window: int = 60) -> Callable:
    """
    Возвращает FastAPI-зависимость, которая ограничивает число запросов.

    Args:
        name: суффикс Redis-ключа (e.g. "export", "import")
        max_requests: максимальное количество запросов в window секунд
        window: временное окно в секундах
    """
    async def _check(request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        key = f"rl:{name}:{ip}"

        count = await redis_incr(key)
        if count is None:
            # Redis недоступен — fail-open: пропускаем с предупреждением
            logger.warning("rate_limit: Redis unavailable, skipping check for %s", key)
            return

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
