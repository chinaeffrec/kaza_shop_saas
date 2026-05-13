from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class OrderItemResponse(BaseModel):
    product_id: Optional[int]
    name: str
    price: int
    quantity: int
    sum: int
    image_file_id: Optional[str] = None
    image_url: Optional[str] = None


class OrderResponse(BaseModel):
    id: int
    user_id: int
    total: int
    status: str
    status_label: str
    comment: Optional[str]
    delivery_address: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    user_name: Optional[str] = None
    user_contact: Optional[str] = None
    items: Optional[List[OrderItemResponse]] = None


class OrderListResponse(BaseModel):
    items: List[OrderResponse]
    total: int
    page: int
    per_page: int
    pages: int


class OrderStatusUpdate(BaseModel):
    status: str
    comment: Optional[str] = None


class OrderCreateRequest(BaseModel):
    user_id: int = Field(gt=0)
    comment: Optional[str] = Field(default=None, max_length=2000)
    delivery_address: Optional[str] = Field(default=None, max_length=1000)
    user_username: Optional[str] = Field(default=None, max_length=64)
    user_first_name: Optional[str] = Field(default=None, max_length=64)
    user_last_name: Optional[str] = Field(default=None, max_length=64)


class StatusItem(BaseModel):
    value: str
    label: str
