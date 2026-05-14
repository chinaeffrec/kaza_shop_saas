"""
Обработчик команды /language и inline-кнопок выбора языка.

/language → inline-клавиатура с флагами
Нажатие на язык → сохраняет в БД/Redis → подтверждение
"""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.bot.i18n import SUPPORTED_LANGUAGES, t
from app.bot.middlewares.i18n_middleware import set_user_lang

router = Router()

_LANG_FLAG = {"ru": "🇷🇺", "en": "🇬🇧", "kk": "🇰🇿"}


def _lang_keyboard(current_lang: str) -> InlineKeyboardMarkup:
    rows = []
    for code, name in SUPPORTED_LANGUAGES.items():
        check = "✓ " if code == current_lang else ""
        rows.append([InlineKeyboardButton(
            text=f"{check}{name}",
            callback_data=f"set_lang_{code}",
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Command("language"))
async def cmd_language(message: Message, lang: str = "ru"):
    await message.answer(
        t("lang.title", lang),
        reply_markup=_lang_keyboard(lang),
    )


@router.callback_query(F.data.startswith("set_lang_"))
async def set_language(
    callback: CallbackQuery,
    shop_id: int = 1,
    lang: str = "ru",
):
    new_lang = callback.data.split("set_lang_")[-1]
    if new_lang not in SUPPORTED_LANGUAGES:
        await callback.answer("Unknown language", show_alert=True)
        return

    user_id = callback.from_user.id
    await set_user_lang(user_id, shop_id, new_lang, redis=None)

    confirm_text = t("lang.changed", new_lang)
    await callback.message.edit_text(
        confirm_text,
        reply_markup=_lang_keyboard(new_lang),
    )
    await callback.answer(confirm_text[:60])
