from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗂  Каталог товаров  ", callback_data="menu_catalog")],
        [InlineKeyboardButton(text="🛒  Корзина          ", callback_data="menu_cart")],
        [InlineKeyboardButton(text="📦  Мои заказы       ", callback_data="menu_order")],
        [InlineKeyboardButton(text="❓  FAQ               ", callback_data="menu_faq")],
        [InlineKeyboardButton(text="💬  Написать нам     ", callback_data="menu_question")],
    ])
