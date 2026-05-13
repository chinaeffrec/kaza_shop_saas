import httpx
from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.services.api_auth import bot_headers

router = Router()
BASE_URL = "http://app:8000"
_BACK_BTN = [[InlineKeyboardButton(text="⬅️ В меню", callback_data="menu_back")]]


async def _fetch_faq(shop_id: int = 1) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{BASE_URL}/faq/",
                headers=bot_headers(shop_id=shop_id),
            )
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return []


@router.callback_query(F.data == "menu_faq")
async def open_faq(callback: CallbackQuery, shop_id: int = 1):
    all_items = await _fetch_faq(shop_id)
    items = [i for i in all_items if i.get("is_active")]

    if not items:
        await callback.message.edit_text(
            "❓ FAQ пока пуст.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=_BACK_BTN),
        )
        await callback.answer()
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=item["question"], callback_data=f"faq_{item['id']}")]
        for item in items
    ] + _BACK_BTN)

    await callback.message.edit_text(
        "❓ <b>Часто задаваемые вопросы</b>", reply_markup=kb, parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("faq_"))
async def show_faq_answer(callback: CallbackQuery, shop_id: int = 1):
    item_id = int(callback.data.split("_")[1])
    all_items = await _fetch_faq(shop_id)
    items = {i["id"]: i for i in all_items}
    item = items.get(item_id)

    if not item:
        await callback.answer("Вопрос не найден", show_alert=True)
        return

    await callback.message.edit_text(
        f"❓ <b>{item['question']}</b>\n\n{item['answer']}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ К вопросам", callback_data="menu_faq")],
            [InlineKeyboardButton(text="🏠 В меню", callback_data="menu_back")],
        ]),
        parse_mode="HTML",
    )
    await callback.answer()
