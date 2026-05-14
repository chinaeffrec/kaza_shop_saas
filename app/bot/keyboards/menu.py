from typing import Optional

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from app.bot.i18n import t


def main_menu(
    miniapp_url: Optional[str] = None,
    lang: str = "ru",
) -> InlineKeyboardMarkup:
    """
    Главное меню бота.
    Если передан miniapp_url — добавляет кнопку WebApp (локализованную).
    lang используется для перевода кнопок.
    """
    rows = []
    if miniapp_url:
        rows.append([InlineKeyboardButton(
            text=t("btn.open_shop", lang),
            web_app=WebAppInfo(url=miniapp_url),
        )])
    rows += [
        [InlineKeyboardButton(text=t("btn.catalog", lang), callback_data="menu_catalog")],
        [InlineKeyboardButton(text=t("btn.cart",    lang), callback_data="menu_cart")],
        [InlineKeyboardButton(text=t("btn.orders",  lang), callback_data="menu_order")],
        [InlineKeyboardButton(text=t("btn.faq",     lang), callback_data="menu_faq")],
        [InlineKeyboardButton(text=t("btn.contact", lang), callback_data="menu_question")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
