"""
BotManager: управляет жизненным циклом Telegram-ботов.

Для каждого активного магазина с заполненным bot_token создаётся
отдельный BotInstance: собственный Bot, Dispatcher и CatalogCache.
shop_id и catalog_cache инжектируются в хендлеры через dp["key"].

Backward-compat: если таблица shops пуста или ни у одного магазина нет
bot_token — запускается один бот из переменной среды BOT_TOKEN для shop_id=1.
"""

import asyncio
import logging
from dataclasses import dataclass, field

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from sqlalchemy import select

from app.bot.handlers.cart import router as cart_router
from app.bot.handlers.cart_actions import router as cart_actions_router
from app.bot.handlers.catalog import router as catalog_router
from app.bot.handlers.faq import router as faq_router
from app.bot.handlers.language import router as language_router
from app.bot.handlers.review import router as review_router
from app.bot.handlers.menu import router as menu_router
from app.bot.handlers.start import router as start_router
from app.bot.middlewares.i18n_middleware import I18nMiddleware
from app.bot.services.catalog_cache import CatalogCache
from app.core.config import get_settings
from app.core.encryption import decrypt_field
from app.core.telegram_queue import TelegramQueue
from app.db.session import SessionLocal
from app.models.platform import Shop
from app.services.abandoned_cart_service import AbandonedCartService

logger = logging.getLogger(__name__)
_cfg = get_settings()


def _make_storage():
    try:
        from aiogram.fsm.storage.redis import RedisStorage
        storage = RedisStorage.from_url(_cfg.redis_url)
        return storage
    except Exception as e:
        from aiogram.fsm.storage.memory import MemoryStorage
        logger.warning("Redis недоступен (%s) — MemoryStorage. Состояния сбросятся при рестарте.", e)
        return MemoryStorage()


def _build_dispatcher(shop_id: int, cache: CatalogCache) -> Dispatcher:
    """Создаёт Dispatcher с инжектированными shop_id и catalog_cache."""
    dp = Dispatcher(storage=_make_storage())

    # aiogram v3: значения из dp["key"] автоматически инжектируются
    # в хендлеры как именованные параметры.
    dp["shop_id"] = shop_id
    dp["catalog_cache"] = cache

    # i18n middleware: injects `lang` into every handler
    dp.message.middleware(I18nMiddleware())
    dp.callback_query.middleware(I18nMiddleware())

    dp.include_router(start_router)
    dp.include_router(language_router)
    dp.include_router(review_router)
    dp.include_router(faq_router)
    dp.include_router(menu_router)
    dp.include_router(catalog_router)
    dp.include_router(cart_router)
    dp.include_router(cart_actions_router)

    return dp


