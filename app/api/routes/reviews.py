"""Роуты отзывов покупателей."""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import BotAuthContext, require_bot_auth, require_shop_id
from app.api.schemas.review import (
    ReviewCreate, ReviewListResponse, ReviewResponse, ReviewStats, ReviewUpdate,
)
from app.core.rbac import Perm
from app.db.session import get_session
from app.services import review_service as svc

router = APIRouter(prefix="/reviews", tags=["reviews"])


# ── Public: для бота и Mini App ───────────────────────────────────────────────

@router.get(
    "/product/{product_id}",
    response_model=ReviewListResponse,
    summary="Одобренные отзывы по товару (публичный)",
)
async def get_product_reviews(
    product_id: int,
    shop_id: int = Query(..., description="ID магазина"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
):
    return await svc.get_product_reviews(
        session, shop_id, product_id,
        only_approved=True, page=page, per_page=per_page,
    )


@router.get(
    "/product/{product_id}/stats",
    response_model=ReviewStats,
    summary="Статистика отзывов по товару (публичный)",
)
async def get_product_review_stats(
    product_id: int,
    shop_id: int = Query(..., description="ID магазина"),
    session: AsyncSession = Depends(get_session),
):
    return await svc.get_review_stats(session, shop_id, product_id)


@router.post(
    "/bot",
    response_model=ReviewResponse,
    status_code=201,
    summary="Создать отзыв (от бота)",
)
async def create_review_bot(
    data: ReviewCreate,
    session: AsyncSession = Depends(get_session),
    bot_ctx: BotAuthContext = Depends(require_bot_auth),
):
    """Bot-only endpoint. Проверяет reviews_enabled в настройках магазина."""
    from app.services.settings_service_ext import read_settings
    settings = await read_settings(session, bot_ctx.shop_id)
    if not settings.reviews_enabled:
        from fastapi import HTTPException
        raise HTTPException(403, "Отзывы отключены в настройках магазина.")
    return await svc.create_review(data, session, bot_ctx.shop_id, auto_approve=True)


# ── Seller panel: модерация ───────────────────────────────────────────────────

@router.get(
    "/",
    response_model=ReviewListResponse,
    summary="Список отзывов магазина (панель продавца)",
)
async def list_reviews(
    status: Literal["pending", "approved", "all"] = Query(default="all"),
    product_id: Optional[int] = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=30, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.REVIEWS_READ),
):
    return await svc.list_reviews(session, shop_id, status, product_id, page, per_page)


@router.patch(
    "/{review_id}",
    response_model=ReviewResponse,
    summary="Одобрить / отклонить отзыв",
)
async def moderate_review(
    review_id: int,
    data: ReviewUpdate,
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.REVIEWS_WRITE),
):
    return await svc.moderate_review(review_id, data, session, shop_id)


@router.delete(
    "/{review_id}",
    status_code=204,
    summary="Удалить отзыв",
)
async def delete_review(
    review_id: int,
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.REVIEWS_WRITE),
):
    await svc.delete_review(review_id, session, shop_id)
