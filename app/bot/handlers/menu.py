import httpx
from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from app.bot.i18n import t
from app.bot.keyboards.menu import main_menu
from app.bot.services.api_auth import API_URL, APP_URL, bot_headers
from app.bot.services.bot_messages import clear_and_reset, track
from app.bot.services.navigation import navigation
from app.bot.services.render_engine import render_engine
from app.bot.states.screen import Screen

router = Router()


class CheckoutState(StatesGroup):
    waiting_comment = State()
    waiting_delivery_type = State()   # CDEK ПВЗ | ввести адрес | пропустить
    waiting_city = State()            # CDEK: ввод города
    waiting_pvz = State()             # CDEK: выбор ПВЗ из списка
    waiting_address = State()         # обычная доставка: ввод адреса
    waiting_promo = State()


_PVZ_PAGE_SIZE = 5


async def _replace_with_text(message: Message, text: str, reply_markup=None, parse_mode=None):
    try:
        if message.photo or message.document:
            try:
                await message.delete()
            except Exception:
                pass
            sent = await message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
            track(message.chat.id, sent.message_id)
        else:
            await message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception:
        sent = await message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
        track(message.chat.id, sent.message_id)


def build_cart_text(data: dict) -> str:
    lines = ["🛒 <b>Ваша корзина</b>\n"]
    for item in data["items"]:
        lines.append(f"• {item['name']} × {item['quantity']} = {_fmt_price(item['sum'])}")
    lines.append(f"\n<b>Итого: {_fmt_price(data['total'])}</b>")
    return "\n".join(lines)


def build_cart_keyboard(data: dict, lang: str = "ru") -> InlineKeyboardMarkup:
    rows = []
    for item in data["items"]:
        pid = item["product_id"]
        title = str(item.get("name", "Товар")).strip() or "Товар"
        if len(title) > 48:
            title = title[:45] + "..."
        qty = int(item.get("quantity", 0))
        rows.append([InlineKeyboardButton(text=f"🧾 {title}", callback_data=f"noop_{pid}")])
        rows.append([
            InlineKeyboardButton(text="➖", callback_data=f"dec_{pid}"),
            InlineKeyboardButton(text=f"{qty} шт.", callback_data=f"noop_{pid}"),
            InlineKeyboardButton(text="➕", callback_data=f"inc_{pid}"),
            InlineKeyboardButton(text="🗑", callback_data=f"rm_{pid}"),
        ])
    rows.append([InlineKeyboardButton(text=t("cart.checkout", lang), callback_data="checkout")])
    rows.append([InlineKeyboardButton(text=t("btn.back_menu",  lang), callback_data="menu_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _fmt_price(price: int | float) -> str:
    if isinstance(price, float) and price != int(price):
        return f"{price:,.2f} ₽".replace(",", " ")
    return f"{int(price):,} ₽".replace(",", " ")


async def _get_public_settings(shop_id: int = 1) -> dict:
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(
                f"{API_URL}/settings/public",
                headers=bot_headers(shop_id=shop_id),
            )
            if r.status_code == 200:
                return r.json()
    except Exception:
        pass
    return {}


@router.callback_query(F.data == "menu_catalog")
async def open_catalog(callback: CallbackQuery, shop_id: int = 1, lang: str = "ru"):
    user_id = callback.from_user.id
    navigation.reset(user_id)
    screen = Screen(type="categories")
    navigation.push(user_id, screen)
    await render_engine.render(screen, callback.message, shop_id=shop_id)
    await callback.answer()


@router.callback_query(F.data == "menu_cart")
async def open_cart(callback: CallbackQuery, shop_id: int = 1, lang: str = "ru"):
    user_id = callback.from_user.id
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(
                f"{API_URL}/cart/{user_id}",
                headers=bot_headers(user_id, shop_id),
            )
        data = response.json()
    except Exception:
        await callback.answer("❌ Ошибка соединения с сервером", show_alert=True)
        return

    if not data.get("items"):
        await _replace_with_text(
            callback.message,
            t("cart.empty", lang),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=t("btn.back_menu", lang), callback_data="menu_back")]
            ])
        )
    else:
        await _replace_with_text(
            callback.message,
            build_cart_text(data),
            reply_markup=build_cart_keyboard(data, lang),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data == "menu_order")
