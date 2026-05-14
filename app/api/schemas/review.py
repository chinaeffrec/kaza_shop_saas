"""Pydantic-схемы отзывов."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ReviewCreate(BaseModel):
    """Создание отзыва ботом."""
    order_id: int
    product_id: int
    user_id: int
    rating: int = Field(..., ge=1, le=5)
    text: Optional[str] = Field(default=None, max_length=1000)


class ReviewResponse(BaseModel):
    id: int
    shop_id: int
    product_id: int
    user_id: int
    order_id: Optional[int]
    rating: int
    text: Optional[str]
    is_approved: bool
    created_at: datetime
    product_name: Optional[str] = None   # denormalized, заполняется сервисом

    model_config = {"from_attributes": True}


class ReviewUpdate(BaseModel):
    """Модерация: одобрить / отклонить / обновить текст."""
    is_approved: Optional[bool] = None
    text: Optional[str] = Field(default=None, max_length=1000)


class ReviewListResponse(BaseModel):
    items: list[ReviewResponse]
    total: int
    page: int
    per_page: int


class ReviewStats(BaseModel):
    """Агрегированная статистика для карточки товара."""
    product_id: int
    count: int
    average: float        # среднее 1.0–5.0
    distribution: dict    # {"1": N, "2": N, ...}
