from typing import Optional
from pydantic import BaseModel, Field


class SettingsResponse(BaseModel):
    shop_name: str
    logo_filename: Optional[str]
    logo_url: Optional[str]
    reviews_enabled: bool
    welcome_message: Optional[str]
    seller_contact: Optional[str]
    admin_contact: Optional[str]
    hide_out_of_stock: bool
    stamp_filename: Optional[str]
    stamp_url: Optional[str]
    payment_qr_filename: Optional[str]
    payment_qr_url: Optional[str]
    payment_qr_comment: Optional[str]
    legal_name: Optional[str]


class SettingsUpdate(BaseModel):
    shop_name: Optional[str] = Field(default=None, max_length=128)
    reviews_enabled: Optional[bool] = None
    welcome_message: Optional[str] = Field(default=None, max_length=2000)
    seller_contact: Optional[str] = Field(default=None, max_length=256)
    admin_contact: Optional[str] = Field(default=None, max_length=256)
    hide_out_of_stock: Optional[bool] = None
    payment_qr_comment: Optional[str] = Field(default=None, max_length=512)
    legal_name: Optional[str] = Field(default=None, max_length=256)


class FaqItemResponse(BaseModel):
    id: int
    question: str
    answer: str
    sort_order: int
    is_active: bool


class FaqCreate(BaseModel):
    question: str = Field(min_length=1, max_length=512)
    answer: str = Field(min_length=1)
    sort_order: int = 0
    is_active: bool = True


class FaqUpdate(BaseModel):
    question: Optional[str] = Field(default=None, min_length=1, max_length=512)
    answer: Optional[str] = Field(default=None, min_length=1)
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None