async def open_order_status(callback: CallbackQuery, shop_id: int = 1, lang: str = "ru"):
    user_id = callback.from_user.id
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(
                f"{API_URL}/orders/user/{user_id}",
                headers=bot_headers(user_id, shop_id),
            )
        orders = response.json()
        if not isinstance(orders, list):
            orders = []
    except Exception:
        await callback.answer("❌ Ошибка соединения с сервером", show_alert=True)
        return

    active = [o for o in orders if o["status"] not in ("delivered", "cancelled", "returned")]
    done = [o for o in orders if o["status"] in ("delivered",)]

    if not orders:
        text = t("orders.none", lang)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t("btn.back_menu", lang), callback_data="menu_back")]
        ])
    else:
        lines = [t("orders.active_title", lang) + "\n"] if active else [t("orders.no_active", lang) + "\n"]
        for o in active:
            status_label = o.get("status_label", o["status"])
            order_text = t("orders.order_line", lang, id=o['id']) + "\n"
            if o.get("items"):
                for it in o["items"]:
                    order_text += f"  • {it['name']} × {it['quantity']} = {_fmt_price(it['sum'])}\n"
            order_text += (
                t("orders.total_line", lang, total=_fmt_price(o['total'])) + "\n" +
                t("orders.status_line", lang, label=status_label, date=o['created_at'][:10])
            )
            lines.append(order_text)
        text = "\n\n".join(lines)

        kb_rows = []
        if done:
            kb_rows.append([InlineKeyboardButton(
                text=t("orders.history_btn", lang, count=len(done)),
                callback_data="order_history",
            )])
        kb_rows.append([InlineKeyboardButton(text=t("btn.back_menu", lang), callback_data="menu_back")])
        kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)

    await _replace_with_text(callback.message, text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "order_history")
async def order_history(callback: CallbackQuery, shop_id: int = 1, lang: str = "ru"):
    user_id = callback.from_user.id
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(
                f"{API_URL}/orders/user/{user_id}",
                headers=bot_headers(user_id, shop_id),
            )
        orders = response.json()
        if not isinstance(orders, list):
            orders = []
    except Exception:
        await callback.answer("❌ Ошибка соединения с сервером", show_alert=True)
        return

    done = [o for o in orders if o["status"] == "delivered"]

    if not done:
        text = t("orders.history_empty", lang)
    else:
        lines = [t("orders.history_title", lang) + "\n"]
        for o in done:
            order_text = t("orders.order_line", lang, id=o['id']) + "\n"
            if o.get("items"):
                for it in o["items"]:
                    order_text += f"  • {it['name']} × {it['quantity']} = {_fmt_price(it['sum'])}\n"
            order_text += f"💰 {_fmt_price(o['total'])} · {o['created_at'][:10]}"
            lines.append(order_text)
        text = "\n\n".join(lines)

    await _replace_with_text(
        callback.message, text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t("btn.back_orders", lang), callback_data="menu_order")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "menu_question")
async def open_question(callback: CallbackQuery, shop_id: int = 1, lang: str = "ru"):
    cfg = await _get_public_settings(shop_id)
    contact = cfg.get("seller_contact") or "@support"
    await _replace_with_text(
        callback.message,
        t("contact.title", lang, contact=contact),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t("btn.back_menu", lang), callback_data="menu_back")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "menu_back")
async def menu_back(callback: CallbackQuery, state: FSMContext, shop_id: int = 1, lang: str = "ru"):
    navigation.reset(callback.from_user.id)
    await state.clear()
    cfg = await _get_public_settings(shop_id)
    welcome_text = cfg.get("welcome_message") or t("welcome.default", lang)
    miniapp_url = cfg.get("miniapp_url") or None
    await _replace_with_text(callback.message, welcome_text, reply_markup=main_menu(miniapp_url, lang))
    await callback.answer()


@router.callback_query(F.data == "checkout")
async def checkout_start(callback: CallbackQuery, state: FSMContext, shop_id: int = 1, lang: str = "ru"):
    await state.set_state(CheckoutState.waiting_comment)
    await state.update_data(shop_id=shop_id, lang=lang)
    await _replace_with_text(
        callback.message,
        t("checkout.comment_prompt", lang),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t("btn.skip", lang), callback_data="checkout_skip_comment")]
        ])
    )
    await callback.answer()


