"""Pydantic-схемы для YooKassa API."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class PaymentCreateResponse(BaseModel):
    payment_id: str
    confirmation_url: str
    order_id: int


class PaymentStatusResponse(BaseModel):
    order_id: int
    payment_id: str
    payment_status: str
    paid: bool
    refundable: bool


class RefundResponse(BaseModel):
    order_id: int
    refund_id: str
    status: str


# ── Webhook payload (YooKassa отправляет POST с JSON) ─────────────────────────

class _WebhookAmount(BaseModel):
    value: str
    currency: str = "RUB"


class _WebhookObject(BaseModel):
    id: str
    status: Optional[str] = None
    paid: bool = False
    refundable: bool = False
    amount: Optional[_WebhookAmount] = None


class YooWebhookPayload(BaseModel):
    event: str                 # payment.succeeded / payment.canceled / refund.succeeded
    object: _WebhookObject


# ── Bot endpoint response (ссылка для оплаты) ─────────────────────────────────

class BotPaymentResponse(BaseModel):
    payment_id: str
    confirmation_url: str
    order_id: int
    payment_status: str
