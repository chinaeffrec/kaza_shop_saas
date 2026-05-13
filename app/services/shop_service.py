"""Бизнес-логика управления магазинами (super-admin API)."""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.shop import (
    ShopCreate, ShopListResponse, ShopResponse, ShopStatsResponse, ShopUpdate,
)
from app.core.encryption import decrypt_field, encrypt_field
from app.models.cart import Cart
from app.models.order import Order
from app.models.platform import PLAN_MAX_PRODUCTS, PlatformUser, Shop
from app.models.product import Product
from app.models.user import User

logger = logging.getLogger(__name__)


def _to_response(shop: Shop, owner: PlatformUser | None = None) -> ShopResponse:
    return ShopResponse(
        id=shop.id,
        owner_id=shop.owner_id,
        owner_email=owner.email if owner else None,
        name=shop.name,
        status=shop.status,
        plan=shop.plan,
        plan_expires_at=shop.plan_expires_at,
        max_products=shop.max_products,
        has_bot_token=bool(shop.bot_token),
        created_at=shop.created_at,
        updated_at=shop.updated_at,
    )


async def _get_shop_or_404(shop_id: int, session: AsyncSession) -> Shop:
    res = await session.execute(select(Shop).where(Shop.id == shop_id))
    shop = res.scalar_one_or_none()
    if not shop:
        raise HTTPException(404, "Shop not found")
    return shop


async def _get_owner(owner_id: int, session: AsyncSession) -> PlatformUser | None:
    res = await session.execute(select(PlatformUser).where(PlatformUser.id == owner_id))
    return res.scalar_one_or_none()


# ── CRUD ──────────────────────────────────────────────────────────────────────

async def create_shop(data: ShopCreate, session: AsyncSession) -> ShopResponse:
    owner = await _get_owner(data.owner_id, session)
    if not owner:
        raise HTTPException(400, f"Platform user {data.owner_id} not found")

    max_products = PLAN_MAX_PRODUCTS.get(data.plan, PLAN_MAX_PRODUCTS["trial"])
    encrypted_token: str | None = None
    if data.bot_token:
        try:
            encrypted_token = encrypt_field(data.bot_token)
        except Exception as e:
            raise HTTPException(400, f"Cannot encrypt bot_token: {e}")

    shop = Shop(
        owner_id=data.owner_id,
        name=data.name,
        bot_token=encrypted_token,
        plan=data.plan,
        status="trial",
        max_products=max_products,
    )
    session.add(shop)
    await session.commit()
    await session.refresh(shop)
    logger.info("Shop created: id=%d name=%s owner=%d", shop.id, shop.name, shop.owner_id)
    return _to_response(shop, owner)