async def _ask_delivery_type(target, state: FSMContext, shop_id: int = 1, lang: str = "ru"):
    """Показывает выбор способа доставки. Проверяет включён ли CDEK в настройках."""
    cdek_on = False
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(
                f"{API_URL}/settings/public",
                headers=bot_headers(shop_id=shop_id),
            )
            if r.status_code == 200:
                cdek_on = r.json().get("cdek_enabled", False)
    except Exception:
        pass

    await state.set_state(CheckoutState.waiting_delivery_type)

    if cdek_on:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t("checkout.btn_cdek",          lang), callback_data="delivery_cdek")],
            [InlineKeyboardButton(text=t("checkout.btn_manual",         lang), callback_data="delivery_manual")],
            [InlineKeyboardButton(text=t("checkout.btn_skip_delivery",  lang), callback_data="delivery_skip")],
        ])
        text = t("checkout.delivery_title", lang)
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t("checkout.btn_manual",        lang), callback_data="delivery_manual")],
            [InlineKeyboardButton(text=t("checkout.btn_skip_delivery", lang), callback_data="delivery_skip")],
        ])
        text = t("checkout.delivery_address_title", lang)

    if hasattr(target, "message"):
        await _replace_with_text(target.message, text, reply_markup=kb)
    else:
        await target.answer(text, reply_markup=kb)


@router.callback_query(F.data == "checkout_skip_comment")
async def checkout_skip_comment(callback: CallbackQuery, state: FSMContext, shop_id: int = 1, lang: str = "ru"):
    await state.update_data(comment="", lang=lang)
    await _ask_delivery_type(callback, state, shop_id, lang)
    await callback.answer()


@router.message(CheckoutState.waiting_comment, F.text)
async def checkout_comment(message: Message, state: FSMContext, shop_id: int = 1, lang: str = "ru"):
    comment = "" if message.text == "/skip" else message.text
    await state.update_data(comment=comment, lang=lang)
    await _ask_delivery_type(message, state, shop_id, lang)


# ── Delivery type selection ───────────────────────────────────────────────────

@router.callback_query(F.data == "delivery_skip")
async def delivery_skip(callback: CallbackQuery, state: FSMContext, shop_id: int = 1, lang: str = "ru"):
    await state.update_data(address="", pvz_code=None, pvz_address=None, delivery_cost=0, lang=lang)
    await _go_to_promo(callback.message, state, shop_id, lang)
    await callback.answer()


@router.callback_query(F.data == "delivery_manual")
async def delivery_manual(callback: CallbackQuery, state: FSMContext, lang: str = "ru"):
    await state.set_state(CheckoutState.waiting_address)
    await state.update_data(lang=lang)
    await _replace_with_text(
        callback.message,
        t("checkout.address_prompt", lang),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t("checkout.btn_skip_address", lang), callback_data="checkout_skip_address")]
        ])
    )
    await callback.answer()


@router.callback_query(F.data == "delivery_cdek")
async def delivery_cdek(callback: CallbackQuery, state: FSMContext, lang: str = "ru"):
    await state.set_state(CheckoutState.waiting_city)
    await state.update_data(lang=lang)
    await _replace_with_text(
        callback.message,
        t("checkout.city_prompt", lang),
    )
    await callback.answer()


# ── CDEK city search ──────────────────────────────────────────────────────────

