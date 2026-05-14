"""
EasyPost delivery provider — агрегатор 100+ перевозчиков.

EasyPost — единый API для всех крупных перевозчиков:
  UPS, FedEx, USPS, DHL, Canada Post, Royal Mail, Australia Post,
  и 100+ других. Рекомендован для международного масштабирования.

Документация: https://www.easypost.com/docs/api
Python SDK: pip install easypost>=9.0

Ключевые преимущества для Kaza Shop:
  - Один API-ключ для всех перевозчиков
  - Реальные ставки в реальном времени
  - Автоматическая покупка этикеток
  - Unified tracking API

Для активации:
  1. Зарегистрироваться на easypost.com (есть бесплатный sandbox)
  2. Добавить в requirements.txt: easypost>=9.0,<10.0
  3. Заполнить TODO-блоки ниже
  4. ShopSettings.delivery_provider = "easypost"
  5. Добавить easypost_api_key в ShopSettings
"""
from __future__ import annotations

import logging
from typing import Optional

from app.integrations.delivery_provider import (
    Address, DeliveryProviderCode, DeliveryRate, Package, Shipment, TrackingInfo,
)

logger = logging.getLogger(__name__)


class EasyPostProvider:
    """
    Реализация DeliveryProvider через EasyPost API.

    EasyPost не требует отдельных аккаунтов у каждого перевозчика —
    достаточно одного EasyPost API ключа.
    """

    def __init__(self, *, api_key: Optional[str] = None, **_):
        if not api_key:
            raise ValueError("EasyPost: api_key не задан в настройках магазина")
        self._api_key = api_key

    def _client(self):
        """
        TODO: создание EasyPost клиента.

        import easypost
        return easypost.EasyPostClient(self._api_key)
        """
        raise NotImplementedError("EasyPost SDK не установлен (pip install easypost)")

    async def get_rates(
        self,
        from_address: Address,
        to_address: Address,
        package: Package,
    ) -> list[DeliveryRate]:
        """
        TODO: EasyPost Shipment API — получение тарифов.

        client = self._client()
        shipment = client.shipment.create(
            from_address={
                "name":     from_address.name,
                "street1":  from_address.street,
                "city":     from_address.city,
                "zip":      from_address.postal_code,
                "country":  from_address.country,
                "phone":    from_address.phone,
            },
            to_address={
                "name":     to_address.name,
                "street1":  to_address.street,
                "city":     to_address.city,
                "zip":      to_address.postal_code,
                "country":  to_address.country,
                "phone":    to_address.phone,
            },
            parcel={
                "weight":  package.weight_kg * 35.274,  # кг → унции для USPS
                "length":  package.length_cm / 2.54,    # см → дюймы
                "width":   package.width_cm  / 2.54,
                "height":  package.height_cm / 2.54,
            },
        )
        rates = []
        for r in shipment.rates:
            rates.append(DeliveryRate(
                provider=DeliveryProviderCode.EASYPOST,
                service_code=f"{r.carrier}_{r.service}",
                service_name=f"{r.carrier} {r.service}",
                price=float(r.rate),
                currency=r.currency.upper(),
                delivery_days_min=r.delivery_days,
                delivery_days_max=r.delivery_days,
                raw={"shipment_id": shipment.id, "rate_id": r.id},
            ))
        return sorted(rates, key=lambda x: x.price)
        """
        raise NotImplementedError(
            "EasyPostProvider.get_rates не реализован. "
            "Добавьте easypost SDK (pip install easypost) и заполните TODO."
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
        TODO: покупка этикетки по выбранному тарифу.

        client = self._client()
        shipment_id = rate.raw.get("shipment_id")
        rate_id     = rate.raw.get("rate_id")
        shipment = client.shipment.buy(shipment_id, rate={"id": rate_id})

        return Shipment(
            shipment_id=shipment.id,
            tracking_number=shipment.tracking_code,
            label_url=shipment.postage_label.label_url,
            provider=DeliveryProviderCode.EASYPOST,
            carrier=rate.service_code.split("_")[0],
            raw=shipment.to_dict(),
        )
        """
        raise NotImplementedError("EasyPostProvider.create_shipment не реализован")

    async def track(self, tracking_number: str) -> TrackingInfo:
        """
        TODO: EasyPost Tracker API.

        client = self._client()
        tracker = client.tracker.create(tracking_code=tracking_number)
        return TrackingInfo(
            tracking_number=tracker.tracking_code,
            status=tracker.status,
            location=tracker.tracking_details[-1].message if tracker.tracking_details else None,
            estimated_delivery=str(tracker.est_delivery_date),
            events=[{"message": d.message, "datetime": str(d.datetime)}
                    for d in tracker.tracking_details],
        )
        """
        raise NotImplementedError("EasyPostProvider.track не реализован")