@dataclass
class BotInstance:
    shop_id: int
    bot_token: str
    bot: Bot = field(init=False)
    dp: Dispatcher = field(init=False)
    cache: CatalogCache = field(init=False)
    tg_queue: TelegramQueue = field(init=False)
    abandoned_cart_svc: AbandonedCartService = field(init=False)
    _task: asyncio.Task | None = field(default=None, init=False)

    def __post_init__(self):
        self.cache = CatalogCache(shop_id=self.shop_id)
        self.bot = Bot(
            token=self.bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        self.dp = _build_dispatcher(self.shop_id, self.cache)
        self.tg_queue = TelegramQueue(self.bot, self.shop_id)
        self.abandoned_cart_svc = AbandonedCartService(self.shop_id, self.tg_queue)

    async def start(self) -> None:
        await self.cache.load()
        await self.tg_queue.start()
        self.abandoned_cart_svc.start()
        logger.info("Starting bot for shop_id=%s", self.shop_id)
        self._task = asyncio.create_task(
            self._supervised_polling(),
            name=f"bot_shop_{self.shop_id}",
        )

    async def _supervised_polling(self) -> None:
        """
        B5: Supervisor-loop вокруг start_polling.
        При неожиданном завершении (сбой сети, Telegram API ошибка) —
        перезапускает polling с экспоненциальным backoff.
        Остановка через CancelledError (от stop()) завершает loop без перезапуска.
        """
        backoff = 5  # секунд, начальный интервал
        _MAX_BACKOFF = 300

        while True:
            try:
                logger.info("Polling started for shop_id=%s", self.shop_id)
                await self.dp.start_polling(self.bot, handle_signals=False)
                # start_polling вернулся штатно — выходим
                logger.info("Polling finished cleanly for shop_id=%s", self.shop_id)
                return
            except asyncio.CancelledError:
                logger.info("Polling cancelled for shop_id=%s", self.shop_id)
                raise  # propagate — это intentional stop()
            except Exception as exc:
                logger.error(
                    "Bot polling crashed for shop_id=%s: %s. "
                    "Restarting in %ds...",
                    self.shop_id, exc, backoff,
                )
                try:
                    await asyncio.sleep(backoff)
                except asyncio.CancelledError:
                    raise
                backoff = min(backoff * 2, _MAX_BACKOFF)

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self.abandoned_cart_svc.stop()
        await self.tg_queue.stop()
        await self.bot.session.close()
        logger.info("Stopped bot for shop_id=%s", self.shop_id)

    async def reload_cache(self) -> None:
        await self.cache.load()
        logger.info("Cache reloaded for shop_id=%s", self.shop_id)

    @property
    def task(self) -> asyncio.Task | None:
        return self._task


class BotManager:
    def __init__(self):
        self._instances: dict[int, BotInstance] = {}

    async def load_from_db(self) -> None:
        """
        Загружает активные магазины из БД. Для каждого с заполненным
        bot_token создаёт BotInstance. Если таблица пуста или токены
        не заданы — откатывается к legacy-режиму (shop_id=1, env BOT_TOKEN).
        """
        try:
            async with SessionLocal() as session:
                result = await session.execute(
                    select(Shop).where(Shop.status == "active")
                )
                shops = result.scalars().all()
        except Exception as e:
            logger.warning("Cannot load shops from DB (%s) — falling back to legacy mode", e)
            shops = []

        loaded = 0
        for shop in shops:
            raw_token = shop.bot_token
            if not raw_token:
                continue
            try:
                token = decrypt_field(raw_token)
            except Exception as e:
                logger.warning("Cannot decrypt bot_token for shop_id=%s: %s", shop.id, e)
                continue
            self._instances[shop.id] = BotInstance(shop_id=shop.id, bot_token=token)
            loaded += 1

        if loaded == 0:
            # Legacy / single-tenant fallback
            legacy_token = _cfg.bot_token
            if legacy_token:
                logger.info("No active shops with bot_token found — using legacy BOT_TOKEN for shop_id=1")
                self._instances[1] = BotInstance(shop_id=1, bot_token=legacy_token)
            else:
                logger.error("No bot_token available — no bots will start")

    async def start_all(self) -> None:
        for inst in self._instances.values():
            await inst.start()
        logger.info("Started %d bot(s)", len(self._instances))

    async def stop_all(self) -> None:
        for inst in self._instances.values():
            await inst.stop()

    async def reload_cache(self, shop_id: int | None = None) -> None:
        """Перезагружает кэш конкретного магазина или всех если shop_id=None."""
        if shop_id is not None:
            inst = self._instances.get(shop_id)
            if inst:
                await inst.reload_cache()
            else:
                logger.warning("reload_cache: no bot instance for shop_id=%s", shop_id)
        else:
            for inst in self._instances.values():
                await inst.reload_cache()

    async def wait_all(self) -> None:
        """Ожидает завершения всех polling-задач."""
        tasks = [inst.task for inst in self._instances.values() if inst.task]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def get_instance(self, shop_id: int) -> BotInstance | None:
        return self._instances.get(shop_id)

    @property
    def shop_ids(self) -> list[int]:
        return list(self._instances.keys())
