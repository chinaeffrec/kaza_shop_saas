import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config


def _upgrade_head() -> None:
    cfg_path = Path(__file__).resolve().parents[2] / "alembic.ini"
    cfg = Config(str(cfg_path))
    command.upgrade(cfg, "head")


async def run_migrations_to_head() -> None:
    await asyncio.to_thread(_upgrade_head)
