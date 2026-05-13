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
    by_status: Dict[str, StatusStat]
    orders_by_status: List[StatusStatItem]
    recent_orders: List[RecentOrder]
    top_products: List[TopProduct]


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


class ImportResponse(BaseModel):
    status: str
    created: int
    updated: int
    errors: List[str]
