"""
Super-admin API для управления магазинами.

Эндпоинты для суперадмина (полный CRUD) и для владельца
(только чтение своего магазина + управление bot_token).

GET    /platform/shops                     [super_admin]
POST   /platform/shops                     [super_admin]
GET    /platform/shops/{id}                [super_admin | owner of shop]
PATCH  /platform/shops/{id}                [super_admin]
DELETE /platform/shops/{id}                [super_admin]
PUT    /platform/shops/{id}/bot-token      [super_admin | owner of shop]
DELETE /platform/shops/{id}/bot-token      [super_admin]
PATCH  /platform/shops/{id}/status         [super_admin]
PATCH  /platform/shops/{id}/plan           [super_admin]
POST   /platform/shops/{id}/assign         [super_admin]
GET    /platform/shops/{id}/stats          [super_admin | owner of shop]
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    PlatformAuthContext,
    assert_shop_access,
    require_platform_auth,
    require_super_admin,
)
from app.api.schemas.shop import (
    BotTokenUpdate,
    ShopAssignRequest,
    ShopCreate,
    ShopListResponse,
    ShopPlanUpdate,
    ShopResponse,
    ShopStatsResponse,
    ShopStatusUpdate,
    ShopUpdate,
)
from app.db.session import get_session
from app.services import shop_service as svc

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/platform/shops", tags=["platform-shops"])


# ── List / Create ─────────────────────────────────────────────────────────────

@router.get("/", response_model=ShopListResponse)
async def list_shops(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    status: Optional[str] = Query(default=None),
    owner_id: Optional[int] = Query(default=None),
    session: AsyncSession = Depends(get_session),
    _: PlatformAuthContext = Depends(require_super_admin),
):
    return await svc.list_shops(page, per_page, session, status=status, owner_id=owner_id)


@router.post("/", response_model=ShopResponse, status_code=201)
async def create_shop(
    data: ShopCreate,
    session: AsyncSession = Depends(get_session),
    _: PlatformAuthContext = Depends(require_super_admin),
):
    return await svc.create_shop(data, session)


# ── Single shop ───────────────────────────────────────────────────────────────

@router.get("/{shop_id}", response_model=ShopResponse)
async def get_shop(
    shop_id: int,
    session: AsyncSession = Depends(get_session),
    ctx: PlatformAuthContext = Depends(require_platform_auth),
):
    assert_shop_access(ctx, shop_id)
    return await svc.get_shop(shop_id, session)


@router.patch("/{shop_id}", response_model=ShopResponse)
async def update_shop(
    shop_id: int,
    data: ShopUpdate,
    session: AsyncSession = Depends(get_session),
    _: PlatformAuthContext = Depends(require_super_admin),
):
    return await svc.update_shop(shop_id, data, session)


@router.delete("/{shop_id}", status_code=204)
async def delete_shop(
    shop_id: int,
    session: AsyncSession = Depends(get_session),
    _: PlatformAuthContext = Depends(require_super_admin),
):
    await svc.delete_shop(shop_id, session)


# ── Bot token ─────────────────────────────────────────────────────────────────

@router.put("/{shop_id}/bot-token", response_model=ShopResponse)
async def set_bot_token(
    shop_id: int,
    data: BotTokenUpdate,
    session: AsyncSession = Depends(get_session),
    ctx: PlatformAuthContext = Depends(require_platform_auth),
):
    """Зашифровать и сохранить bot_token. Доступен владельцу магазина и суперадмину."""
    assert_shop_access(ctx, shop_id)
    return await svc.set_bot_token(shop_id, data.bot_token, session)


@router.delete("/{shop_id}/bot-token", response_model=ShopResponse)
async def delete_bot_token(
    shop_id: int,
    session: AsyncSession = Depends(get_session),
    _: PlatformAuthContext = Depends(require_super_admin),
):
    return await svc.delete_bot_token(shop_id, session)


# ── Status ────────────────────────────────────────────────────────────────────

@router.patch("/{shop_id}/status", response_model=ShopResponse)
async def set_status(
    shop_id: int,
    data: ShopStatusUpdate,
    session: AsyncSession = Depends(get_session),
    _: PlatformAuthContext = Depends(require_super_admin),
):
    return await svc.set_status(shop_id, data.status, session)


# ── Plan ──────────────────────────────────────────────────────────────────────

@router.patch("/{shop_id}/plan", response_model=ShopResponse)
async def update_plan(
    shop_id: int,
    data: ShopPlanUpdate,
    session: AsyncSession = Depends(get_session),
    _: PlatformAuthContext = Depends(require_super_admin),
):
    return await svc.update_plan(shop_id, data.plan, data.plan_expires_at, session)


# ── Assign owner ──────────────────────────────────────────────────────────────

@router.post("/{shop_id}/assign", response_model=ShopResponse)
async def assign_owner(
    shop_id: int,
    data: ShopAssignRequest,
    session: AsyncSession = Depends(get_session),
    _: PlatformAuthContext = Depends(require_super_admin),
):
    return await svc.assign_owner(shop_id, data.owner_id, session)


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/{shop_id}/stats", response_model=ShopStatsResponse)
async def get_stats(
    shop_id: int,
    session: AsyncSession = Depends(get_session),
    ctx: PlatformAuthContext = Depends(require_platform_auth),
):
    assert_shop_access(ctx, shop_id)
    return await svc.get_stats(shop_id, session)
