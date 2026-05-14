"""
DHL Express delivery provider — стаб для международной доставки.

DHL Express API: https://developer.dhl.com/api-reference/dhl-express
Покрытие: 220+ стран, экспресс-доставка, таможенное оформление

Для активации:
  1. Получить API-ключ: https://developer.dhl.com/
  2. Добавить в requirements.txt: httpx>=0.27  (уже есть)
  3. Заполнить TODO-блоки
  4. ShopSettings.delivery_provider = "dhl"
  5. Добавить dhl_api_key, dhl_account_number в ShopSettings

Особенности DHL Express API:
  - Базовый URL: https://express.api.dhl.com/mydhlapi
  - Аутентификация: Basic Auth (username = API key, password = пароль)
  - Запрос тарифа: POST /rates
  - Создание отправления: POST /shipments
  - Трекинг: GET /shipments/{shipmentTrackingNumber}/tracking
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import HTTPException

from app.integrations.delivery_provider import (
    Address, DeliveryProviderCode, DeliveryRate, Package, Shipment, TrackingInfo,
)

logger = logging.getLogger(__name__)

_BASE_URL = "https://express.api.dhl.com/mydhlapi"


class DhlProvider:
    """
    Реализация DeliveryProvider для DHL Express API.
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,         # DHL API Key (username)
        api_password: Optional[str] = None,    # DHL API Password
        account_number: Optional[str] = None,  # Номер аккаунта DHL
        **_,
    ):
        if not api_key:
            raise ValueError("DHL: api_key не задан в настройках магазина")
        self._api_key = api_key
        self._api_password = api_password or ""
        self._account_number = account_number

    async def get_rates(
        self,
        from_address: Address,
        to_address: Address,
        package: Package,
    ) -> list[DeliveryRate]:
        """
        TODO: DHL Express Rates and Date-Time API
        POST /mydhlapi/rates

        Request body:
        {
            "customerDetails": {
                "shipperDetails": {
                    "postalCode": from_address.postal_code,
                    "cityName": from_address.city,
                    "countryCode": from_address.country,
                },
                "receiverDetails": {
                    "postalCode": to_address.postal_code,
                    "cityName": to_address.city,
                    "countryCode": to_address.country,
                },
            },
            "accounts": [{"number": self._account_number, "typeCode": "shipper"}],
            "packages": [{
                "weight": package.weight_kg,
                "dimensions": {
                    "length": package.length_cm,
                    "width": package.width_cm,
                    "height": package.height_cm,
                },
            }],
            "plannedShippingDateAndTime": "...",  # ISO 8601
            "unitOfMeasurement": "metric",
        }

        Response → список продуктов с totalPrice.
        Маппинг: product.productCode → service_code,
                 product.productName → service_name,
                 product.totalPrice[0].price → price

        import httpx, base64
        auth = base64.b64encode(f"{self._api_key}:{self._api_password}".encode()).decode()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{_BASE_URL}/rates",
                json=...,
                headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"},
            )
        ...
        """
        raise NotImplementedError(
            "DhlProvider.get_rates не реализован. "
            "Зарегистрируйте аккаунт на developer.dhl.com и заполните TODO."
        )

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
        TODO: DHL Express Shipment API
        POST /mydhlapi/shipments

        Создаёт отправление и возвращает AWB (трек-номер) + PDF этикетку (base64).
        """
        raise NotImplementedError("DhlProvider.create_shipment не реализован")

    async def track(self, tracking_number: str) -> TrackingInfo:
        """
        TODO: DHL Express Tracking API
        GET /mydhlapi/shipments/{trackingNumber}/tracking
        """
        raise NotImplementedError("DhlProvider.track не реализован")
