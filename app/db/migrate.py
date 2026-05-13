"""
Ручной скрипт для применения SQL-миграций.
Для новых изменений схемы используйте Alembic:
  alembic revision --autogenerate -m "описание"
  alembic upgrade head
"""
import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings

logger = logging.getLogger(__name__)
_cfg = get_settings()

MIGRATIONS = [
    # Пример: "ALTER TABLE products ADD COLUMN IF NOT EXISTS weight INTEGER DEFAULT 0;",
]


async def run_migrations():
    engine = create_async_engine(_cfg.database_url, echo=True)
    async with engine.begin() as conn:
        for sql in MIGRATIONS:
            logger.info("Running: %s", sql[:80])
            await conn.execute(text(sql))
    await engine.dispose()
    logger.info("Migrations complete")


if __name__ == "__main__":
    asyncio.run(run_migrations())
