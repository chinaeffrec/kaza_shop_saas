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
    # CDEK
    cdek_enabled: bool = False
    cdek_test_mode: bool = True
    cdek_client_id: Optional[str] = None
    cdek_client_secret: Optional[str] = None   # возвращаем маскированным
    cdek_sender_city_code: Optional[int] = None
    cdek_sender_address: Optional[str] = None
    cdek_default_weight: int = 500
    # YooKassa
    yookassa_enabled: bool = False
    yookassa_shop_id: Optional[str] = None
    yookassa_secret_key: Optional[str] = None  # возвращаем маскированным
    yookassa_return_url: Optional[str] = None
    # Mini App
    miniapp_url: Optional[str] = None
    # i18n
    default_language: str = "ru"
    shop_languages: str = "ru"


class SettingsUpdate(BaseModel):
    shop_name: Optional[str] = Field(default=None, max_length=128)
    reviews_enabled: Optional[bool] = None
    welcome_message: Optional[str] = Field(default=None, max_length=2000)
    seller_contact: Optional[str] = Field(default=None, max_length=256)
    admin_contact: Optional[str] = Field(default=None, max_length=256)
    hide_out_of_stock: Optional[bool] = None
    payment_qr_comment: Optional[str] = Field(default=None, max_length=512)
    legal_name: Optional[str] = Field(default=None, max_length=256)
    # CDEK
    cdek_enabled: Optional[bool] = None
    cdek_test_mode: Optional[bool] = None
    cdek_client_id: Optional[str] = Field(default=None, max_length=128)
    cdek_client_secret: Optional[str] = Field(default=None, max_length=256)
    cdek_sender_city_code: Optional[int] = None
    cdek_sender_address: Optional[str] = Field(default=None, max_length=512)
    cdek_default_weight: Optional[int] = Field(default=None, ge=50, le=31000)
    # YooKassa
    yookassa_enabled: Optional[bool] = None
    yookassa_shop_id: Optional[str] = Field(default=None, max_length=64)
    yookassa_secret_key: Optional[str] = Field(default=None, max_length=256)
    yookassa_return_url: Optional[str] = Field(default=None, max_length=512)
    # Mini App
    miniapp_url: Optional[str] = Field(default=None, max_length=512)
    # i18n
    default_language: Optional[str] = Field(default=None, max_length=8)
    shop_languages: Optional[str] = Field(default=None, max_length=64)


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
