from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


# ── City search ───────────────────────────────────────────────────────────────

class CdekCity(BaseModel):
    code: int
    city: str
    region: Optional[str] = None
    country_code: Optional[str] = None


# ── PVZ ───────────────────────────────────────────────────────────────────────

class PvzPoint(BaseModel):
    code: str
    name: str
    address: str
    city: str
    work_time: str = ""
    phone: str = ""
    type: str = "PVZ"
    note: str = ""


class PvzListResponse(BaseModel):
    items: List[PvzPoint]
    total: int
    city_code: int
    city_name: str


# ── Tariff calculation ────────────────────────────────────────────────────────

class TariffRequest(BaseModel):
    to_city_code: int
    weight_grams: int = Field(default=500, ge=50)


class TariffResponse(BaseModel):
    total_sum: int      # в рублях
    period_min: int
    period_max: int
    currency: str = "RUB"


# ── Shipment creation ─────────────────────────────────────────────────────────

class ShipmentRequest(BaseModel):
    order_id: int
    pvz_code: str
    receiver_name: str
    receiver_phone: str
    weight_grams: int = 500
    comment: str = ""


class ShipmentResponse(BaseModel):
    cdek_order_uuid: str
    message: str = "Заявка создана"


# ── Status ────────────────────────────────────────────────────────────────────

class CdekStatusResponse(BaseModel):
    cdek_order_uuid: Optional[str]
    cdek_track_number: Optional[str]
    status_code: str = ""
    status_name: str = ""
    track_url: str = ""


# ── Webhook payload (CDEK → наш сервис) ──────────────────────────────────────

class CdekWebhookPayload(BaseModel):
    type: str = ""                      # ORDER_STATUS
    date_time: Optional[str] = None
    uuid: Optional[str] = None          # uuid заявки СДЭК
    attributes: dict = Field(default_factory=dict)
