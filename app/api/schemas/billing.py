"""Pydantic-схемы биллинга."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PlanResponse(BaseModel):
    id: int
    slug: str
    display_name: str
    price_monthly: int          # копейки
    max_products: int           # -1 = без лимита
    max_orders_monthly: int     # -1 = без лимита
    features: dict
    sort_order: int

    model_config = {"from_attributes": True}


class SubscriptionResponse(BaseModel):
    shop_id: int
    plan: PlanResponse
    status: str
    started_at: datetime
    expires_at: Optional[datetime] = None
    trial_ends_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UsageResponse(BaseModel):
    products_count: int
    products_limit: int             # -1 = без лимита
    products_pct: float             # 0–100, -1 если безлимит
    orders_this_month: int
    orders_limit: int               # -1 = без лимита
    orders_pct: float               # 0–100, -1 если безлимит
    plan_slug: str
    plan_display_name: str


class AssignPlanRequest(BaseModel):
    shop_id: int
    plan_slug: str
    expires_at: Optional[datetime] = None


class LimitExceededError(BaseModel):
    detail: str
    limit_type: str    # "products" | "orders"
    current: int
    limit: int
    plan_slug: str
    upgrade_required: bool = True