def _pvz_keyboard(pvzs: list, page: int) -> InlineKeyboardMarkup:
    """Клавиатура с пагинацией ПВЗ (5 штук на страницу)."""
    total_pages = max(1, (len(pvzs) + _PVZ_PAGE_SIZE - 1) // _PVZ_PAGE_SIZE)
    start = page * _PVZ_PAGE_SIZE
    page_items = pvzs[start: start + _PVZ_PAGE_SIZE]

    rows = []
    for p in page_items:
        label = f"📍 {p['address']}"
        if len(label) > 60:
            label = label[:57] + "…"
        rows.append([InlineKeyboardButton(
            text=label,
            callback_data=f"pvz_{p['code']}",
        )])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀ Назад", callback_data=f"pvz_page_{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop_pvz"))
    if (page + 1) < total_pages:
        nav.append(InlineKeyboardButton(text="Далее ▶", callback_data=f"pvz_page_{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="delivery_cdek_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(CheckoutState.waiting_city, F.text)
async def checkout_city(message: Message, state: FSMContext, shop_id: int = 1, lang: str = "ru"):
    city_name = (message.text or "").strip()
    # Refresh lang from FSM in case middleware re-detects
    fsm_data = await state.get_data()
    lang = fsm_data.get("lang", lang)
    await message.answer(t("checkout.city_searching", lang))

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(
                f"{API_URL}/cdek/bot/cities",
                params={"q": city_name},
                headers=bot_headers(message.chat.id, shop_id),
            )
            cities = r.json() if r.status_code == 200 else []
    except Exception:
        cities = []

    if not cities:
        await message.answer(
            t("checkout.city_not_found", lang),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=t("checkout.btn_manual",        lang), callback_data="delivery_manual")],
                [InlineKeyboardButton(text=t("checkout.btn_skip_delivery", lang), callback_data="delivery_skip")],
            ])
        )
        return

    # Берём первый совпавший город и получаем ПВЗ
    city = cities[0]
    city_code = city.get("code")
    city_label = city.get("city", city_name)
    region = city.get("region", "")
    if region:
        city_label = f"{city_label}, {region}"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"{API_URL}/cdek/bot/pvz",
                params={"city_code": city_code},
                headers=bot_headers(message.chat.id, shop_id),
            )
            pvz_data = r.json() if r.status_code == 200 else {}
    except Exception:
        pvz_data = {}

    pvzs = pvz_data.get("items", [])
    if not pvzs:
        await message.answer(
            t("checkout.city_no_pvz", lang, city=city_label),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=t("checkout.btn_another_city",  lang), callback_data="delivery_cdek")],
                [InlineKeyboardButton(text=t("checkout.btn_manual",        lang), callback_data="delivery_manual")],
                [InlineKeyboardButton(text=t("checkout.btn_skip_delivery", lang), callback_data="delivery_skip")],
            ])
        )
        return

    await state.update_data(
        cdek_city_code=city_code,
        cdek_city_name=city_label,
        pvz_list=pvzs,
        pvz_page=0,
    )
    await state.set_state(CheckoutState.waiting_pvz)
    await message.answer(
        t("checkout.pvz_title", lang, city=city_label, count=len(pvzs)),
        parse_mode="HTML",
        reply_markup=_pvz_keyboard(pvzs, 0),
    )


@router.callback_query(F.data.startswith("pvz_page_"))
async def pvz_page(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data.split("_")[-1])
    data = await state.get_data()
    pvzs = data.get("pvz_list", [])
    await state.update_data(pvz_page=page)
    await callback.message.edit_reply_markup(reply_markup=_pvz_keyboard(pvzs, page))
    await callback.answer()


@router.callback_query(F.data == "noop_pvz")
async def noop_pvz(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(F.data == "delivery_cdek_cancel")
async def cdek_cancel(callback: CallbackQuery, state: FSMContext, shop_id: int = 1, lang: str = "ru"):
    fsm_data = await state.get_data()
    lang = fsm_data.get("lang", lang)
    await _ask_delivery_type(callback, state, shop_id, lang)
    await callback.answer()


@router.callback_query(F.data.startswith("pvz_"), ~F.data.startswith("pvz_page_"))
async def pvz_selected(callback: CallbackQuery, state: FSMContext, shop_id: int = 1, lang: str = "ru"):
    pvz_code = callback.data[4:]  # strip "pvz_"
    data = await state.get_data()
    lang = data.get("lang", lang)
    pvzs = data.get("pvz_list", [])

    # Найдём адрес выбранного ПВЗ
    matched = [p for p in pvzs if p["code"] == pvz_code]
    pvz_address = matched[0]["address"] if matched else pvz_code
    city_name = data.get("cdek_city_name", "")
    city_code = data.get("cdek_city_code")

    # Рассчитаем стоимость доставки
    delivery_cost = 0
    period_text = ""
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.post(
                f"{API_URL}/cdek/bot/calculate",
                json={"to_city_code": city_code, "weight_grams": 500},
                headers=bot_headers(callback.from_user.id, shop_id),
            )
            if r.status_code == 200:
                calc = r.json()
                delivery_cost = calc.get("total_sum", 0)
                pmin = calc.get("period_min", 0)
                pmax = calc.get("period_max", 0)
                period_text = f", {pmin}–{pmax} дн." if pmin else ""
    except Exception:
        pass

    await state.update_data(
        pvz_code=pvz_code,
        pvz_address=f"{city_name}, {pvz_address}".strip(", "),
        delivery_cost=delivery_cost,
        address="",
    )

    cost_str = t("checkout.delivery_cost", lang, cost=delivery_cost, period=period_text) if delivery_cost else ""
    pvz_text = (
        t("checkout.pvz_selected", lang, city=city_name, address=pvz_address)
        + cost_str
        + t("checkout.pvz_continue", lang)
    )
    await _replace_with_text(callback.message, pvz_text, parse_mode="HTML")
    await callback.answer()
    await _go_to_promo(callback.message, state, shop_id, lang)


# ── Address (manual) handlers ─────────────────────────────────────────────────

async def _go_to_promo(message: Message, state: FSMContext, shop_id: int = 1, lang: str = "ru"):
    await state.set_state(CheckoutState.waiting_promo)
    await message.answer(
        t("checkout.promo_prompt", lang),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t("btn.skip", lang), callback_data="checkout_skip_promo")]
        ])
    )


