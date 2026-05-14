"""Роуты товаров - только HTTP-слой, вся логика в product_service."""
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_shop_id
from app.api.schemas.product import (
    ProductBulkDelete, ProductCreate, ProductListResponse, ProductResponse, ProductUpdate,
)
from app.core.rbac import Perm
from app.db.session import get_session
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.services import product_service as svc

router = APIRouter(prefix="/products", tags=["products"])


# ── Variant schemas ───────────────────────────────────────────────────────────

class VariantCreate(BaseModel):
    name: str
    sku: Optional[str] = None
    price: Optional[int] = None   # None = цена родительского товара
    stock: int = 0
    is_active: bool = True


class VariantUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    price: Optional[int] = None
    stock: Optional[int] = None
    is_active: Optional[bool] = None


class VariantResponse(BaseModel):
    id: int
    product_id: int
    name: str
    sku: Optional[str]
    price: Optional[int]
    stock: int
    is_active: bool

    model_config = {"from_attributes": True}


class StockAdjust(BaseModel):
    stock: int   # абсолютное значение (не дельта)


@router.post("/", response_model=ProductResponse)
async def create_product(
    data: ProductCreate,
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.PRODUCTS_WRITE),
):
    # Billing: check product limit for current plan
    from app.services import billing_service as billing_svc
    allowed, current, limit = await billing_svc.check_product_limit(session, shop_id)
    if not allowed:
        raise HTTPException(
            status_code=402,
            detail={
                "detail": f"Достигнут лимит товаров тарифа ({current}/{limit}). "
                          "Обновите тариф для добавления новых товаров.",
                "limit_type": "products",
                "current": current,
                "limit": limit,
                "upgrade_required": True,
            },
        )
    return await svc.create_product(data, session, shop_id)


@router.get(
    "/",
    response_model=ProductListResponse,
    summary="Список товаров",
    response_description="Страница товаров с пагинацией",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "items": [
                            {
                                "id": 7,
                                "name": "Футболка L",
                                "description": "Хлопок 100%",
                                "price": 1495,
                                "stock": 12,
                                "is_active": True,
                                "category_id": 3,
                                "photo_urls": ["/media/products/photo_abc123.jpg"],
                            }
                        ],
                        "total": 42,
                        "page": 1,
                        "per_page": 20,
                        "pages": 3,
                    }
                }
            }
        }
    },
)
async def list_products(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=200),
    search: Optional[str] = Query(default=None, max_length=200),
    subcategory_id: Optional[int] = Query(default=None),
    category_id: Optional[int] = Query(default=None),
    has_image: Optional[bool] = Query(default=None),
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.PRODUCTS_READ),
):
    """
    Возвращает постраничный список товаров магазина.

    Доступно как для seller (JWT), так и для бота (X-Bot-Token).
    Параметры `search`, `category_id`, `subcategory_id`, `has_image` — опциональные фильтры.
    """
    return await svc.list_products(
        page, per_page, session, shop_id,
        search=search,
        subcategory_id=subcategory_id,
        category_id=category_id,
        has_image=has_image,
    )


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    data: ProductUpdate,
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.PRODUCTS_WRITE),
):
    return await svc.update_product(product_id, data, session, shop_id)


@router.delete("/{product_id}")
async def delete_product(
    product_id: int,
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.PRODUCTS_WRITE),
):
    return await svc.delete_product(product_id, session, shop_id)


@router.post("/bulk-delete")
async def bulk_delete_products(
    data: ProductBulkDelete,
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.PRODUCTS_WRITE),
):
    return await svc.bulk_delete_products(data.ids, session, shop_id)


@router.post("/{product_id}/photo/{slot}")
async def upload_photo(
    product_id: int,
    slot: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.PRODUCTS_WRITE),
):
    if slot not in (1, 2, 3):
        raise HTTPException(400, "Slot must be 1, 2 or 3")
    return await svc.upload_photo(product_id, slot, file, session, background_tasks, shop_id)


@router.delete("/{product_id}/photo/{slot}")
async def delete_photo(
    product_id: int,
    slot: int,
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.PRODUCTS_WRITE),
):
    if slot not in (1, 2, 3):
        raise HTTPException(400, "Slot must be 1, 2 or 3")
    return await svc.delete_photo(product_id, slot, session, shop_id)


# ── Inventory stock adjustment ────────────────────────────────────────────────

@router.patch("/{product_id}/stock")
async def set_product_stock(
    product_id: int,
    data: StockAdjust,
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.PRODUCTS_WRITE),
):
    """Устанавливает абсолютное значение остатка товара."""
    product = await session.get(Product, product_id)
    if not product or product.shop_id != shop_id:
        raise HTTPException(404, "Product not found")
    product.stock = max(0, data.stock)
    await session.commit()
    return {"id": product_id, "stock": product.stock}


# ── Product variants ──────────────────────────────────────────────────────────

@router.get("/{product_id}/variants", response_model=List[VariantResponse])
async def list_variants(
    product_id: int,
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.PRODUCTS_READ),
):
    rows = (await session.execute(
        select(ProductVariant)
        .where(ProductVariant.product_id == product_id, ProductVariant.shop_id == shop_id)
        .order_by(ProductVariant.id)
    )).scalars().all()
    return [VariantResponse.model_validate(v) for v in rows]


@router.post("/{product_id}/variants", response_model=VariantResponse, status_code=201)
async def create_variant(
    product_id: int,
    data: VariantCreate,
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.PRODUCTS_WRITE),
):
    variant = ProductVariant(
        product_id=product_id, shop_id=shop_id,
        name=data.name, sku=data.sku or None,
        price=data.price, stock=data.stock, is_active=data.is_active,
    )
    session.add(variant)
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        raise HTTPException(409, "SKU already exists in this shop")
    await session.refresh(variant)
    return VariantResponse.model_validate(variant)


@router.patch("/{product_id}/variants/{variant_id}", response_model=VariantResponse)
async def update_variant(
    product_id: int,
    variant_id: int,
    data: VariantUpdate,
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.PRODUCTS_WRITE),
):
    variant = await session.get(ProductVariant, variant_id)
    if not variant or variant.product_id != product_id or variant.shop_id != shop_id:
        raise HTTPException(404, "Variant not found")
    if data.name is not None:
        variant.name = data.name
    if data.sku is not None:
        variant.sku = data.sku or None
    if data.price is not None:
        variant.price = data.price
    if data.stock is not None:
        variant.stock = max(0, data.stock)
    if data.is_active is not None:
        variant.is_active = data.is_active
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        raise HTTPException(409, "SKU already exists in this shop")
    await session.refresh(variant)
    return VariantResponse.model_validate(variant)


@router.delete("/{product_id}/variants/{variant_id}", status_code=204)
async def delete_variant(
    product_id: int,
    variant_id: int,
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.PRODUCTS_WRITE),
):
    variant = await session.get(ProductVariant, variant_id)
    if not variant or variant.product_id != product_id or variant.shop_id != shop_id:
        raise HTTPException(404, "Variant not found")
    await session.delete(variant)
    await session.commit()