async def list_shops(
    page: int,
    per_page: int,
    session: AsyncSession,
    status: Optional[str] = None,
    owner_id: Optional[int] = None,
) -> ShopListResponse:
    q = select(Shop)
    count_q = select(func.count()).select_from(Shop)
    if status:
        q = q.where(Shop.status == status)
        count_q = count_q.where(Shop.status == status)
    if owner_id:
        q = q.where(Shop.owner_id == owner_id)
        count_q = count_q.where(Shop.owner_id == owner_id)

    total = (await session.execute(count_q)).scalar() or 0
    offset = (page - 1) * per_page
    shops = (
        await session.execute(q.order_by(Shop.created_at.desc()).offset(offset).limit(per_page))
    ).scalars().all()

    owner_ids = {s.owner_id for s in shops}
    owners: dict[int, PlatformUser] = {}
    if owner_ids:
        res = await session.execute(
            select(PlatformUser).where(PlatformUser.id.in_(owner_ids))
        )
        owners = {u.id: u for u in res.scalars().all()}

    items = [_to_response(s, owners.get(s.owner_id)) for s in shops]
    return ShopListResponse(
        items=items, total=total, page=page, per_page=per_page,
        pages=max(1, (total + per_page - 1) // per_page),
    )


async def get_shop(shop_id: int, session: AsyncSession) -> ShopResponse:
    shop = await _get_shop_or_404(shop_id, session)
    owner = await _get_owner(shop.owner_id, session)
    return _to_response(shop, owner)


async def update_shop(shop_id: int, data: ShopUpdate, session: AsyncSession) -> ShopResponse:
    shop = await _get_shop_or_404(shop_id, session)
    if data.name is not None:
        shop.name = data.name
    shop.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(shop)
    owner = await _get_owner(shop.owner_id, session)
    return _to_response(shop, owner)


async def delete_shop(shop_id: int, session: AsyncSession) -> None:
    shop = await _get_shop_or_404(shop_id, session)
    await session.delete(shop)
    await session.commit()
    logger.info("Shop deleted: id=%d", shop_id)


# ── Bot token ─────────────────────────────────────────────────────────────────

async def set_bot_token(shop_id: int, raw_token: str, session: AsyncSession) -> ShopResponse:
    shop = await _get_shop_or_404(shop_id, session)
    try:
        shop.bot_token = encrypt_field(raw_token)
    except Exception as e:
        raise HTTPException(400, f"Cannot encrypt bot_token: {e}")
    shop.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(shop)
    owner = await _get_owner(shop.owner_id, session)
    logger.info("Bot token updated for shop_id=%d", shop_id)
    return _to_response(shop, owner)


async def delete_bot_token(shop_id: int, session: AsyncSession) -> ShopResponse:
    shop = await _get_shop_or_404(shop_id, session)
    shop.bot_token = None
    shop.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(shop)
    owner = await _get_owner(shop.owner_id, session)
    logger.info("Bot token deleted for shop_id=%d", shop_id)
    return _to_response(shop, owner)


# ── Status & plan ─────────────────────────────────────────────────────────────

async def set_status(shop_id: int, status: str, session: AsyncSession) -> ShopResponse:
    from app.models.platform import SHOP_STATUSES
    if status not in SHOP_STATUSES:
        raise HTTPException(400, f"Invalid status: {status}")
    shop = await _get_shop_or_404(shop_id, session)
    old_status = shop.status
    shop.status = status
    shop.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(shop)
    owner = await _get_owner(shop.owner_id, session)
    logger.info("Shop %d status: %s → %s", shop_id, old_status, status)
    return _to_response(shop, owner)


async def update_plan(
    shop_id: int,
    plan: str,
    plan_expires_at: datetime | None,
    session: AsyncSession,
) -> ShopResponse:
    from app.models.platform import SHOP_PLANS
    if plan not in SHOP_PLANS:
        raise HTTPException(400, f"Invalid plan: {plan}")
    shop = await _get_shop_or_404(shop_id, session)
    shop.plan = plan
    shop.max_products = PLAN_MAX_PRODUCTS.get(plan, PLAN_MAX_PRODUCTS["trial"])
    shop.plan_expires_at = plan_expires_at
    shop.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(shop)
    owner = await _get_owner(shop.owner_id, session)
    logger.info("Shop %d plan updated: %s, expires=%s", shop_id, plan, plan_expires_at)
    return _to_response(shop, owner)


async def assign_owner(shop_id: int, owner_id: int, session: AsyncSession) -> ShopResponse:
    shop = await _get_shop_or_404(shop_id, session)
    owner = await _get_owner(owner_id, session)
    if not owner:
        raise HTTPException(400, f"Platform user {owner_id} not found")
    shop.owner_id = owner_id
    shop.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(shop)
    logger.info("Shop %d reassigned to owner %d", shop_id, owner_id)
    return _to_response(shop, owner)


# ── Stats ─────────────────────────────────────────────────────────────────────

async def get_stats(shop_id: int, session: AsyncSession) -> ShopStatsResponse:
    await _get_shop_or_404(shop_id, session)

    REVENUE_STATUSES = {"paid", "confirmed", "assembled", "shipped", "delivered"}

    total_orders = (await session.execute(
        select(func.count()).select_from(Order).where(Order.shop_id == shop_id)
    )).scalar() or 0

    active_orders = (await session.execute(
        select(func.count()).select_from(Order).where(
            Order.shop_id == shop_id,
            Order.status.not_in(["delivered", "cancelled", "returned"]),
        )
    )).scalar() or 0

    total_products = (await session.execute(
        select(func.count()).select_from(Product).where(Product.shop_id == shop_id)
    )).scalar() or 0

    total_users = (await session.execute(
        select(func.count()).select_from(User).where(User.shop_id == shop_id)
    )).scalar() or 0

    revenue_result = await session.execute(
        select(func.coalesce(func.sum(Order.total), 0)).where(
            Order.shop_id == shop_id,
            Order.status.in_(REVENUE_STATUSES),
        )
    )
    total_revenue = float(revenue_result.scalar() or 0)

    return ShopStatsResponse(
        shop_id=shop_id,
        total_orders=total_orders,
        total_products=total_products,
        total_users=total_users,
        total_revenue=total_revenue,
        active_orders=active_orders,
    )