@router.message(CheckoutState.waiting_address, F.text)
async def checkout_address(message: Message, state: FSMContext, shop_id: int = 1, lang: str = "ru"):
    address = (message.text or "").strip()
    if address == "/skip":
        address = ""
    fsm_data = await state.get_data()
    lang = fsm_data.get("lang", lang)
    await state.update_data(address=address, pvz_code=None, pvz_address=None, delivery_cost=0)
    await _go_to_promo(message, state, shop_id, lang)


@router.callback_query(F.data == "checkout_skip_address")
async def checkout_skip_address(callback: CallbackQuery, state: FSMContext, shop_id: int = 1, lang: str = "ru"):
    fsm_data = await state.get_data()
    lang = fsm_data.get("lang", lang)
    await state.update_data(address="", pvz_code=None, pvz_address=None, delivery_cost=0)
    await _go_to_promo(callback.message, state, shop_id, lang)
    await callback.answer()


@router.callback_query(F.data == "checkout_skip_promo")
async def checkout_skip_promo(callback: CallbackQuery, state: FSMContext, shop_id: int = 1, lang: str = "ru"):
    data = await state.get_data()
    lang = data.get("lang", lang)
    await _finalize_order(
        callback.message, state,
        address=data.get("address", ""),
        shop_id=shop_id,
        promo_code=None,
        pvz_code=data.get("pvz_code"),
        pvz_address=data.get("pvz_address"),
        delivery_cost=data.get("delivery_cost", 0),
        lang=lang,
    )
    await callback.answer()


@router.message(CheckoutState.waiting_promo, F.text)
async def checkout_promo(message: Message, state: FSMContext, shop_id: int = 1, lang: str = "ru"):
    code = (message.text or "").strip().upper()
    data = await state.get_data()
    lang = data.get("lang", lang)
    address = data.get("address", "")

    if code == "/SKIP" or not code:
        await _finalize_order(
            message, state, address=address, shop_id=shop_id, promo_code=None,
            pvz_code=data.get("pvz_code"), pvz_address=data.get("pvz_address"),
            delivery_cost=data.get("delivery_cost", 0), lang=lang,
        )
        return

    # Validate promo code via API
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            # Get cart total first for validation
            cart_resp = await client.get(
                f"{API_URL}/cart/{message.chat.id}",
                headers=bot_headers(message.chat.id, shop_id),
            )
            cart_data = cart_resp.json()
            cart_total = cart_data.get("total", 0)

            promo_resp = await client.post(
                f"{API_URL}/promos/bot/validate",
                json={"code": code, "cart_total": cart_total},
                headers=bot_headers(message.chat.id, shop_id),
            )
            promo_data = promo_resp.json()
    except Exception:
        await message.answer(
            t("checkout.promo_error", lang),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=t("btn.skip", lang), callback_data="checkout_skip_promo")]
            ])
        )
        return

    if not promo_data.get("valid"):
        err = promo_data.get("message", "Промокод не найден")
        await message.answer(
            t("checkout.promo_invalid", lang, error=err),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=t("btn.skip", lang), callback_data="checkout_skip_promo")]
            ])
        )
        return

    discount = promo_data.get("discount", 0)
    final_total = promo_data.get("final_total", cart_total)
    discount_rub = discount // 100
    await message.answer(
        t("checkout.promo_applied", lang, code=code, discount=discount_rub, final=_fmt_price(final_total)),
        parse_mode="HTML",
    )
    await _finalize_order(
        message, state, address=address, shop_id=shop_id, promo_code=code,
        pvz_code=data.get("pvz_code"), pvz_address=data.get("pvz_address"),
        delivery_cost=data.get("delivery_cost", 0), lang=lang,
    )


