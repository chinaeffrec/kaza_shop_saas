from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def categories_kb(categories):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=c.name,
                callback_data=f"open_category_{c.id}"
            )
        ]
        for c in categories
    ] + [
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu_back")]
    ])


def subcategories_kb(subs):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=s.name, callback_data=f"open_sub_{s.id}")]
        for s in subs
    ] + [
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back"),
            InlineKeyboardButton(text="🏠 Меню", callback_data="menu_back"),
        ]
    ])


def products_kb(products):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=p.name, callback_data=f"open_product_{p.id}")]
        for p in products
    ] + [
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back"),
            InlineKeyboardButton(text="🏠 Меню", callback_data="menu_back"),
        ]
    ])

