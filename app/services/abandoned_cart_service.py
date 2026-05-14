"""
Сервис напоминаний о брошенных корзинах.

Логика:
  - Запускается как фоновый asyncio-таск внутри BotInstance.
  - Каждые POLL_INTERVAL секунд опрашивает БД на наличие корзин,
    обновлённых более ABANDON_THRESHOLD_HOURS назад.
  - Для каждого такого пользователя:
      1. Проверяет Redis-ключ reminded:{shop_id}:{user_id}.
         Если ключ есть — напоминание уже отправлено сегодня, пропускаем.
      2. Отправляет сообщение через TelegramQueue (throttled).
      3. Ставит Redis-ключ с TTL 24 ч.
  - Redis недоступность не роняет сервис: без Redis ключи не проверяются,
    напоминание отправляется при каждом цикле (допустимое ухудшение).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import distinct, select, text

from app.core.redis_client import redis_get, redis_set
from app.db.session import SessionLocal
from app.models.cart import Cart

if TYPE_CHECKING:
    from app.core.telegram_queue import TelegramQueue

logger = logging.getLogger(__name__)

POLL_INTERVAL = 1800          # 30 минут между проверками
ABANDON_THRESHOLD_HOURS = 1   # корзина считается брошенной через 1 час
_REDIS_REMIND_TTL = 86400     # 24 ч — не беспокоим дважды в день


def _reminded_key(shop_id: int, user_id: int) -> str:
    return f"reminded:{shop_id}:{user_id}"


class AbandonedCartService:
    def __init__(self, shop_id: int, queue: "TelegramQueue"):
        self._shop_id = shop_id
        self._queue = queue
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(
            self._loop(), name=f"abandoned_cart_{self._shop_id}"
        )
        logger.info("AbandonedCartService started for shop_id=%s", self._shop_id)

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    # ── internal ──────────────────────────────────────────────────────────────

    async def _loop(self) -> None:
        # небольшая задержка при старте, чтобы не гонять БД сразу при запуске
        await asyncio.sleep(60)
        while True:
            try:
                await self._run_once()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("AbandonedCartService error (shop_id=%s): %s", self._shop_id, exc)
            try:
                await asyncio.sleep(POLL_INTERVAL)
            except asyncio.CancelledError:
                break

    async def _run_once(self) -> None:
        threshold = datetime.now(timezone.utc) - timedelta(hours=ABANDON_THRESHOLD_HOURS)
        async with SessionLocal() as session:
            result = await session.execute(
                select(distinct(Cart.user_id)).where(
                    Cart.shop_id == self._shop_id,
                    Cart.updated_at < threshold,
                )
            )
            user_ids = result.scalars().all()

        if not user_ids:
            return

        sent = 0
        for user_id in user_ids:
            key = _reminded_key(self._shop_id, user_id)
            already_reminded = await redis_get(key)
            if already_reminded:
                continue

            text = (
                "🛒 <b>Вы забыли товары в корзине!</b>\n\n"
                "Вернитесь и оформите заказ — ваши товары ждут вас."
            )
            await self._queue.enqueue(user_id, text)
            await redis_set(key, "1", ex=_REDIS_REMIND_TTL)
            sent += 1

        if sent:
            logger.info(
                "AbandonedCartService: sent %d reminders for shop_id=%s",
                sent, self._shop_id,
            )
