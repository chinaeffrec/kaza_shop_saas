from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    subcategory_id: int
    name: str = Field(min_length=1, max_length=200)
    price: int = Field(gt=0)
    discount_price: Optional[int] = Field(default=None, gt=0)
    description: Optional[str] = None
    characteristics: Optional[str] = None
    stock: int = Field(default=0, ge=0)
    is_active: bool = True


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    price: Optional[int] = Field(default=None, gt=0)
    discount_price: Optional[int] = Field(default=None, gt=0)
    description: Optional[str] = None
    characteristics: Optional[str] = None
    stock: Optional[int] = Field(default=None, ge=0)
    is_active: Optional[bool] = None
    subcategory_id: Optional[int] = None


class ProductResponse(BaseModel):
    id: int
    subcategory_id: int
    name: str
    price: int
    discount_price: Optional[int]
    description: Optional[str]
    characteristics: Optional[str]
    image_file_id: Optional[str]
    image_file_id_2: Optional[str]
    image_file_id_3: Optional[str]
    image_url: Optional[str]
    image_url_2: Optional[str]
    image_url_3: Optional[str]
    images: List[str]
    has_image: bool
    stock: int
    is_active: bool
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


class ProductListResponse(BaseModel):
    items: List[ProductResponse]
    total: int
    page: int
    per_page: int
    pages: int


class ProductBulkDelete(BaseModel):
    ids: List[int] = Field(min_length=1)
