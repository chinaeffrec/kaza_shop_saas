"""
CDEK API v2 HTTP-клиент.

Документация: https://api-docs.cdek.ru/

Особенности реализации:
  - OAuth2 client_credentials; токен кэшируется в Redis (ключ cdek_token:{shop_id}).
    Без Redis кэш in-process (dict), что подходит для single-process запуска.
  - Работает как в тестовом режиме (api.edu.cdek.ru), так и в боевом (api.cdek.ru).
  - Все методы бросают CdekError при ошибке API.

Тестовые учётные данные (CDEK):
  client_id     = EMscd6r9JnFiQ3bLoyjJY6eM
  client_secret = PjLZkKBHEiLK3YsjtNrt3TGNG0ahs3kG
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

import httpx

from app.core.circuit_breaker import cdek_cb, CircuitOpenError
from app.core.redis_client import redis_get, redis_set

logger = logging.getLogger(__name__)

_PROD_BASE = "https://api.cdek.ru/v2"
_TEST_BASE = "https://api.edu.cdek.ru/v2"

# Explicit per-phase timeouts: fail fast on unreachable host (connect=5s),
# allow more time for delivery calculation responses (read=30s).
_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)

# In-process fallback cache: {shop_id: (token, expires_at)}
_token_cache: dict[int, tuple[str, float]] = {}


class CdekError(Exception):
    pass


def _base(test: bool) -> str:
    return _TEST_BASE if test else _PROD_BASE


# ── Token management ──────────────────────────────────────────────────────────

async def get_token(
    client_id: str,
    client_secret: str,
    shop_id: int,
    test: bool = False,
) -> str:
    """Возвращает валидный access-token, используя Redis или in-process кэш."""
    redis_key = f"cdek_token:{shop_id}"

    # Try Redis first
    cached = await redis_get(redis_key)
    if cached:
        return cached

    # Try in-process cache
    mem = _token_cache.get(shop_id)
    if mem and mem[1] > time.time() + 30:
        return mem[0]

    # Fetch new token
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.post(
                f"{_base(test)}/oauth/token",
                params={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
    except httpx.RequestError as exc:
        raise CdekError(f"CDEK token request failed: {exc}") from exc

    if not r.is_success:
        raise CdekError(f"CDEK auth error {r.status_code}: {r.text[:200]}")

    data = r.json()
    token = data.get("access_token")
    if not token:
        raise CdekError("CDEK: no access_token in response")

    expires_in = int(data.get("expires_in", 3600))
    ttl = max(expires_in - 60, 60)

    await redis_set(redis_key, token, ex=ttl)
    _token_cache[shop_id] = (token, time.time() + ttl)

    logger.info("CDEK: obtained new token for shop_id=%s (ttl=%ds)", shop_id, ttl)
    return token


# ── Low-level helpers ─────────────────────────────────────────────────────────

async def _get(token: str, url: str, params: dict | None = None) -> Any:
    async def _do():
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.get(
                url,
                params=params or {},
                headers={"Authorization": f"Bearer {token}"},
            )
        if not r.is_success:
            raise CdekError(f"CDEK GET {url} → {r.status_code}: {r.text[:300]}")
        return r.json()
    try:
        return await cdek_cb.call(_do)
    except CircuitOpenError as exc:
        raise CdekError(str(exc)) from exc


async def _post(token: str, url: str, body: dict) -> Any:
    async def _do():
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.post(
                url,
                json=body,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
        if not r.is_success:
            raise CdekError(f"CDEK POST {url} → {r.status_code}: {r.text[:300]}")
        return r.json()
    try:
        return await cdek_cb.call(_do)
    except CircuitOpenError as exc:
        raise CdekError(str(exc)) from exc


# ── Public API methods ────────────────────────────────────────────────────────

async def search_cities(
    token: str,
    city_name: str,
    test: bool = False,
    limit: int = 10,
) -> list[dict]:
    """Поиск городов СДЭК по названию. Возвращает список {code, city, region, country_code}."""
    data = await _get(
        token,
        f"{_base(test)}/location/cities",
        params={"city": city_name, "size": limit, "page": 0},
    )
    return data if isinstance(data, list) else []


async def get_pvz_list(
    token: str,
    city_code: int,
    test: bool = False,
    pvz_type: str = "PVZ",   # PVZ | POSTAMAT | ALL
) -> list[dict]:
    """
    Список пунктов выдачи заказов (ПВЗ) в городе.
    Возвращает список {code, name, address, work_time, phones, type}.
    """
    data = await _get(
        token,
        f"{_base(test)}/deliverypoints",
        params={
            "city_code": city_code,
            "type": pvz_type,
            "is_handout": True,
            "is_reception": False,
            "size": 200,
            "page": 0,
        },
    )
    if not isinstance(data, list):
        return []

    result = []
    for p in data:
        location = p.get("location", {})
        phones = p.get("phones", [])
        result.append({
            "code": p.get("code", ""),
            "name": p.get("name", ""),
            "address": location.get("address", ""),
            "city": location.get("city", ""),
            "work_time": p.get("work_time", ""),
            "phone": phones[0].get("number", "") if phones else "",
            "type": p.get("type", "PVZ"),
            "note": p.get("note", ""),
        })
    return result


async def calculate_tariff(
    token: str,
    from_city_code: int,
    to_city_code: int,
    weight_grams: int = 500,
    test: bool = False,
    tariff_code: int = 233,  # Эконом: дверь → склад СДЭК
) -> dict:
    """
    Расчёт стоимости доставки.
    Возвращает {total_sum, period_min, period_max, currency}.
    tariff_code=233 — Эконом (дверь→ПВЗ).
    """
    body = {
        "tariff_code": tariff_code,
        "from_location": {"code": from_city_code},
        "to_location": {"code": to_city_code},
        "packages": [{
            "weight": max(weight_grams, 50),
            "length": 20, "width": 15, "height": 10,
        }],
    }
    data = await _post(token, f"{_base(test)}/calculator/tariff", body)

    errors = data.get("errors", [])
    if errors:
        msg = "; ".join(e.get("message", str(e)) for e in errors)
        raise CdekError(f"CDEK tariff error: {msg}")

    return {
        "total_sum": int(data.get("total_sum", 0)),
        "period_min": data.get("period_min", 0),
        "period_max": data.get("period_max", 0),
        "currency": data.get("currency", "RUB"),
    }


async def create_order(
    token: str,
    order_data: dict,
    test: bool = False,
) -> dict:
    """
    Создаёт заявку в СДЭК.
    order_data — полный payload согласно API СДЭК /orders.
    Возвращает {uuid, cdek_number} или бросает CdekError.
    """
    data = await _post(token, f"{_base(test)}/orders", order_data)

    requests = data.get("requests", [])
    if requests and requests[0].get("state") == "INVALID":
        errors = requests[0].get("errors", [])
        msg = "; ".join(e.get("message", str(e)) for e in errors)
        raise CdekError(f"CDEK order create error: {msg}")

    entity = data.get("entity", {})
    uuid = entity.get("uuid", "")
    if not uuid:
        raise CdekError("CDEK: no entity.uuid in create_order response")

    return {"uuid": uuid}


async def get_order_info(
    token: str,
    uuid: str,
    test: bool = False,
) -> dict:
    """
    Получает текущий статус заявки СДЭК.
    Возвращает {uuid, cdek_number, status_code, status_name, track_url}.
    """
    data = await _get(token, f"{_base(test)}/orders/{uuid}")

    entity = data.get("entity", {})
    statuses = entity.get("statuses", [])
    current = statuses[0] if statuses else {}

    cdek_number = entity.get("cdek_number", "")
    track_url = f"https://www.cdek.ru/ru/tracking?order_id={cdek_number}" if cdek_number else ""

    return {
        "uuid": uuid,
        "cdek_number": cdek_number,
        "status_code": current.get("code", ""),
        "status_name": current.get("name", ""),
        "track_url": track_url,
        "entity": entity,
    }
