"""Pydantic-схемы Mini App API."""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


# ── Auth ──────────────────────────────────────────────────────────────────────

class MiniAppAuthRequest(BaseModel):
    init_data: str   # raw initData string from window.Telegram.WebApp.initData
    shop_id: int


class MiniAppAuthResponse(BaseModel):
    token: str
    user_id: int
    first_name: str = ""
    username: Optional[str] = None


# ── Catalog ───────────────────────────────────────────────────────────────────

class MiniCategory(BaseModel):
    id: int
    name: str


class MiniProduct(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price: int              # в копейках
    image_url: Optional[str] = None
    in_stock: bool = True
    category_id: Optional[int] = None


# ── Cart ──────────────────────────────────────────────────────────────────────

class MiniCartItem(BaseModel):
    product_id: int
    name: str
    price: int
    quantity: int
    sum: int
    image_url: Optional[str] = None


class MiniCartResponse(BaseModel):
    items: list[MiniCartItem]
    total: int


class MiniCartAdd(BaseModel):
    product_id: int
    quantity: int = 1
    variant_id: Optional[int] = None


class MiniCartUpdate(BaseModel):
    product_id: int
    quantity: int      # 0 = удалить


# ── Orders ────────────────────────────────────────────────────────────────────

class MiniOrderCreate(BaseModel):
    comment: Optional[str] = None
    delivery_address: Optional[str] = None
    promo_code: Optional[str] = None


class MiniOrderItem(BaseModel):
    name: str
    price: int
    quantity: int
    sum: int


class MiniOrderResponse(BaseModel):
    id: int
    status: str
    status_label: str
    total: int
    discount: int = 0
    promo_code: Optional[str] = None
    delivery_address: Optional[str] = None
    payment_status: Optional[str] = None
    payment_id: Optional[str] = None
    created_at: str
    items: list[MiniOrderItem] = []
