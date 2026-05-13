"""
Сервис инвалидации кэша каталога в боте.

В multi-tenant режиме каждый бот слушает reload-cache только для своего shop_id.
Endpoint бота: POST /reload-cache  (body: {"shop_id": N} или без тела — reload all)
"""
import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

_invalidate_task: asyncio.Task | None = None


async def _do_invalidate(shop_id: int | None = None) -> None:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            body = {"shop_id": shop_id} if shop_id else {}
            await client.post("http://bot:8001/reload-cache", json=body)
            logger.debug("Bot catalog cache invalidated for shop_id=%s", shop_id)
    except Exception as e:
        logger.warning("Could not invalidate bot catalog cache: %s", e)


async def invalidate_catalog_cache(shop_id: int | None = None) -> None:
    """Fire-and-forget: инвалидирует кэш конкретного магазина (или всех если shop_id=None)."""
    global _invalidate_task
    _invalidate_task = asyncio.create_task(_do_invalidate(shop_id))
