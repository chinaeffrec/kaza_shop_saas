from typing import List, Optional
from pydantic import BaseModel


class CategoryResponse(BaseModel):
    id: int
    name: str


class SubCategoryResponse(BaseModel):
    id: int
    name: str
    category_id: int


class CatalogProductResponse(BaseModel):
    id: int
    name: str
    price: int
    discount_price: Optional[int]
    description: Optional[str]
    characteristics: Optional[str]
    image_file_id: Optional[str]
    image_url: Optional[str]
    image_url_2: Optional[str]
    image_url_3: Optional[str]
    stock: int
    images: List[str]


class CacheReloadResponse(BaseModel):
    status: str
    message: str
