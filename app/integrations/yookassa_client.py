"""
YooKassa API v3 HTTP-клиент.

Документация: https://yookassa.ru/developers/api

Аутентификация: Basic Auth — {yookassa_shop_id}:{secret_key}.
Идемпотентность: каждый POST содержит заголовок Idempotence-Key (UUID).

Тестовые данные (YooKassa):
  shop_id    = 100500   (любое в тесте)
  secret_key = test_...  (от ЛК)
  Для тестовых платежей используйте testbank.yookassa.ru

Все публичные функции бросают YooKassaError при ошибке API.
"""
from __future__ import annotations

import logging
import uuid as _uuid
from typing import Any, Optional

import httpx

from app.core.circuit_breaker import yookassa_cb, CircuitOpenError

logger = logging.getLogger(__name__)

_BASE = "https://api.yookassa.ru/v3"
# Explicit per-phase timeouts: fail fast on unreachable host (connect=5s),
# allow more time for payment processing (read=30s).
_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)


class YooKassaError(Exception):
    pass


def _auth(shop_id: str, secret_key: str) -> httpx.BasicAuth:
    return httpx.BasicAuth(username=shop_id, password=secret_key)


def _idempotency_key() -> str:
    return str(_uuid.uuid4())


async def _post(
    path: str,
    body: dict,
    shop_id: str,
    secret_key: str,
    idempotency_key: Optional[str] = None,
) -> Any:
    headers = {"Idempotence-Key": idempotency_key or _idempotency_key()}

    async def _do():
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.post(
                    f"{_BASE}{path}",
                    json=body,
                    auth=_auth(shop_id, secret_key),
                    headers=headers,
                )
        except httpx.RequestError as exc:
            raise YooKassaError(f"YooKassa request failed: {exc}") from exc

        if not r.is_success:
            try:
                err = r.json()
                msg = err.get("description") or err.get("message") or r.text[:200]
            except Exception:
                msg = r.text[:200]
            raise YooKassaError(f"YooKassa {r.status_code}: {msg}")

        return r.json()

    try:
        return await yookassa_cb.call(_do)
    except CircuitOpenError as exc:
        raise YooKassaError(str(exc)) from exc


async def _get(path: str, shop_id: str, secret_key: str) -> Any:
    async def _do():
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.get(
                    f"{_BASE}{path}",
                    auth=_auth(shop_id, secret_key),
                )
        except httpx.RequestError as exc:
            raise YooKassaError(f"YooKassa request failed: {exc}") from exc

        if not r.is_success:
            raise YooKassaError(f"YooKassa GET {path} → {r.status_code}: {r.text[:200]}")

        return r.json()

    try:
        return await yookassa_cb.call(_do)
    except CircuitOpenError as exc:
        raise YooKassaError(str(exc)) from exc


# ── Public methods ────────────────────────────────────────────────────────────

async def create_payment(
    *,
    yookassa_shop_id: str,
    secret_key: str,
    amount_rub: int,              # в рублях (целых)
    order_id: int,
    description: str,
    return_url: str,
    receipt: Optional[dict] = None,
    idempotency_key: Optional[str] = None,
) -> dict:
    """
    Создаёт платёж. Возвращает dict с полями:
      id          — payment_id для дальнейших операций
      status      — pending / waiting_for_capture / succeeded / canceled
      confirmation_url — URL для редиректа пользователя
    """
    body: dict = {
        "amount": {
            "value": f"{amount_rub}.00",
            "currency": "RUB",
        },
        "capture": True,           # auto-capture после авторизации
        "confirmation": {
            "type": "redirect",
            "return_url": return_url,
        },
        "description": description[:128],
        "metadata": {"order_id": str(order_id)},
    }
    if receipt:
        body["receipt"] = receipt

    data = await _post(
        "/payments",
        body,
        yookassa_shop_id,
        secret_key,
        idempotency_key=idempotency_key or f"order_{order_id}",
    )
    return {
        "id": data["id"],
        "status": data.get("status", "pending"),
        "confirmation_url": data.get("confirmation", {}).get("confirmation_url", ""),
        "paid": data.get("paid", False),
    }


async def get_payment(
    payment_id: str,
    yookassa_shop_id: str,
    secret_key: str,
) -> dict:
    """Возвращает текущее состояние платежа."""
    data = await _get(f"/payments/{payment_id}", yookassa_shop_id, secret_key)
    return {
        "id": data["id"],
        "status": data.get("status", ""),
        "paid": data.get("paid", False),
        "amount": data.get("amount", {}),
        "refundable": data.get("refundable", False),
        "metadata": data.get("metadata", {}),
    }


async def create_refund(
    *,
    payment_id: str,
    amount_rub: int,
    yookassa_shop_id: str,
    secret_key: str,
    description: str = "Возврат средств",
) -> dict:
    """
    Создаёт возврат по платежу.
    Возвращает dict с полями id, status.
    """
    body = {
        "payment_id": payment_id,
        "amount": {"value": f"{amount_rub}.00", "currency": "RUB"},
        "description": description[:250],
    }
    data = await _post("/refunds", body, yookassa_shop_id, secret_key)
    return {
        "id": data["id"],
        "status": data.get("status", "pending"),
    }
