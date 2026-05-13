from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ── Requests ──────────────────────────────────────────────────────────────────

class ShopCreate(BaseModel):
    owner_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=128)
    bot_token: Optional[str] = Field(default=None, min_length=10, max_length=256)
    plan: Literal["trial", "basic", "pro"] = "trial"


class ShopUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)


class ShopStatusUpdate(BaseModel):
    status: Literal["trial", "active", "suspended"]


class ShopPlanUpdate(BaseModel):
    plan: Literal["trial", "basic", "pro"]
    plan_expires_at: Optional[datetime] = None


class BotTokenUpdate(BaseModel):
    bot_token: str = Field(min_length=10, max_length=256)


class ShopAssignRequest(BaseModel):
    owner_id: int = Field(gt=0)


# ── Responses ─────────────────────────────────────────────────────────────────

class ShopResponse(BaseModel):
    id: int
    owner_id: int
    owner_email: Optional[str] = None
    name: str
    status: str
    plan: str
    plan_expires_at: Optional[datetime] = None
    max_products: int
    has_bot_token: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ShopListResponse(BaseModel):
    items: list[ShopResponse]
    total: int
    page: int
    per_page: int
    pages: int


class ShopStatsResponse(BaseModel):
    shop_id: int
    total_orders: int
    total_products: int
    total_users: int
    total_revenue: float
    active_orders: int
