"""Роуты каталога - публичные (для бота) + защищённый reload."""
from typing import List, Optional

from fastapi import APIRouter, Depends, Header
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_admin_shop_id, require_auth
from app.api.schemas.catalog import (
    CacheReloadResponse, CatalogProductResponse,
    CategoryResponse, SubCategoryResponse,
)
from app.db.session import get_session
from app.models.category import Category
from app.models.product import Product
from app.models.subcategory import SubCategory
from app.services.cache_service import invalidate_catalog_cache
from app.services.settings_service import get_shop_settings

router = APIRouter(prefix="/catalog", tags=["catalog"])


def _bot_shop_id(x_bot_shop_id: Optional[int] = Header(default=None, alias="X-Bot-Shop-Id")) -> int:
    """Извлекает shop_id из заголовка бота; для legacy-запросов возвращает 1."""
    return x_bot_shop_id if x_bot_shop_id is not None else 1


@router.get("/categories", response_model=List[CategoryResponse])
async def get_categories(
    session: AsyncSession = Depends(get_session),
    shop_id: int = Depends(_bot_shop_id),
):
    result = await session.execute(
        select(Category).where(Category.shop_id == shop_id)
    )
    return [CategoryResponse(id=c.id, name=c.name) for c in result.scalars().all()]


@router.get("/subcategories", response_model=List[SubCategoryResponse])
async def get_all_subcategories(
    session: AsyncSession = Depends(get_session),
    shop_id: int = Depends(_bot_shop_id),
):
    """Все подкатегории одним запросом — для панели управления."""
    result = await session.execute(
        select(SubCategory)
        .where(SubCategory.shop_id == shop_id)
        .order_by(SubCategory.category_id, SubCategory.id)
    )
    return [SubCategoryResponse(id=s.id, name=s.name, category_id=s.category_id) for s in result.scalars().all()]


@router.get("/categories/{category_id}/subcategories", response_model=List[SubCategoryResponse])
async def get_subcategories(
    category_id: int,
    session: AsyncSession = Depends(get_session),
    shop_id: int = Depends(_bot_shop_id),
):
    result = await session.execute(
        select(SubCategory).where(
            SubCategory.category_id == category_id,
            SubCategory.shop_id == shop_id,
        )
    )
    return [SubCategoryResponse(id=s.id, name=s.name, category_id=s.category_id) for s in result.scalars().all()]


@router.get("/subcategories/{subcategory_id}/products", response_model=List[CatalogProductResponse])
async def get_products(
    subcategory_id: int,
    session: AsyncSession = Depends(get_session),
    shop_id: int = Depends(_bot_shop_id),
):
    shop = await get_shop_settings(session, shop_id)
    hide_oos = shop.hide_out_of_stock or False

    q = select(Product).where(
        Product.subcategory_id == subcategory_id,
        Product.shop_id == shop_id,
        Product.is_active == True,
    ).order_by(func.lower(Product.name).asc(), Product.id.asc())
    if hide_oos:
        q = q.where(Product.stock > 0)

    products = (await session.execute(q)).scalars().all()
    return [
        CatalogProductResponse(
            id=p.id, name=p.name, price=p.price, discount_price=p.discount_price,
            description=p.description, characteristics=p.characteristics,
            image_file_id=p.image_file_id,
            image_url=f"/media/{p.image_file_id}" if p.image_file_id else None,
            image_url_2=f"/media/{p.image_file_id_2}" if getattr(p, "image_file_id_2", None) else None,
            image_url_3=f"/media/{p.image_file_id_3}" if getattr(p, "image_file_id_3", None) else None,
            stock=p.stock or 0,
            images=[x for x in [
                p.image_file_id,
                getattr(p, "image_file_id_2", None),
                getattr(p, "image_file_id_3", None),
            ] if x],
        )
        for p in products
    ]


@router.get("/products/{product_id}", response_model=CatalogProductResponse)
async def get_product(
    product_id: int,
    session: AsyncSession = Depends(get_session),
    shop_id: int = Depends(_bot_shop_id),
):
    from fastapi import HTTPException
    result = await session.execute(
        select(Product).where(Product.id == product_id, Product.shop_id == shop_id)
    )
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(404, "Product not found")
    return CatalogProductResponse(
        id=p.id, name=p.name, price=p.price, discount_price=p.discount_price,
        description=p.description, characteristics=p.characteristics,
        image_file_id=p.image_file_id,
        image_url=f"/media/{p.image_file_id}" if p.image_file_id else None,
        image_url_2=None, image_url_3=None, stock=p.stock or 0, images=[],
    )


@router.post("/cache/reload", response_model=CacheReloadResponse)
async def reload_cache(
    _: str = Depends(require_auth),
    shop_id: int = Depends(get_admin_shop_id),
):
    await invalidate_catalog_cache(shop_id)
    return CacheReloadResponse(status="ok", message="Кэш каталога перезагружен")
