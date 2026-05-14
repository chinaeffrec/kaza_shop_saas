"""
Абстракция провайдера доставки.

Поддерживаемые и запланированные провайдеры:
  - CDEK (Россия/СНГ)         — реализован, app/integrations/cdek_client.py
  - DHL Express (международный) — стаб, app/integrations/dhl_client.py
  - EasyPost (агрегатор, 100+ перевозчиков) — стаб, app/integrations/easypost_client.py
  - Shippo (агрегатор, альтернатива EasyPost) — стаб, app/integrations/shippo_client.py

Выбор провайдера: ShopSettings.delivery_provider
Фабрика: get_delivery_provider()

Добавление нового провайдера:
  1. Реализуй DeliveryProvider (Protocol).
  2. Зарегистрируй в _REGISTRY.
  3. Добавь credential-поля в ShopSettings + миграцию.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Protocol, runtime_checkable

from fastapi import HTTPException

logger = logging.getLogger(__name__)


# ── Значения ───────────────────────────────────────────────────────────────────

class DeliveryProviderCode(str, Enum):
    CDEK     = "cdek"
    DHL      = "dhl"
    EASYPOST = "easypost"
    SHIPPO   = "shippo"
    FEDEX    = "fedex"


# ── Dataclasses ────────────────────────────────────────────────────────────────

@dataclass
class Address:
    country: str          # ISO 3166-1 alpha-2: "RU", "DE", "US", …
    city: str
    street: str
    postal_code: str
    state: Optional[str] = None   # для США/Канады
    name: Optional[str] = None    # имя получателя
    phone: Optional[str] = None


@dataclass
class Package:
    weight_kg: float
    length_cm: float
    width_cm: float
    height_cm: float


@dataclass
class DeliveryRate:
    """Один вариант доставки — тариф/сервис перевозчика."""
    provider: DeliveryProviderCode
    service_code: str       # например "CDEK_EXPRESS", "dhl_express", "USPS_Priority"
    service_name: str       # человекочитаемое название
    price: float
    currency: str           # ISO 4217
    delivery_days_min: Optional[int] = None
    delivery_days_max: Optional[int] = None
    raw: dict = field(default_factory=dict)


@dataclass
class Shipment:
    """Созданное отправление с трек-номером."""
    shipment_id: str
    tracking_number: str
    label_url: Optional[str]      # URL для скачивания этикетки (PDF)
    provider: DeliveryProviderCode
    carrier: Optional[str] = None  # реальный перевозчик (для агрегаторов)
    raw: dict = field(default_factory=dict)


@dataclass
class TrackingInfo:
    tracking_number: str
    status: str
    location: Optional[str]
    estimated_delivery: Optional[str]
    events: list[dict] = field(default_factory=list)


# ── Протокол (интерфейс) ───────────────────────────────────────────────────────

@runtime_checkable
class DeliveryProvider(Protocol):
    """Единый интерфейс для всех провайдеров доставки."""

    async def get_rates(
        self,
        from_address: Address,
        to_address: Address,
        package: Package,
    ) -> list[DeliveryRate]:
        """Рассчитывает доступные тарифы доставки."""
        ...

    async def create_shipment(
        self,
        from_address: Address,
        to_address: Address,
        package: Package,
        rate: DeliveryRate,
        *,
        order_id: str,
        reference: Optional[str] = None,
    ) -> Shipment:
        """
        Создаёт отправление, выкупает этикетку.
        Возвращает трек-номер и URL этикетки.
        """
        ...

    async def track(self, tracking_number: str) -> TrackingInfo:
        """Запрашивает статус отправления."""
        ...


# ── Фабрика ────────────────────────────────────────────────────────────────────

_REGISTRY: dict[DeliveryProviderCode, str] = {
    DeliveryProviderCode.CDEK:     "app.integrations.cdek_client.CdekProvider",
    DeliveryProviderCode.DHL:      "app.integrations.dhl_client.DhlProvider",
    DeliveryProviderCode.EASYPOST: "app.integrations.easypost_client.EasyPostProvider",
    DeliveryProviderCode.SHIPPO:   "app.integrations.shippo_client.ShippoProvider",
    DeliveryProviderCode.FEDEX:    "app.integrations.fedex_client.FedExProvider",
}


def get_delivery_provider(
    provider_code: str,
    *,
    api_key: Optional[str] = None,
    **credentials,
) -> DeliveryProvider:
    """
    Возвращает реализацию DeliveryProvider для указанного провайдера.

    Пример:
        provider = get_delivery_provider(
            settings.delivery_provider,
            api_key=fernet_decrypt(settings.delivery_api_key),
        )
        rates = await provider.get_rates(from_addr, to_addr, package)
    """
    try:
        code = DeliveryProviderCode(provider_code)
    except ValueError:
        raise HTTPException(400, f"Неизвестный провайдер доставки: {provider_code!r}")

    dotpath = _REGISTRY.get(code)
    if not dotpath:
        raise HTTPException(400, f"Провайдер {code} не зарегистрирован")

    module_path, class_name = dotpath.rsplit(".", 1)
    try:
        import importlib
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)
    except (ImportError, AttributeError) as exc:
        logger.error("Cannot load delivery provider %s: %s", dotpath, exc)
        raise HTTPException(503, f"Провайдер доставки {code} недоступен: {exc}")

    return cls(api_key=api_key, **credentials)
