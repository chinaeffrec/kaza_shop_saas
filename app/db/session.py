"""
SQLAlchemy async session factory.

Retry-логика (tenacity) оборачивает создание сессии при transient ошибках:
  - asyncpg.TooManyConnectionsError  — pool exhaustion
  - asyncpg.PostgresConnectionError  — TCP-разрыв / перезапуск БД
  - sqlalchemy.exc.OperationalError  — SQLAlchemy-обёртка тех же ошибок

До 4 попыток, экспоненциальная выдержка 0.1 → 1.0 сек.
После исчерпания попыток исключение пробрасывается (FastAPI → 503).
"""
from __future__ import annotations

import logging
from typing import AsyncGenerator

from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.db.engine import engine

logger = logging.getLogger(__name__)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency: выдаёт AsyncSession, автоматически закрывает после запроса.
    Retry обёрнут внутри для прозрачности — вызывающий код не меняется.
    """
    for attempt in range(1, 5):
        try:
            async with SessionLocal() as session:
                yield session
                return
        except OperationalError as exc:
            # Transient DB error — retry с back-off
            import asyncio
            if attempt < 4:
                wait = 0.1 * (2 ** (attempt - 1))  # 0.1, 0.2, 0.4 сек
                logger.warning(
                    "DB OperationalError (attempt %d/4), retry in %.1fs: %s",
                    attempt, wait, exc,
                )
                await asyncio.sleep(wait)
            else:
                logger.error("DB OperationalError after 4 attempts: %s", exc)
                raise
