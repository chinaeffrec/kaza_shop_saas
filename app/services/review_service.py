"""
Review service — бизнес-логика отзывов покупателей.

Принцип модерации:
  Если в настройках магазина reviews_enabled=True и нет ручной модерации —
  отзыв создаётся сразу как is_approved=True.
  В будущем можно добавить флаг moderation_required в ShopSettings.
"""
from __future__ import annotations

import logging
from typing import Literal, Optional

from fastapi import HTTPException
from sqlalchemy import asc, desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.schemas.review import (
    ReviewCreate, ReviewListResponse, ReviewResponse, ReviewStats, ReviewUpdate,
)
from app.models.product import Product
from app.models.review import Review

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_response(review: Review, product_name: str | None = None) -> ReviewResponse:
    return ReviewResponse(
        id=review.id,
        shop_id=review.shop_id,
        product_id=review.product_id,
        user_id=review.user_id,
        order_id=review.order_id,
        rating=review.rating,
        text=review.text,
        is_approved=review.is_approved,
        created_at=review.created_at,
        product_name=product_name,
    )


async def _product_name(session: AsyncSession, product_id: int) -> str | None:
    r = await session.execute(select(Product.name).where(Product.id == product_id))
    return r.scalar_one_or_none()


# ── Public (bot / miniapp) ────────────────────────────────────────────────────

async def create_review(
    data: ReviewCreate,
    session: AsyncSession,
    shop_id: int,
    auto_approve: bool = True,
) -> ReviewResponse:
    """Создаёт отзыв, поданный через бота или Mini App."""
    review = Review(
        shop_id=shop_id,
        product_id=data.product_id,
        user_id=data.user_id,
        order_id=data.order_id,
        rating=data.rating,
        text=data.text,
        is_approved=auto_approve,
    )
    session.add(review)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(409, "Отзыв для этого заказа уже оставлен.")
    await session.commit()
    pname = await _product_name(session, data.product_id)
    logger.info("Review created: id=%s shop=%s product=%s rating=%s",
                review.id, shop_id, data.product_id, data.rating)
    return _to_response(review, pname)


async def get_product_reviews(
    session: AsyncSession,
    shop_id: int,
    product_id: int,
    only_approved: bool = True,
    page: int = 1,
    per_page: int = 20,
) -> ReviewListResponse:
    """Публичные одобренные отзывы для карточки товара."""
    q = select(Review).where(
        Review.shop_id == shop_id,
        Review.product_id == product_id,
    )
    if only_approved:
        q = q.where(Review.is_approved == True)

    total_r = await session.execute(select(func.count()).select_from(q.subquery()))
    total = total_r.scalar_one() or 0

    rows = await session.execute(
        q.order_by(desc(Review.created_at))
         .offset((page - 1) * per_page)
         .limit(per_page)
    )
    reviews = list(rows.scalars().all())
    return ReviewListResponse(
        items=[_to_response(r) for r in reviews],
        total=total,
        page=page,
        per_page=per_page,
    )


async def get_review_stats(
    session: AsyncSession,
    shop_id: int,
    product_id: int,
) -> ReviewStats:
    """Агрегированная статистика: среднее, распределение."""
    rows = await session.execute(
        select(Review.rating)
        .where(
            Review.shop_id == shop_id,
            Review.product_id == product_id,
            Review.is_approved == True,
        )
    )
    ratings = [r for (r,) in rows.all()]
    count = len(ratings)
    avg = round(sum(ratings) / count, 2) if count else 0.0
    dist = {str(i): 0 for i in range(1, 6)}
    for r in ratings:
        dist[str(r)] = dist.get(str(r), 0) + 1
    return ReviewStats(
        product_id=product_id,
        count=count,
        average=avg,
        distribution=dist,
    )


# ── Seller panel (moderation) ─────────────────────────────────────────────────

async def list_reviews(
    session: AsyncSession,
    shop_id: int,
    status: Literal["pending", "approved", "all"] = "all",
    product_id: Optional[int] = None,
    page: int = 1,
    per_page: int = 30,
) -> ReviewListResponse:
    q = select(Review).where(Review.shop_id == shop_id)
    if status == "pending":
        q = q.where(Review.is_approved == False)
    elif status == "approved":
        q = q.where(Review.is_approved == True)
    if product_id:
        q = q.where(Review.product_id == product_id)

    total_r = await session.execute(select(func.count()).select_from(q.subquery()))
    total = total_r.scalar_one() or 0

    rows = await session.execute(
        q.options(selectinload(Review.product))
         .order_by(desc(Review.created_at))
         .offset((page - 1) * per_page)
         .limit(per_page)
    )
    reviews = list(rows.scalars().all())
    items = [
        _to_response(r, r.product.name if r.product else None)
        for r in reviews
    ]
    return ReviewListResponse(items=items, total=total, page=page, per_page=per_page)


async def moderate_review(
    review_id: int,
    data: ReviewUpdate,
    session: AsyncSession,
    shop_id: int,
) -> ReviewResponse:
    r = await session.get(Review, review_id)
    if not r or r.shop_id != shop_id:
        raise HTTPException(404, "Отзыв не найден.")
    if data.is_approved is not None:
        r.is_approved = data.is_approved
    if data.text is not None:
        r.text = data.text
    await session.commit()
    pname = await _product_name(session, r.product_id)
    return _to_response(r, pname)


async def delete_review(
    review_id: int,
    session: AsyncSession,
    shop_id: int,
) -> None:
    r = await session.get(Review, review_id)
    if not r or r.shop_id != shop_id:
        raise HTTPException(404, "Отзыв не найден.")
    await session.delete(r)
    await session.commit()
