"""
Аутентификация Telegram Mini App.

Telegram передаёт initData — строку query-параметров с HMAC-SHA256 подписью.
Алгоритм проверки (официальная документация Telegram):
  1. Разобрать параметры, вынуть hash
  2. Отсортировать оставшиеся пары ключ=значение по ключу, собрать через \n
  3. secret = HMAC-SHA256("WebAppData", bot_token)
  4. computed = HMAC-SHA256(secret, data_check_string)
  5. computed == hash → данные подлинны

После валидации создаётся short-lived JWT с role="miniapp".
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

import jwt

from app.core.config import get_settings

_INIT_DATA_MAX_AGE = 86400  # 24 часа


def validate_init_data(init_data: str, bot_token: str) -> dict:
    """
    Проверяет подпись Telegram initData.
    Возвращает словарь user (id, first_name, …) или бросает ValueError.
    """
    params = dict(parse_qsl(init_data, strict_parsing=True))
    received_hash = params.pop("hash", "")
    if not received_hash:
        raise ValueError("Missing hash in initData")

    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(params.items())
    )

    # secret key = HMAC-SHA256("WebAppData", bot_token)
    secret_key = hmac.new(
        b"WebAppData", bot_token.encode(), hashlib.sha256
    ).digest()
    computed = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed, received_hash):
        raise ValueError("Invalid initData signature")

    # Проверяем свежесть данных
    try:
        auth_date = int(params.get("auth_date", 0))
    except ValueError:
        auth_date = 0
    if time.time() - auth_date > _INIT_DATA_MAX_AGE:
        raise ValueError("initData expired (older than 24 h)")

    user_raw = params.get("user", "{}")
    try:
        user = json.loads(user_raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Cannot parse user from initData") from exc

    if not isinstance(user.get("id"), int):
        raise ValueError("Missing user.id in initData")

    return user


def create_miniapp_token(user_id: int, shop_id: int) -> str:
    """Создаёт JWT для Mini App (TTL 24 ч)."""
    cfg = get_settings()
    secret = cfg.platform_jwt_secret or cfg.secret_key
    payload = {
        "sub": str(user_id),
        "shop_id": shop_id,
        "role": "miniapp",
        "iat": int(time.time()),
        "exp": int(time.time()) + 86400,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_miniapp_token(token: str) -> dict | None:
    """Декодирует токен Mini App. Возвращает payload или None."""
    cfg = get_settings()
    secret = cfg.platform_jwt_secret or cfg.secret_key
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        if payload.get("role") != "miniapp":
            return None
        return payload
    except Exception:
        return None
