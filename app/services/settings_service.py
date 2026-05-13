"""
Сервис настроек магазина.

get_shop_settings(session, shop_id) — загружает настройки конкретного магазина.
При первом обращении (строки нет) — создаёт с дефолтными значениями.
"""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.settings import ShopSettings

logger = logging.getLogger(__name__)


async def get_shop_settings(session: AsyncSession, shop_id: int = 1) -> ShopSettings:
    """Загружает настройки магазина shop_id. Создаёт запись если её нет."""
    res = await session.execute(
        select(ShopSettings).where(ShopSettings.shop_id == shop_id)
    )
    s = res.scalar_one_or_none()
    if not s:
        # Backward compat: для shop_id=1 также проверяем legacy-запись с id=1
        if shop_id == 1:
            legacy = await session.execute(
                select(ShopSettings).where(ShopSettings.id == 1)
            )
            s = legacy.scalar_one_or_none()
            if s and s.shop_id is None:
                s.shop_id = 1
                await session.commit()
                return s

        s = ShopSettings(shop_id=shop_id)
        session.add(s)
        await session.flush()
        await session.commit()
    return s


def invalidate_settings_cache() -> None:
    """Оставлен для совместимости вызовов — кэша нет."""
    pass
