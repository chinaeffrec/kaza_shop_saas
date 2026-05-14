"""
Throttled Telegram send queue.

Telegram API limits:
  - 30 messages/sec overall
  - 1 message/sec per chat (to same user)

This queue serialises outgoing messages through a single asyncio task per
BotInstance, sleeping 1/25 s between sends (slightly under the 30/s cap to
leave headroom).  When Redis is available, unsent items survive a process
restart (Redis list as the backing store).  Without Redis the queue is
in-memory only and items are lost on restart — acceptable for reminders.

Usage:
    queue = TelegramQueue(bot, shop_id)
    await queue.start()                     # launch background sender task
    await queue.enqueue(chat_id, text, ...)
    await queue.stop()                      # graceful shutdown
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from app.core.redis_client import get_redis

logger = logging.getLogger(__name__)

_SEND_INTERVAL = 1 / 25   # 25 msg/sec → safely under Telegram 30/sec cap
_REDIS_KEY_TPL = "tg_queue:{shop_id}"


@dataclass
class _QueueItem:
    chat_id: int
    text: str
    parse_mode: str = "HTML"
    reply_markup: Optional[dict] = None


class TelegramQueue:
    def __init__(self, bot, shop_id: int):
        self._bot = bot
        self._shop_id = shop_id
        self._queue: asyncio.Queue[_QueueItem] = asyncio.Queue()
        self._task: Optional[asyncio.Task] = None
        self._redis_key = _REDIS_KEY_TPL.format(shop_id=shop_id)

    # ── public ────────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Запускает фоновый таск-отправщик; загружает незавершённые задачи из Redis."""
        await self._load_from_redis()
        self._task = asyncio.create_task(
            self._sender_loop(), name=f"tg_queue_{self._shop_id}"
        )
        logger.info("TelegramQueue started for shop_id=%s", self._shop_id)

    async def stop(self) -> None:
        """Мягкая остановка: ждёт опустошения очереди, затем отменяет таск."""
        if self._task and not self._task.done():
            # Даём разумное время (5 с) на дренаж очереди
            try:
                await asyncio.wait_for(self._queue.join(), timeout=5.0)
            except asyncio.TimeoutError:
                pass
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("TelegramQueue stopped for shop_id=%s", self._shop_id)

    async def enqueue(
        self,
        chat_id: int,
        text: str,
        parse_mode: str = "HTML",
    ) -> None:
        """Добавляет сообщение в очередь. Персистирует в Redis если доступен."""
        item = _QueueItem(chat_id=chat_id, text=text, parse_mode=parse_mode)
        await self._persist_to_redis(item)
        await self._queue.put(item)

    # ── internal ──────────────────────────────────────────────────────────────

    async def _sender_loop(self) -> None:
        while True:
            try:
                item = await self._queue.get()
                try:
                    await self._bot.send_message(
                        chat_id=item.chat_id,
                        text=item.text,
                        parse_mode=item.parse_mode,
                    )
                except Exception as exc:
                    logger.warning(
                        "TelegramQueue: failed to send to chat_id=%s: %s",
                        item.chat_id, exc,
                    )
                finally:
                    self._queue.task_done()
                await asyncio.sleep(_SEND_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("TelegramQueue sender_loop error: %s", exc)
                await asyncio.sleep(1)

    async def _persist_to_redis(self, item: _QueueItem) -> None:
        r = get_redis()
        if r is None:
            return
        try:
            payload = json.dumps({
                "chat_id": item.chat_id,
                "text": item.text,
                "parse_mode": item.parse_mode,
            })
            await r.rpush(self._redis_key, payload)
            await r.expire(self._redis_key, 86400)  # 24 ч TTL
        except Exception as exc:
            logger.warning("TelegramQueue persist_to_redis failed: %s", exc)

    async def _load_from_redis(self) -> None:
        """При старте переносит незавершённые сообщения из Redis в локальную очередь."""
        r = get_redis()
        if r is None:
            return
        try:
            items = await r.lrange(self._redis_key, 0, -1)
            await r.delete(self._redis_key)
            for raw in items:
                try:
                    d = json.loads(raw)
                    item = _QueueItem(
                        chat_id=d["chat_id"],
                        text=d["text"],
                        parse_mode=d.get("parse_mode", "HTML"),
                    )
                    await self._queue.put(item)
                except Exception:
                    pass
            if items:
                logger.info(
                    "TelegramQueue: loaded %d pending messages from Redis for shop_id=%s",
                    len(items), self._shop_id,
                )
        except Exception as exc:
            logger.warning("TelegramQueue load_from_redis failed: %s", exc)
