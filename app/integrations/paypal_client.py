"""
PayPal payment provider — стаб для международных платежей.

Документация PayPal REST API: https://developer.paypal.com/docs/api/overview/
Python SDK: pip install paypalrestsdk>=1.13  (или paypal-checkout-serversdk)

Для активации:
  1. Добавить в requirements.txt: paypalrestsdk>=1.13,<2.0
  2. Заполнить TODO-блоки ниже
  3. В ShopSettings: payment_provider="paypal"
  4. Добавить paypal_client_id и paypal_client_secret в настройки магазина

Поддерживаемые страны/валюты: https://developer.paypal.com/docs/reports/reference/
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import HTTPException

from app.integrations.payment_provider import (
    PaymentProviderCode, PaymentResult, PaymentStatus, WebhookEvent,
)

logger = logging.getLogger(__name__)


class PayPalProvider:
    """
    Реализация PaymentProvider для PayPal Orders API v2.
    Документация: https://developer.paypal.com/docs/api/orders/v2/
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,      # PayPal Client ID
        secret_key: Optional[str] = None,   # PayPal Client Secret
        sandbox: bool = False,
        **_,
    ):
        if not api_key or not secret_key:
            raise ValueError("PayPal: client_id и client_secret не заданы")
        self._client_id = api_key
        self._client_secret = secret_key
        self._base_url = (
            "https://api-m.sandbox.paypal.com" if sandbox
            else "https://api-m.paypal.com"
        )

    async def create_payment(
        self,
        *,
        amount: float,
        currency: str = "USD",
        description: str,
        return_url: str,
        order_id: str,
        **_,
    ) -> PaymentResult:
        """
        TODO: PayPal Orders API v2 — создание заказа (CAPTURE intent):

        import httpx, base64
        auth = base64.b64encode(f"{self._client_id}:{self._client_secret}".encode()).decode()
        headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}

        # Получаем access_token
        async with httpx.AsyncClient() as client:
            token_resp = await client.post(
                f"{self._base_url}/v1/oauth2/token",
                data={"grant_type": "client_credentials"},
                headers=headers,
            )
            access_token = token_resp.json()["access_token"]

            # Создаём заказ
            order_resp = await client.post(
                f"{self._base_url}/v2/checkout/orders",
                json={
                    "intent": "CAPTURE",
                    "purchase_units": [{
                        "reference_id": order_id,
                        "amount": {"currency_code": currency.upper(), "value": f"{amount:.2f}"},
                        "description": description,
                    }],
                    "application_context": {
                        "return_url": return_url,
                        "cancel_url": return_url,
                    },
                },
                headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            )
            data = order_resp.json()

        approve_url = next(
            (l["href"] for l in data.get("links", []) if l["rel"] == "approve"), ""
        )
        return PaymentResult(
            payment_id=data["id"],
            status=PaymentStatus.PENDING,
            confirmation_url=approve_url,
            provider=PaymentProviderCode.PAYPAL,
            raw=data,
        )
        """
        raise NotImplementedError("PayPalProvider.create_payment не реализован")

    async def get_payment(self, payment_id: str) -> PaymentResult:
        """
        TODO: GET /v2/checkout/orders/{payment_id}
        Маппинг статусов:
          "COMPLETED"  → SUCCEEDED
          "VOIDED"     → CANCELED
          "CREATED"    → PENDING
        """
        raise NotImplementedError("PayPalProvider.get_payment не реализован")

    async def parse_webhook(self, body: bytes, headers: dict) -> WebhookEvent:
        """
        TODO: верификация подписи PayPal вебхука через
        POST /v1/notifications/verify-webhook-signature
        """
        raise NotImplementedError("PayPalProvider.parse_webhook не реализован")
