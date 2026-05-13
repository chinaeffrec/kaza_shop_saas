from typing import Optional

from app.core.config import get_settings

_cfg = get_settings()


def bot_headers(user_id: Optional[int] = None, shop_id: Optional[int] = None) -> dict[str, str]:
    headers: dict[str, str] = {}
    if _cfg.bot_api_token:
        headers["X-Bot-Token"] = _cfg.bot_api_token
    if user_id is not None:
        headers["X-Bot-User-Id"] = str(user_id)
    if shop_id is not None:
        headers["X-Bot-Shop-Id"] = str(shop_id)
    return headers
