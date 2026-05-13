import time

import httpx
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.bot.keyboards.menu import main_menu
from app.bot.services.bot_messages import track
from app.bot.services.api_auth import bot_headers

router = Router()
BASE_URL = "http://app:8000"
DEFAULT_WELCOME = "👋 Добро пожаловать!\n\nВыберите действие:"

_last_start: dict[int, float] = {}


@router.message(Command("start"))
async def start_handler(message: Message, shop_id: int = 1):
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
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            await client.post(
                f"{BASE_URL}/users/register",
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

    welcome_text = DEFAULT_WELCOME
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(
                f"{BASE_URL}/settings/public",
                headers=bot_headers(shop_id=shop_id),
            )
            if r.status_code == 200:
                welcome_text = r.json().get("welcome_message") or DEFAULT_WELCOME
    except Exception:
        pass

    sent = await message.answer(welcome_text, reply_markup=main_menu())
    track(message.chat.id, sent.message_id)
