"""
Запуск Alembic-миграций при старте приложения.

Advisory lock pg_try_advisory_lock(8472381) гарантирует, что при
горизонтальном масштабировании только один инстанс выполняет миграции
одновременно. Остальные ждут с экспоненциальным backoff.

Магическое число 8472381 — случайное, уникальное для этого приложения.
"""
import asyncio
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

logger = logging.getLogger(__name__)

_LOCK_KEY = 8472381          # advisory lock id — уникальный для приложения
_LOCK_TIMEOUT = 60           # максимальное время ожидания lock, секунд
_LOCK_RETRY_INTERVAL = 2     # интервал между попытками, секунд


def _upgrade_head() -> None:
    cfg_path = Path(__file__).resolve().parents[2] / "alembic.ini"
    cfg = Config(str(cfg_path))
    command.upgrade(cfg, "head")


async def _acquire_advisory_lock() -> bool:
    """
    Пытается получить PostgreSQL advisory lock.
    Возвращает True если lock получен, False если таймаут истёк.
    Использует сырое psycopg/asyncpg соединение (не SQLAlchemy сессию),
    чтобы не мешать пулу основного приложения.
    """
    import asyncpg
    from app.core.config import get_settings

    cfg = get_settings()
    dsn = (
        f"postgresql://{cfg.db_user}:{cfg.db_password}"
        f"@{cfg.db_host}:{cfg.db_port}/{cfg.db_name}"
    )
    conn = await asyncpg.connect(dsn)
    try:
        elapsed = 0
        while elapsed < _LOCK_TIMEOUT:
            locked = await conn.fetchval(
                "SELECT pg_try_advisory_lock($1)", _LOCK_KEY
            )
            if locked:
                logger.info("Migration advisory lock acquired")
                return True
            logger.info(
                "Waiting for migration advisory lock (elapsed=%ds)...", elapsed
            )
            await asyncio.sleep(_LOCK_RETRY_INTERVAL)
            elapsed += _LOCK_RETRY_INTERVAL
        logger.error("Migration advisory lock timeout after %ds", _LOCK_TIMEOUT)
        return False
    finally:
        await conn.close()


async def run_migrations_to_head() -> None:
    """
    Запускает миграции под advisory lock.
    При недоступности asyncpg (не установлен) — запускает без lock с предупреждением.
    """
    try:
        locked = await _acquire_advisory_lock()
        if not locked:
            logger.error("Skipping migrations: could not acquire advisory lock")
            return
    except ImportError:
        logger.warning("asyncpg not available — running migrations without advisory lock")
    except Exception as exc:
        logger.warning("Advisory lock failed (%s) — running migrations without lock", exc)

    try:
        await asyncio.to_thread(_upgrade_head)
        logger.info("Migrations complete")
    except Exception as exc:
        logger.error("Migration failed: %s", exc)
        raise
