from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class OrderItemResponse(BaseModel):
    product_id: Optional[int]
    name: str
    price: int
    quantity: int
    sum: int
    variant_id: Optional[int] = None
    variant_name: Optional[str] = None
    sku: Optional[str] = None
    image_file_id: Optional[str] = None
    image_url: Optional[str] = None


class OrderResponse(BaseModel):
    id: int
    user_id: int
    total: int
    discount: int = 0
    promo_code: Optional[str] = None
    status: str
    status_label: str
    comment: Optional[str]
    staff_notes: Optional[str] = None           # внутренние заметки (не для покупателя)
    delivery_address: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    user_name: Optional[str] = None
    user_contact: Optional[str] = None
    items: Optional[List[OrderItemResponse]] = None
    allowed_transitions: List[str] = Field(default_factory=list)
    # CDEK
    cdek_order_uuid: Optional[str] = None
    cdek_track_number: Optional[str] = None
    cdek_status: Optional[str] = None
    pvz_code: Optional[str] = None
    pvz_address: Optional[str] = None
    delivery_cost: int = 0


class OrderListResponse(BaseModel):
    items: List[OrderResponse]
    total: int
    page: int
    per_page: int
    pages: int


class OrderStatusUpdate(BaseModel):
    status: str
    comment: Optional[str] = None
    staff_notes: Optional[str] = None
    force: bool = False     # обход валидации перехода (только owner/super_admin)


class OrderCreateRequest(BaseModel):
    user_id: int = Field(gt=0)
    comment: Optional[str] = Field(default=None, max_length=2000)
    delivery_address: Optional[str] = Field(default=None, max_length=1000)
    user_username: Optional[str] = Field(default=None, max_length=64)
    user_first_name: Optional[str] = Field(default=None, max_length=64)
    user_last_name: Optional[str] = Field(default=None, max_length=64)
    promo_code: Optional[str] = Field(default=None, max_length=50)
    # CDEK
    pvz_code: Optional[str] = Field(default=None, max_length=64)
    pvz_address: Optional[str] = Field(default=None, max_length=512)
    delivery_cost: int = 0


class StatusItem(BaseModel):
    value: str
    label: str
