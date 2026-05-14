"""
Billing service — управление тарифами и подписками магазинов.

Ключевые функции:
  get_plans            — список всех публичных тарифов
  get_or_create_sub    — получить (или создать free) подписку магазина
  get_usage            — текущее использование ресурсов магазина
  assign_plan          — назначить тариф (superadmin)
  check_product_limit  — можно ли добавить ещё один товар?
  check_order_limit    — можно ли принять ещё один заказ в этом месяце?
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.schemas.billing import AssignPlanRequest, SubscriptionResponse, UsageResponse
from app.models.billing import PLAN_FREE, Plan, Subscription
from app.models.order import Order
from app.models.product import Product

logger = logging.getLogger(__name__)

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _get_free_plan(session: AsyncSession) -> Plan:
    """Возвращает тариф free, кидает RuntimeError если его нет в БД."""
    result = await session.execute(select(Plan).where(Plan.slug == PLAN_FREE))
    plan = result.scalar_one_or_none()
    if plan is None:
        raise RuntimeError("Free plan not found in DB — run migrations/seed")
    return plan


async def _get_plan_by_slug(session: AsyncSession, slug: str) -> Plan | None:
    result = await session.execute(select(Plan).where(Plan.slug == slug))
    return result.scalar_one_or_none()


# ── Public API ────────────────────────────────────────────────────────────────


async def get_plans(session: AsyncSession) -> list[Plan]:
    """Возвращает все публичные тарифы, упорядоченные по sort_order."""
    result = await session.execute(
        select(Plan).where(Plan.is_public == True).order_by(Plan.sort_order)
    )
    return list(result.scalars().all())


async def get_or_create_sub(session: AsyncSession, shop_id: int) -> Subscription:
    """
    Возвращает подписку магазина.
    Если подписки нет — автоматически создаёт free-подписку.
    """
    result = await session.execute(
        select(Subscription)
        .where(Subscription.shop_id == shop_id)
        .options(selectinload(Subscription.plan))
    )
    sub = result.scalar_one_or_none()

    if sub is None:
        free_plan = await _get_free_plan(session)
        sub = Subscription(
            shop_id=shop_id,
            plan_id=free_plan.id,
            status="active",
            started_at=datetime.now(timezone.utc),
        )
        session.add(sub)
        await session.flush()
        # Reload with plan relationship
        await session.refresh(sub, ["plan"])

    elif sub.plan is None:
        await session.refresh(sub, ["plan"])

    return sub


async def get_usage(session: AsyncSession, shop_id: int) -> UsageResponse:
    """Возвращает текущее использование ресурсов магазина."""
    sub = await get_or_create_sub(session, shop_id)
    plan = sub.plan

    # Количество товаров
    products_count_result = await session.execute(
        select(func.count(Product.id)).where(Product.shop_id == shop_id)
    )
    products_count = products_count_result.scalar_one() or 0

    # Заказов в текущем месяце (с начала текущего UTC-месяца)
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    orders_month_result = await session.execute(
        select(func.count(Order.id)).where(
            Order.shop_id == shop_id,
            Order.created_at >= month_start,
        )
    )
    orders_this_month = orders_month_result.scalar_one() or 0

    max_p = plan.max_products
    max_o = plan.max_orders_monthly

    return UsageResponse(
        products_count=products_count,
        products_limit=max_p,
        products_pct=round(products_count / max_p * 100, 1) if max_p > 0 else -1.0,
        orders_this_month=orders_this_month,
        orders_limit=max_o,
        orders_pct=round(orders_this_month / max_o * 100, 1) if max_o > 0 else -1.0,
        plan_slug=plan.slug,
        plan_display_name=plan.display_name,
    )


async def check_product_limit(session: AsyncSession, shop_id: int) -> tuple[bool, int, int]:
    """
    Проверяет, можно ли добавить ещё один товар.

    Returns:
        (allowed, current_count, limit)
        limit = -1 означает безлимит.
    """
    sub = await get_or_create_sub(session, shop_id)
    max_p = sub.plan.max_products
    if max_p < 0:
        return True, 0, -1

    count_result = await session.execute(
        select(func.count(Product.id)).where(Product.shop_id == shop_id)
    )
    count = count_result.scalar_one() or 0
    return count < max_p, count, max_p


async def check_order_limit(session: AsyncSession, shop_id: int) -> tuple[bool, int, int]:
    """
    Проверяет, можно ли принять ещё один заказ в текущем месяце.

    Returns:
        (allowed, orders_this_month, limit)
        limit = -1 означает безлимит.
    """
    sub = await get_or_create_sub(session, shop_id)
    max_o = sub.plan.max_orders_monthly
    if max_o < 0:
        return True, 0, -1

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    count_result = await session.execute(
        select(func.count(Order.id)).where(
            Order.shop_id == shop_id,
            Order.created_at >= month_start,
        )
    )
    count = count_result.scalar_one() or 0
    return count < max_o, count, max_o


async def assign_plan(
    data: AssignPlanRequest,
    session: AsyncSession,
) -> Subscription:
    """
    Назначает тарифный план магазину (только superadmin).
    Создаёт подписку если её нет, или обновляет существующую.
    """
    plan = await _get_plan_by_slug(session, data.plan_slug)
    if plan is None:
        from fastapi import HTTPException
        raise HTTPException(404, f"Plan '{data.plan_slug}' not found")

    result = await session.execute(
        select(Subscription)
        .where(Subscription.shop_id == data.shop_id)
        .options(selectinload(Subscription.plan))
    )
    sub = result.scalar_one_or_none()

    if sub is None:
        sub = Subscription(
            shop_id=data.shop_id,
            plan_id=plan.id,
            status="active",
            started_at=datetime.now(timezone.utc),
            expires_at=data.expires_at,
        )
        session.add(sub)
    else:
        sub.plan_id = plan.id
        sub.status = "active"
        sub.started_at = datetime.now(timezone.utc)
        sub.expires_at = data.expires_at

    await session.flush()
    await session.refresh(sub, ["plan"])
    logger.info("Plan assigned: shop_id=%s plan=%s", data.shop_id, data.plan_slug)
    return sub
