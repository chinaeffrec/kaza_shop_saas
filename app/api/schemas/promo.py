from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class PromoCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    discount_type: Literal["fixed", "percent"]
    value: int = Field(..., gt=0)
    min_order_amount: Optional[int] = Field(None, ge=0)
    max_uses: Optional[int] = Field(None, ge=1)
    expires_at: Optional[datetime] = None
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def upper_code(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("value")
    @classmethod
    def validate_percent(cls, v: int, info) -> int:
        # percent must be 1-100
        if info.data.get("discount_type") == "percent" and v > 100:
            raise ValueError("percent discount cannot exceed 100")
        return v


class PromoUpdate(BaseModel):
    discount_type: Optional[Literal["fixed", "percent"]] = None
    value: Optional[int] = Field(None, gt=0)
    min_order_amount: Optional[int] = Field(None, ge=0)
    max_uses: Optional[int] = Field(None, ge=1)
    expires_at: Optional[datetime] = None
    is_active: Optional[bool] = None


class PromoResponse(BaseModel):
    id: int
    shop_id: int
    code: str
    discount_type: str
    value: int
    min_order_amount: Optional[int]
    max_uses: Optional[int]
    used_count: int
    expires_at: Optional[datetime]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PromoListResponse(BaseModel):
    items: List[PromoResponse]
    total: int


class PromoValidateRequest(BaseModel):
    code: str
    cart_total: int  # in kopecks


class PromoValidateResponse(BaseModel):
    valid: bool
    discount: int = 0         # kopecks
    final_total: int = 0      # cart_total - discount
    message: str = ""
    promo_id: Optional[int] = None
