"""
Обработчик отзывов покупателей.

Флоу:
  1. Когда заказ переходит в «delivered» — order_service отправляет
     покупателю сообщение с inline-кнопками ⭐–⭐⭐⭐⭐⭐.
  2. Покупатель нажимает рейтинг → callback rv_{order_id}_{product_id}_{rating}.
  3. Бот сохраняет рейтинг в FSM-состоянии и предлагает добавить текст.
  4. Покупатель пишет текст или нажимает «Пропустить» → отзыв сохраняется через API.
"""
import httpx
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.bot.i18n import t
from app.bot.services.api_auth import API_URL, bot_headers

router = Router()


class ReviewState(StatesGroup):
    waiting_text = State()


# ── Обработчик нажатия звезды ─────────────────────────────────────────────────

@router.callback_query(F.data.regexp(r"^rv_\d+_\d+_[1-5]$"))
async def review_rate(
    callback: CallbackQuery,
    state: FSMContext,
    shop_id: int = 1,
    lang: str = "ru",
):
    """Пользователь нажал звезду — сохраняем рейтинг, просим текст."""
    parts = callback.data.split("_")   # ["rv", order_id, product_id, rating]
    order_id  = int(parts[1])
    product_id = int(parts[2])
    rating    = int(parts[3])

    await state.set_state(ReviewState.waiting_text)
    await state.update_data(
        rv_order_id=order_id,
        rv_product_id=product_id,
        rv_rating=rating,
        rv_shop_id=shop_id,
        lang=lang,
    )

    stars_display = "⭐" * rating
    prompt = t("review.rated", lang, stars=stars_display) + "\n\n" + t("review.text_prompt", lang)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("review.skip_btn", lang), callback_data="review_skip_text")]
    ])
    try:
        await callback.message.edit_text(prompt, reply_markup=kb)
    except Exception:
        await callback.message.answer(prompt, reply_markup=kb)
    await callback.answer()


# ── Пропустить текст ──────────────────────────────────────────────────────────

@router.callback_query(F.data == "review_skip_text")
async def review_skip_text(
    callback: CallbackQuery,
    state: FSMContext,
    shop_id: int = 1,
    lang: str = "ru",
):
    data = await state.get_data()
    lang = data.get("lang", lang)
    await _submit_review(
        user_id=callback.from_user.id,
        shop_id=data.get("rv_shop_id", shop_id),
        order_id=data.get("rv_order_id"),
        product_id=data.get("rv_product_id"),
        rating=data.get("rv_rating", 5),
        text=None,
    )
    await state.clear()
    try:
        await callback.message.edit_text(t("review.saved", lang))
    except Exception:
        await callback.message.answer(t("review.saved", lang))
    await callback.answer()


# ── Текст отзыва ──────────────────────────────────────────────────────────────

@router.message(ReviewState.waiting_text, F.text)
async def review_text(
    message: Message,
    state: FSMContext,
    shop_id: int = 1,
    lang: str = "ru",
):
    data = await state.get_data()
    lang = data.get("lang", lang)
    text = message.text.strip() if message.text and message.text != "/skip" else None

    await _submit_review(
        user_id=message.from_user.id,
        shop_id=data.get("rv_shop_id", shop_id),
        order_id=data.get("rv_order_id"),
        product_id=data.get("rv_product_id"),
        rating=data.get("rv_rating", 5),
        text=text,
    )
    await state.clear()
    await message.answer(t("review.saved", lang))


@router.message(ReviewState.waiting_text)
async def review_text_non_text(message: Message, state: FSMContext, lang: str = "ru"):
    data = await state.get_data()
    lang = data.get("lang", lang)
    await message.answer(
        t("review.text_must_be_text", lang),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t("review.skip_btn", lang), callback_data="review_skip_text")]
        ])
    )


# ── HTTP helper ───────────────────────────────────────────────────────────────

async def _submit_review(
    user_id: int,
    shop_id: int,
    order_id: int | None,
    product_id: int | None,
    rating: int,
    text: str | None,
) -> None:
    """Отправляет отзыв в API. Молча игнорирует ошибки."""
    if not order_id or not product_id:
        return
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            await client.post(
                f"{API_URL}/reviews/bot",
                json={
                    "order_id":   order_id,
                    "product_id": product_id,
                    "user_id":    user_id,
                    "rating":     rating,
                    "text":       text,
                },
                headers=bot_headers(user_id, shop_id),
            )
    except Exception:
        pass