@router.message(CheckoutState.waiting_promo)
async def checkout_promo_non_text(message: Message, state: FSMContext, lang: str = "ru"):
    fsm_data = await state.get_data()
    lang = fsm_data.get("lang", lang)
    await message.answer(
        t("checkout.promo_non_text", lang),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t("btn.skip", lang), callback_data="checkout_skip_promo")]
        ])
    )


@router.message(CheckoutState.waiting_comment)
async def checkout_comment_non_text(message: Message, state: FSMContext, lang: str = "ru"):
    fsm_data = await state.get_data()
    lang = fsm_data.get("lang", lang)
    await message.answer(
        t("checkout.comment_non_text", lang),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t("btn.skip", lang), callback_data="checkout_skip_comment")]
        ])
    )


@router.message(CheckoutState.waiting_address)
async def checkout_address_non_text(message: Message, state: FSMContext, lang: str = "ru"):
    fsm_data = await state.get_data()
    lang = fsm_data.get("lang", lang)
    await message.answer(
        t("checkout.address_non_text", lang),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t("checkout.btn_skip_address", lang), callback_data="checkout_skip_address")]
        ])
    )


async def _finalize_order(
    message: Message,
    state: FSMContext,
    address: str,
    shop_id: int = 1,
    promo_code: str | None = None,
    pvz_code: str | None = None,
    pvz_address: str | None = None,
    delivery_cost: int = 0,
    lang: str = "ru",
):
    data = await state.get_data()
    comment = data.get("comment", "")
    lang = data.get("lang", lang)
    user_id = message.chat.id
    await state.clear()

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            cart_resp = await client.get(
                f"{API_URL}/cart/{user_id}",
                headers=bot_headers(user_id, shop_id),
            )
        cart_data = cart_resp.json()
        total = cart_data.get("total", 0)
    except Exception:
        total = 0

    order_payload: dict = {
        "user_id": user_id,
        "comment": comment,
        "delivery_address": pvz_address or address or "",
        "user_first_name": message.chat.first_name or "",
        "user_last_name": message.chat.last_name or "",
        "user_username": message.chat.username or "",
    }
    if promo_code:
        order_payload["promo_code"] = promo_code
    if pvz_code:
        order_payload["pvz_code"] = pvz_code
        order_payload["pvz_address"] = pvz_address or ""
    if delivery_cost:
        order_payload["delivery_cost"] = delivery_cost

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{API_URL}/orders/",
                json=order_payload,
                headers=bot_headers(user_id, shop_id),
            )
    except Exception:
        await message.answer(t("error.connection", lang), reply_markup=main_menu(lang=lang))
        return

    if response.status_code != 200:
        await message.answer(t("error.order_failed", lang), reply_markup=main_menu(lang=lang))
        return

    order = response.json()
    actual_total = order.get("total", total)
    discount = order.get("discount", 0)

    caption = t("checkout.order_created", lang, id=order["id"]) + "\n\n"
    caption += t("checkout.order_sum", lang, total=_fmt_price(actual_total)) + "\n"
    if discount:
        caption += t("checkout.order_discount", lang, discount=_fmt_price(discount)) + "\n"
    if promo_code:
        caption += t("checkout.order_promo", lang, code=promo_code) + "\n"
    caption += t("checkout.order_status_new", lang) + "\n"
    if pvz_address:
        caption += t("checkout.order_pvz", lang, pvz=pvz_address) + "\n"
        if delivery_cost:
            caption += t("checkout.order_delivery_cost", lang, cost=delivery_cost) + "\n"
    elif address:
        caption += t("checkout.order_address", lang, address=address) + "\n"
    if comment:
        caption += t("checkout.order_comment", lang, comment=comment) + "\n"

    cfg = await _get_public_settings(shop_id)
    qr_url = cfg.get("payment_qr_url")
    qr_comment = cfg.get("payment_qr_comment", "").strip()
    yookassa_enabled = cfg.get("yookassa_enabled", False)

    # ── Попытка создать платёж ЮКасса ────────────────────────────────────────
    payment_url: str | None = None
    order_id_val: int | None = order.get("id")

    if yookassa_enabled and order_id_val:
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                pay_resp = await client.post(
                    f"{API_URL}/yookassa/bot/payments/{order_id_val}",
                    headers=bot_headers(user_id, shop_id),
                )
                if pay_resp.status_code in (200, 201):
                    payment_url = pay_resp.json().get("confirmation_url")
        except Exception:
            pass

    # ── Клавиатура ─────────────────────────────────────────────────────────────
    kb_rows = []
    if payment_url:
        kb_rows.append([InlineKeyboardButton(text=t("checkout.btn_pay", lang), url=payment_url)])
        kb_rows.append([InlineKeyboardButton(
            text=t("checkout.btn_check_pay", lang),
            callback_data=f"check_payment_{order_id_val}",
        )])
    kb_rows.append([InlineKeyboardButton(text=t("checkout.btn_contact_seller", lang), callback_data="menu_question")])
    kb_rows.append([InlineKeyboardButton(text=t("btn.back_menu", lang), callback_data="menu_back")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)

    if payment_url:
        caption += t("checkout.order_pay_online", lang)
        await message.answer(caption, reply_markup=kb, parse_mode="HTML")
        return

    if qr_url:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                img_resp = await client.get(f"{APP_URL}{qr_url}")
                if img_resp.status_code == 200 and len(img_resp.content) > 100:
                    caption_qr = caption + f"\n📱 <b>{_fmt_price(total)}</b> QR"
                    if qr_comment:
                        caption_qr += f"\n{qr_comment}"
                    qr_photo = BufferedInputFile(img_resp.content, filename="qr.png")
                    await message.answer_photo(
                        photo=qr_photo, caption=caption_qr,
                        reply_markup=kb, parse_mode="HTML",
                    )
                    return
        except Exception:
            pass

    caption += t("checkout.order_contact_seller", lang)
    await message.answer(caption, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("check_payment_"))
async def check_payment(callback: CallbackQuery, shop_id: int = 1, lang: str = "ru"):
    """Проверяет статус оплаты заказа в ЮКасса."""
    order_id_val = callback.data.split("check_payment_")[-1]
    user_id = callback.from_user.id

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(
                f"{API_URL}/yookassa/bot/payments/{order_id_val}",
                headers=bot_headers(user_id, shop_id),
            )
            data = r.json() if r.status_code == 200 else {}
    except Exception:
        await callback.answer(t("error.connection", lang), show_alert=True)
        return

    status = data.get("payment_status", "")
    paid = data.get("paid", False)

    label = t(f"payment.status.{status}", lang) if status else status or "?"

    if paid or status == "succeeded":
        await callback.answer(t("payment.check.paid", lang), show_alert=True)
    else:
        await callback.answer(t("payment.check.status", lang, label=label), show_alert=True)


@router.callback_query(F.data == "menu_refresh")
async def menu_refresh(callback: CallbackQuery, state: FSMContext, shop_id: int = 1, lang: str = "ru"):
    navigation.reset(callback.from_user.id)
    await state.clear()
    cfg = await _get_public_settings(shop_id)
    welcome_text = cfg.get("welcome_message") or t("welcome.default", lang)
    miniapp_url = cfg.get("miniapp_url") or None
    await clear_and_reset(callback.from_user.id, callback.bot)
    sent = await callback.bot.send_message(
        callback.from_user.id, welcome_text, reply_markup=main_menu(miniapp_url, lang),
    )
    track(callback.from_user.id, sent.message_id)
    await callback.answer()


@router.callback_query(F.data.startswith("noop_"))
async def noop(callback: CallbackQuery):
    await callback.answer()


@router.message(StateFilter(None), F.text)
async def unexpected_message(message: Message, lang: str = "ru"):
    if message.text and message.text.startswith('/'):
        return
    await message.answer(
        t("error.unexpected", lang),
        reply_markup=main_menu(lang=lang),
    )
