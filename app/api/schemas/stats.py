from typing import Dict, List, Optional
from pydantic import BaseModel


class StatusStat(BaseModel):
    count: int
    label: str


class StatusStatItem(BaseModel):
    status: str
    count: int
    label: str


class TopProduct(BaseModel):
    product_id: int
    name: str
    ordered: int
    revenue: int = 0          # выручка за период (не все время)


class RecentOrder(BaseModel):
    id: int
    user_id: int
    user_name: str
    status: str
    status_label: str
    total: int
    created_at: str


class DashboardResponse(BaseModel):
    total_revenue: int
    total_orders: int
    billable_orders: int
    average_order_value: int
    conversion_rate: float = 0.0        # billable / total * 100
    by_status: Dict[str, StatusStat]
    orders_by_status: List[StatusStatItem]
    recent_orders: List[RecentOrder]
    top_products: List[TopProduct]


# ── Analytics ─────────────────────────────────────────────────────────────────

class RevenuePoint(BaseModel):
    """Одна точка на графике выручки."""
    date: str              # "2026-05-01" (day) или "2026-W18" (week)
    revenue: int
    orders_count: int
    new_customers: int = 0  # новых покупателей в этот период


class CohortStats(BaseModel):
    """Разбивка покупателей: новые vs. повторные."""
    period_buyers: int          # уникальных покупателей в периоде
    new_buyers: int             # первый заказ в периоде
    returning_buyers: int       # уже покупали до периода
    repeat_rate: float          # returning / period_buyers * 100
    avg_orders_new: float       # среднее заказов у новых
    avg_orders_returning: float # среднее заказов у повторных


class AnalyticsResponse(BaseModel):
    revenue_chart: List[RevenuePoint]
    cohorts: CohortStats
    period: str   # "day" | "week"


# ── Product stats ─────────────────────────────────────────────────────────────

class ProductStatItem(BaseModel):
    product_id: int
    name: str
    added_to_cart: int
    ordered: int
    returned: int
    period_sold_qty: int
    period_sold_sum: int


class ProductStatsSummary(BaseModel):
    total_sold_qty: int
    total_sold_sum: int
    avg_items_per_order: float
    avg_price: int
    total_returned: int


class ProductStatsResponse(BaseModel):
    items: List[ProductStatItem]
    summary: ProductStatsSummary


# ── Import ────────────────────────────────────────────────────────────────────

class ImportResponse(BaseModel):
    status: str
    created: int
    updated: int
    errors: List[str]
