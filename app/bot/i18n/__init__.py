"""
Система интернационализации бота.

Поддерживаемые языки: ru (русский), en (English), kk (қазақ тілі).

Использование:
    from app.bot.i18n import t

    text = t("btn.cart", lang)
    text = t("checkout.promo_applied", lang, code="SALE10", discount=100, final=900)
"""
from __future__ import annotations

from app.bot.i18n.en import STRINGS as _EN
from app.bot.i18n.kk import STRINGS as _KK
from app.bot.i18n.ru import STRINGS as _RU

SUPPORTED_LANGUAGES: dict[str, str] = {
    "ru": "Русский 🇷🇺",
    "en": "English 🇬🇧",
    "kk": "Қазақша 🇰🇿",
}

DEFAULT_LANGUAGE = "ru"

_TRANSLATIONS: dict[str, dict[str, str]] = {
    "ru": _RU,
    "en": _EN,
    "kk": _KK,
}


def t(key: str, lang: str = DEFAULT_LANGUAGE, **kwargs) -> str:
    """
    Возвращает переведённую строку по ключу.
    Если ключ отсутствует в target-языке — откатывается к русскому.
    Поддерживает format-placeholders: t("checkout.promo_applied", lang, code="X").
    """
    strings = _TRANSLATIONS.get(lang, _RU)
    text = strings.get(key) or _RU.get(key) or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text


def normalize_lang(lang_code: str | None) -> str:
    """
    Нормализует код языка из Telegram (e.g. 'ru', 'en-US', 'kk') → наш код.
    Возвращает DEFAULT_LANGUAGE если не поддерживается.
    """
    if not lang_code:
        return DEFAULT_LANGUAGE
    # Берём первые 2 символа (en-US → en)
    short = lang_code[:2].lower()
    return short if short in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
