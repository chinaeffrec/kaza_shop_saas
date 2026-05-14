import httpx
from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.bot.i18n import t
from app.bot.services.api_auth import API_URL, bot_headers

router = Router()


@router.callback_query(F.data.startswith("cart_add_"))
async def add_to_cart(callback: CallbackQuery, shop_id: int = 1, lang: str = "ru"):
    product_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                f"{API_URL}/cart/",
                json={"user_id": user_id, "product_id": product_id, "quantity": 1},
                headers=bot_headers(user_id, shop_id),
            )
        if resp.status_code == 200:
            await callback.answer(t("cart.added", lang))
        else:
            await callback.answer(t("error.connection", lang), show_alert=True)
    except httpx.RequestError:
        await callback.answer(t("error.connection", lang), show_alert=True)
