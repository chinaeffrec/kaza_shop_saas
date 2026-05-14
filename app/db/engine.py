"""
SQLAlchemy async engine.

HA-расширения:
  • Поддержка PgBouncer: если задан DB_PGBOUNCER_URL, подключаемся через пулер.
    В transaction-mode PgBouncer pool_pre_ping отключается (SET/SHOW команды
    несовместимы с этим режимом), pool_size уменьшается — соединения держит сам пулер.
  • Retry при transient ошибках (разрыв соединения, TooManyConnections):
    tenacity делает до 4 попыток с экспоненциальной выдержкой.
"""
from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import get_settings

logger = logging.getLogger(__name__)
_settings = get_settings()


def _build_engine() -> AsyncEngine:
    # Если задан PgBouncer URL — используем его; иначе прямое подключение к БД.
    url = _settings.db_pgbouncer_url or _settings.database_url

    # В transaction-mode PgBouncer нельзя использовать pool_pre_ping
    # (он отправляет SELECT 1, а транзакции не завершены).
    via_bouncer = bool(_settings.db_pgbouncer_url)

    kwargs: dict = {
        "echo": False,
        "pool_pre_ping": not via_bouncer,
        "pool_recycle": 1800,
    }

    if via_bouncer:
        # PgBouncer управляет пулом — приложению нужны минимальные соединения.
        kwargs["pool_size"] = 2
        kwargs["max_overflow"] = 3
    else:
        kwargs["pool_size"] = 10
        kwargs["max_overflow"] = 20

    if via_bouncer:
        logger.info("DB engine: using PgBouncer at %s", url.split("@")[-1])
    else:
        logger.info("DB engine: direct PostgreSQL at %s", url.split("@")[-1])

    return create_async_engine(url, **kwargs)


engine = _build_engine()
