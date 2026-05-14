import time

import httpx
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.bot.keyboards.menu import main_menu
from app.bot.services.bot_messages import track
from app.bot.services.api_auth import API_URL, bot_headers
from app.bot.i18n import normalize_lang, t
from app.bot.middlewares.i18n_middleware import set_user_lang

router = Router()
DEFAULT_WELCOME = "👋 Добро пожаловать!\n\nВыберите действие:"

_last_start: dict[int, float] = {}


@router.message(Command("start"))
async def start_handler(message: Message, shop_id: int = 1, lang: str = "ru"):
    user_id = message.from_user.id
    now = time.time()

    if user_id in _last_start and (now - _last_start[user_id]) < 3:
        try:
            await message.delete()
        except Exception:
            pass
        return
    _last_start[user_id] = now

    user = message.from_user

    # Авто-определение языка при первом старте
    tg_lang = normalize_lang(user.language_code if user else None)
    if tg_lang != lang:
        await set_user_lang(user.id, shop_id, tg_lang)
        lang = tg_lang

    try:
        async with httpx.AsyncClient(timeout=3) as client:
            await client.post(
                f"{API_URL}/users/register",
                json={
                    "id": user.id,
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                },
                headers=bot_headers(user.id, shop_id),
            )
    except Exception:
        pass

    welcome_text = t("welcome.default", lang)
    miniapp_url: str | None = None
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(
                f"{API_URL}/settings/public",
                headers=bot_headers(shop_id=shop_id),
            )
            if r.status_code == 200:
                cfg = r.json()
                welcome_text = cfg.get("welcome_message") or t("welcome.default", lang)
                miniapp_url = cfg.get("miniapp_url") or None
    except Exception:
        pass

    sent = await message.answer(welcome_text, reply_markup=main_menu(miniapp_url, lang))
    track(message.chat.id, sent.message_id)
