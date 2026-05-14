"""
Абстракция платёжного провайдера.

Позволяет подключить любой платёжный шлюз без изменения бизнес-логики:
  - YooKassa (Россия/СНГ)         — реализован, app/integrations/yookassa_client.py
  - Stripe (международный)         — стаб, app/integrations/stripe_client.py
  - PayPal (международный)         — стаб, app/integrations/paypal_client.py
  - Checkout.com (международный)   — стаб, app/integrations/checkout_client.py

Выбор провайдера задаётся в ShopSettings.payment_provider.
Фабрика get_payment_provider() возвращает нужную реализацию.

Добавление нового провайдера:
  1. Реализуй PaymentProvider (Protocol).
  2. Зарегистрируй в _REGISTRY ниже.
  3. Добавь credentials-поля в ShopSettings + миграцию.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Protocol, runtime_checkable

from fastapi import HTTPException

logger = logging.getLogger(__name__)


# ── Значения ───────────────────────────────────────────────────────────────────

class PaymentProviderCode(str, Enum):
    YOOKASSA = "yookassa"
    STRIPE   = "stripe"
    PAYPAL   = "paypal"
    CHECKOUT = "checkout"


class PaymentStatus(str, Enum):
    PENDING   = "pending"
    WAITING   = "waiting_for_capture"
    SUCCEEDED = "succeeded"
    CANCELED  = "canceled"
    FAILED    = "failed"


# ── Dataclasses результатов ────────────────────────────────────────────────────

@dataclass
class PaymentResult:
    """Результат создания платежа."""
    payment_id: str
    status: PaymentStatus
    confirmation_url: str        # URL для редиректа покупателя
    provider: PaymentProviderCode
    raw: dict = field(default_factory=dict)  # оригинальный ответ провайдера


@dataclass
class WebhookEvent:
    """Нормализованное событие из вебхука провайдера."""
    payment_id: str
    status: PaymentStatus
    amount: float
    currency: str
    order_id: Optional[str]      # shop-side order reference
    provider: PaymentProviderCode
    raw: dict = field(default_factory=dict)


# ── Протокол (интерфейс) ───────────────────────────────────────────────────────

@runtime_checkable
class PaymentProvider(Protocol):
    """
    Единый интерфейс для всех платёжных провайдеров.
    Каждый клиент должен реализовывать эти три метода.
    """

    async def create_payment(
        self,
        *,
        amount: float,
        currency: str,            # ISO 4217: "RUB", "USD", "EUR", …
        description: str,
        return_url: str,
        order_id: str,
        idempotency_key: Optional[str] = None,
        **extra,
    ) -> PaymentResult:
        """Создаёт платёж и возвращает ссылку для оплаты."""
        ...

    async def get_payment(self, payment_id: str) -> PaymentResult:
        """Запрашивает актуальный статус платежа по ID."""
        ...

    async def parse_webhook(self, body: bytes, headers: dict) -> WebhookEvent:
        """
        Верифицирует и разбирает входящий вебхук.
        Должен проверять подпись / IP-список провайдера.
        Raises HTTPException(400) при неверной подписи.
        """
        ...


# ── Фабрика ────────────────────────────────────────────────────────────────────

# Ленивый реестр: provider_code → callable, возвращающий PaymentProvider
# Используем строки модулей для отложенного импорта — не тащим все SDK при старте.
_REGISTRY: dict[PaymentProviderCode, str] = {
    PaymentProviderCode.YOOKASSA: "app.integrations.yookassa_client.YooKassaProvider",
    PaymentProviderCode.STRIPE:   "app.integrations.stripe_client.StripeProvider",
    PaymentProviderCode.PAYPAL:   "app.integrations.paypal_client.PayPalProvider",
    PaymentProviderCode.CHECKOUT: "app.integrations.checkout_client.CheckoutProvider",
}


def get_payment_provider(
    provider_code: str,
    *,
    shop_id: Optional[str] = None,
    api_key: Optional[str] = None,
    secret_key: Optional[str] = None,
    **credentials,
) -> PaymentProvider:
    """
    Возвращает реализацию PaymentProvider для указанного провайдера.

    Credentials передаются из расшифрованных полей ShopSettings.
    Пример вызова из yookassa_service:
        provider = get_payment_provider(
            settings.payment_provider,
            shop_id=settings.yookassa_shop_id,
            secret_key=fernet_decrypt(settings.yookassa_secret_key),
        )
    """
    try:
        code = PaymentProviderCode(provider_code)
    except ValueError:
        raise HTTPException(400, f"Неизвестный платёжный провайдер: {provider_code!r}")

    dotpath = _REGISTRY.get(code)
    if not dotpath:
        raise HTTPException(400, f"Провайдер {code} не зарегистрирован")

    module_path, class_name = dotpath.rsplit(".", 1)
    try:
        import importlib
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)
    except (ImportError, AttributeError) as exc:
        logger.error("Cannot load payment provider %s: %s", dotpath, exc)
        raise HTTPException(503, f"Платёжный провайдер {code} недоступен: {exc}")

    return cls(
        shop_id=shop_id,
        api_key=api_key,
        secret_key=secret_key,
        **credentials,
    )
