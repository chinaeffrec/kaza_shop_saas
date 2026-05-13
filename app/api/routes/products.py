"""Роуты товаров - только HTTP-слой, вся логика в product_service."""
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_owner_shop_id
from app.api.schemas.product import (
    ProductBulkDelete, ProductCreate, ProductListResponse, ProductResponse, ProductUpdate,
)
from app.db.session import get_session
from app.services import product_service as svc

router = APIRouter(prefix="/products", tags=["Products"])


@router.post("/", response_model=ProductResponse)
async def create_product(
    data: ProductCreate,
    session: AsyncSession = Depends(get_session),
    shop_id: int = Depends(get_owner_shop_id),
):
    return await svc.create_product(data, session, shop_id)


@router.get("/", response_model=ProductListResponse)
async def list_products(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=200),
    search: Optional[str] = Query(default=None, max_length=200),
    subcategory_id: Optional[int] = Query(default=None),
    category_id: Optional[int] = Query(default=None),
    has_image: Optional[bool] = Query(default=None),
    session: AsyncSession = Depends(get_session),
    shop_id: int = Depends(get_owner_shop_id),
):
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
    shop_id: int = Depends(get_owner_shop_id),
):
    return await svc.update_product(product_id, data, session, shop_id)


@router.delete("/{product_id}")
async def delete_product(
    product_id: int,
    session: AsyncSession = Depends(get_session),
    shop_id: int = Depends(get_owner_shop_id),
):
    return await svc.delete_product(product_id, session, shop_id)


@router.post("/bulk-delete")
async def bulk_delete_products(
    data: ProductBulkDelete,
    session: AsyncSession = Depends(get_session),
    shop_id: int = Depends(get_owner_shop_id),
):
    return await svc.bulk_delete_products(data.ids, session, shop_id)


@router.post("/{product_id}/photo/{slot}")
async def upload_photo(
    product_id: int,
    slot: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    shop_id: int = Depends(get_owner_shop_id),
):
    if slot not in (1, 2, 3):
        raise HTTPException(400, "Slot must be 1, 2 or 3")
    return await svc.upload_photo(product_id, slot, file, session, background_tasks, shop_id)


@router.delete("/{product_id}/photo/{slot}")
async def delete_photo(
    product_id: int,
    slot: int,
    session: AsyncSession = Depends(get_session),
    shop_id: int = Depends(get_owner_shop_id),
):
    if slot not in (1, 2, 3):
        raise HTTPException(400, "Slot must be 1, 2 or 3")
    return await svc.delete_photo(product_id, slot, session, shop_id)
