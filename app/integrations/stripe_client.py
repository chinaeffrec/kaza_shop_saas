"""
Stripe payment provider — стаб для международных платежей.

Документация Stripe API: https://stripe.com/docs/api
Python SDK: pip install stripe>=7.0

Для активации:
  1. Добавить в requirements.txt: stripe>=7.0,<9.0
  2. Заполнить TODO-блоки ниже
  3. В ShopSettings установить payment_provider="stripe"
  4. Добавить stripe_secret_key и stripe_webhook_secret в настройки магазина

Поддерживаемые валюты: https://stripe.com/docs/currencies
Поддерживаемые страны: 47+ (Европа, США, Азия, Латинская Америка, …)
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Optional

from fastapi import HTTPException

from app.core.circuit_breaker import CircuitOpenError
from app.integrations.payment_provider import (
    PaymentProviderCode, PaymentResult, PaymentStatus, WebhookEvent,
)

logger = logging.getLogger(__name__)

# Circuit breaker для Stripe (создаётся при первом обращении)
_stripe_cb = None

def _get_cb():
    global _stripe_cb
    if _stripe_cb is None:
        from app.core.circuit_breaker import CircuitBreaker
        _stripe_cb = CircuitBreaker(
            name="stripe",
            failure_threshold=5,
            recovery_timeout=60,
            half_open_max_calls=2,
        )
    return _stripe_cb


class StripeProvider:
    """
    Реализация PaymentProvider для Stripe.

    Использует Stripe Payment Intents API (рекомендован для SCA/3DS).
    Документация: https://stripe.com/docs/payments/payment-intents
    """

    def __init__(
        self,
        *,
        secret_key: Optional[str] = None,   # sk_live_… или sk_test_…
        webhook_secret: Optional[str] = None,  # whsec_…
        shop_id: Optional[str] = None,       # для multi-tenant не используется
        **_,
    ):
        if not secret_key:
            raise ValueError("Stripe: secret_key не задан в настройках магазина")
        self._secret_key = secret_key
        self._webhook_secret = webhook_secret

    async def create_payment(
        self,
        *,
        amount: float,
        currency: str = "usd",
        description: str,
        return_url: str,
        order_id: str,
        idempotency_key: Optional[str] = None,
        **extra,
    ) -> PaymentResult:
        """
        Создаёт Stripe PaymentIntent + Checkout Session.

        TODO: раскомментировать и заполнить после добавления stripe SDK:

        import stripe
        stripe.api_key = self._secret_key

        async def _do():
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": currency.lower(),
                        "product_data": {"name": description},
                        "unit_amount": int(amount * 100),  # cents
                    },
                    "quantity": 1,
                }],
                mode="payment",
                success_url=f"{return_url}?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=return_url,
                metadata={"order_id": order_id},
                idempotency_key=idempotency_key,
            )
            return PaymentResult(
                payment_id=session["payment_intent"],
                status=PaymentStatus.PENDING,
                confirmation_url=session["url"],
                provider=PaymentProviderCode.STRIPE,
                raw=session,
            )

        try:
            return await _get_cb().call(_do)
        except CircuitOpenError as exc:
            raise HTTPException(503, f"Stripe временно недоступен: {exc}") from exc
        except stripe.error.StripeError as exc:
            raise HTTPException(400, f"Stripe error: {exc.user_message}") from exc
        """
        raise NotImplementedError(
            "StripeProvider.create_payment не реализован. "
            "Добавьте stripe SDK и раскомментируйте код выше."
        )

    async def get_payment(self, payment_id: str) -> PaymentResult:
        """
        TODO: stripe.PaymentIntent.retrieve(payment_id)
        Маппинг статусов:
          "succeeded"        → PaymentStatus.SUCCEEDED
          "requires_payment" → PaymentStatus.PENDING
          "canceled"         → PaymentStatus.CANCELED
        """
        raise NotImplementedError("StripeProvider.get_payment не реализован")

    async def parse_webhook(self, body: bytes, headers: dict) -> WebhookEvent:
        """
        Верифицирует подпись Stripe-вебхука (Stripe-Signature header).

        TODO после добавления stripe SDK:

        import stripe
        sig_header = headers.get("stripe-signature", "")
        try:
            event = stripe.Webhook.construct_event(body, sig_header, self._webhook_secret)
        except stripe.error.SignatureVerificationError:
            raise HTTPException(400, "Неверная подпись Stripe-вебхука")

        intent = event["data"]["object"]
        status_map = {
            "succeeded":          PaymentStatus.SUCCEEDED,
            "payment_failed":     PaymentStatus.FAILED,
            "canceled":           PaymentStatus.CANCELED,
        }
        return WebhookEvent(
            payment_id=intent["id"],
            status=status_map.get(event["type"].split(".")[-1], PaymentStatus.PENDING),
            amount=intent["amount"] / 100,
            currency=intent["currency"].upper(),
            order_id=intent.get("metadata", {}).get("order_id"),
            provider=PaymentProviderCode.STRIPE,
            raw=event,
        )
        """
        # Minimal signature check (HMAC-SHA256) without SDK — for reference
        sig_header = headers.get("stripe-signature", "")
        if self._webhook_secret and sig_header:
            # Stripe signature format: t=timestamp,v1=hash,...
            try:
                parts = dict(p.split("=", 1) for p in sig_header.split(","))
                timestamp = parts.get("t", "")
                expected = hmac.new(
                    self._webhook_secret.encode(),
                    f"{timestamp}.".encode() + body,
                    hashlib.sha256,
                ).hexdigest()
                if not hmac.compare_digest(expected, parts.get("v1", "")):
                    raise HTTPException(400, "Неверная подпись Stripe-вебхука")
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(400, f"Ошибка верификации Stripe-вебхука: {exc}") from exc

        raise NotImplementedError("StripeProvider.parse_webhook: добавьте stripe SDK")
