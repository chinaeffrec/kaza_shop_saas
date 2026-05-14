"""
I18n middleware для aiogram v3.

Извлекает язык пользователя из Redis → БД → language_code Telegram.
Устанавливает data['lang'], который инжектируется в хендлеры как параметр `lang: str`.

Redis-ключ:  user_lang:{shop_id}:{telegram_id}  TTL 24 ч
"""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from app.bot.i18n import DEFAULT_LANGUAGE, normalize_lang

logger = logging.getLogger(__name__)

_LANG_TTL = 86400  # 24 часа


def _redis_key(shop_id: int, user_id: int) -> str:
    return f"user_lang:{shop_id}:{user_id}"


async def _get_lang_from_redis(redis, shop_id: int, user_id: int) -> str | None:
    try:
        val = await redis.get(_redis_key(shop_id, user_id))
        return val.decode() if val else None
    except Exception:
        return None


async def _set_lang_in_redis(redis, shop_id: int, user_id: int, lang: str) -> None:
    try:
        await redis.set(_redis_key(shop_id, user_id), lang, ex=_LANG_TTL)
    except Exception:
        pass


async def get_user_lang(user_id: int, shop_id: int, redis=None) -> str:
    """
    Публичная функция: возвращает язык пользователя.
    Порядок: Redis → БД → DEFAULT_LANGUAGE.
    """
    if redis:
        cached = await _get_lang_from_redis(redis, shop_id, user_id)
        if cached:
            return cached

    try:
        from app.db.session import SessionLocal
        from app.models.user import User
        from sqlalchemy import select

        async with SessionLocal() as session:
            res = await session.execute(
                select(User.language).where(
                    User.telegram_id == user_id,
                    User.shop_id == shop_id,
                )
            )
            row = res.scalar_one_or_none()
            if row:
                lang = row or DEFAULT_LANGUAGE
                if redis:
                    await _set_lang_in_redis(redis, shop_id, user_id, lang)
                return lang
    except Exception as exc:
        logger.debug("i18n: DB lookup failed for user %s: %s", user_id, exc)

    return DEFAULT_LANGUAGE


async def set_user_lang(user_id: int, shop_id: int, lang: str, redis=None) -> None:
    """Сохраняет язык в БД и Redis."""
    # Redis
    if redis:
        await _set_lang_in_redis(redis, shop_id, user_id, lang)

    # DB
    try:
        from app.db.session import SessionLocal
        from app.models.user import User
        from sqlalchemy import select

        async with SessionLocal() as session:
            res = await session.execute(
                select(User).where(
                    User.telegram_id == user_id,
                    User.shop_id == shop_id,
                )
            )
            user = res.scalar_one_or_none()
            if user:
                user.language = lang
                await session.commit()
    except Exception as exc:
        logger.error("i18n: failed to save lang to DB: %s", exc)


class I18nMiddleware(BaseMiddleware):
    """
    Middleware для aiogram v3 Dispatcher.
    Добавляет `lang` в data хендлера.
    """

    def __init__(self, redis=None, default_lang: str = DEFAULT_LANGUAGE) -> None:
        self._redis = redis
        self._default = default_lang

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        shop_id: int = data.get("shop_id", 1)

        lang = self._default
        if user:
            lang = await get_user_lang(user.id, shop_id, self._redis)
            if lang == DEFAULT_LANGUAGE and user.language_code:
                # Если в БД/Redis ещё нет — берём из Telegram и сохраняем
                tg_lang = normalize_lang(user.language_code)
                if tg_lang != DEFAULT_LANGUAGE:
                    await set_user_lang(user.id, shop_id, tg_lang, self._redis)
                    lang = tg_lang

        data["lang"] = lang
        return await handler(event, data)
