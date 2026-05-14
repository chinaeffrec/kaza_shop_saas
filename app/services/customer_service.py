"""
CRM-сервис: агрегированное представление покупателей магазина.

Покупатель = запись User (telegram_id + shop_id) + агрегаты из orders.
Здесь нет отдельной таблицы — всё считается из существующих данных.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.user import User


@dataclass
class CustomerSummary:
    id: int                          # users.id
    telegram_id: int
    shop_id: int
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]
    notes: Optional[str]
    is_active: bool
    total_orders: int
    total_spent: int                 # сумма по billable-статусам
    first_order_at: Optional[datetime]
    last_order_at: Optional[datetime]
    created_at: datetime


_BILLABLE = {"paid", "confirmed", "assembled", "shipped", "delivered"}


async def list_customers(
    page: int,
    per_page: int,
    session: AsyncSession,
    shop_id: int,
    search: Optional[str] = None,
) -> tuple[list[CustomerSummary], int]:
    """Список покупателей с агрегатами. Возвращает (items, total)."""

    base = select(User).where(User.shop_id == shop_id)
    count_base = select(func.count()).select_from(User).where(User.shop_id == shop_id)

    if search:
        like = f"%{search}%"
        from sqlalchemy import or_
        condition = or_(
            User.username.ilike(like),
            User.first_name.ilike(like),
            User.last_name.ilike(like),
            User.phone.ilike(like),
        )
        base = base.where(condition)
        count_base = count_base.where(condition)

    total, users = await asyncio.gather(
        session.execute(count_base),
        session.execute(
            base.order_by(User.created_at.desc())
            .offset((page - 1) * per_page).limit(per_page)
        ),
    )
    total_count = total.scalar() or 0
    user_list = users.scalars().all()

    if not user_list:
        return [], total_count

    # Агрегаты за один запрос для всех пользователей выборки
    tg_ids = [u.telegram_id for u in user_list]
    agg_q = (
        select(
            Order.user_id,
            func.count(Order.id).label("total_orders"),
            func.sum(Order.total).filter(Order.status.in_(_BILLABLE)).label("total_spent"),
            func.min(Order.created_at).label("first_order_at"),
            func.max(Order.created_at).label("last_order_at"),
        )
        .where(Order.shop_id == shop_id, Order.user_id.in_(tg_ids))
        .group_by(Order.user_id)
    )
    agg_rows = (await session.execute(agg_q)).all()
    agg_map: dict[int, dict] = {
        r.user_id: {
            "total_orders": r.total_orders or 0,
            "total_spent": int(r.total_spent or 0),
            "first_order_at": r.first_order_at,
            "last_order_at": r.last_order_at,
        }
        for r in agg_rows
    }

    return [
        CustomerSummary(
            id=u.id,
            telegram_id=u.telegram_id,
            shop_id=u.shop_id,
            username=u.username,
            first_name=u.first_name,
            last_name=u.last_name,
            phone=u.phone,
            notes=u.notes,
            is_active=u.is_active,
            created_at=u.created_at,
            **agg_map.get(u.telegram_id, {
                "total_orders": 0, "total_spent": 0,
                "first_order_at": None, "last_order_at": None,
            }),
        )
        for u in user_list
    ], total_count


async def get_customer(
    customer_id: int, session: AsyncSession, shop_id: int,
) -> CustomerSummary:
    user = await session.get(User, customer_id)
    if not user or user.shop_id != shop_id:
        raise HTTPException(404, "Customer not found")

    agg_q = (
        select(
            func.count(Order.id).label("total_orders"),
            func.sum(Order.total).filter(Order.status.in_(_BILLABLE)).label("total_spent"),
            func.min(Order.created_at).label("first_order_at"),
            func.max(Order.created_at).label("last_order_at"),
        )
        .where(Order.shop_id == shop_id, Order.user_id == user.telegram_id)
    )
    row = (await session.execute(agg_q)).one()

    return CustomerSummary(
        id=user.id,
        telegram_id=user.telegram_id,
        shop_id=user.shop_id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        phone=user.phone,
        notes=user.notes,
        is_active=user.is_active,
        created_at=user.created_at,
        total_orders=row.total_orders or 0,
        total_spent=int(row.total_spent or 0),
        first_order_at=row.first_order_at,
        last_order_at=row.last_order_at,
    )


async def update_customer(
    customer_id: int,
    phone: Optional[str],
    notes: Optional[str],
    session: AsyncSession,
    shop_id: int,
) -> CustomerSummary:
    user = await session.get(User, customer_id)
    if not user or user.shop_id != shop_id:
        raise HTTPException(404, "Customer not found")

    if phone is not None:
        user.phone = phone or None
    if notes is not None:
        user.notes = notes or None

    await session.commit()
    return await get_customer(customer_id, session, shop_id)
