"""
Maintenance mode manager.

Хранит состояние режима обслуживания в Redis (key: platform:maintenance).
При недоступности Redis — считает режим выключенным (fail-open).

Middleware проверяет состояние при каждом запросе; исключённые пути
(health, platform/auth, platform/maintenance) обрабатываются всегда.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from app.core.redis_client import redis_delete, redis_get, redis_set

logger = logging.getLogger(__name__)

_KEY = "platform:maintenance"
# 24-часовой TTL — подстраховка на случай краша без вызова деактивации
_TTL = 86_400

# Пути, для которых maintenance mode НЕ применяется
EXCLUDED_PREFIXES: tuple[str, ...] = (
    "/health",
    "/platform/auth",
    "/platform/maintenance",
    "/docs",
    "/redoc",
    "/openapi.json",
)


async def get_maintenance_state() -> Optional[dict]:
    """
    Возвращает dict с ключами active/message/started_at/started_by,
    или None если режим выключен / Redis недоступен.
    """
    raw = await redis_get(_KEY)
    if raw is None:
        return None
    try:
        state = json.loads(raw)
        if not state.get("active"):
            return None
        return state
    except Exception:
        return None


async def set_maintenance(
    active: bool,
    message: str = "",
    started_by: str = "",
) -> dict:
    """
    Включает или выключает режим обслуживания.
    Возвращает текущий state-dict.
    """
    state: dict = {
        "active": active,
        "message": message or "Ведутся технические работы. Попробуйте позже.",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "started_by": started_by,
    }
    if active:
        ok = await redis_set(_KEY, json.dumps(state), ex=_TTL)
        if not ok:
            logger.warning("maintenance: Redis SET failed — state stored in-memory only")
        logger.warning("MAINTENANCE MODE ENABLED by %s", started_by)
    else:
        await redis_delete(_KEY)
        logger.info("MAINTENANCE MODE DISABLED by %s", started_by)
    return state
