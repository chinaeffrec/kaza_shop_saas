"""Роуты заказов - только HTTP-слой."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_owner_shop_id
from app.api.routes.auth import BotAuthContext, require_bot_auth
from app.api.schemas.order import (
    OrderCreateRequest, OrderListResponse, OrderResponse, OrderStatusUpdate, StatusItem,
)
from app.db.session import get_session
from app.models.order import ORDER_STATUSES
from app.services import order_service as svc
from app.services.receipt_service import generate_and_send_receipt

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("/statuses", response_model=list[StatusItem])
async def get_statuses():
    return [StatusItem(value=k, label=v) for k, v in ORDER_STATUSES.items()]


@router.post("/", summary="Создать заказ (вызывается ботом)")
async def create_order(
    data: OrderCreateRequest,
    session: AsyncSession = Depends(get_session),
    bot_ctx: BotAuthContext = Depends(require_bot_auth),
):
    if bot_ctx.user_id is None or bot_ctx.user_id != data.user_id:
        raise HTTPException(403, "user_id mismatch")
    return await svc.create_order(data, session, bot_ctx.shop_id)


@router.get("/user/{user_id}", summary="История заказов пользователя (для бота)")
async def get_user_orders(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    bot_ctx: BotAuthContext = Depends(require_bot_auth),
):
    if bot_ctx.user_id is None or bot_ctx.user_id != user_id:
        raise HTTPException(403, "user_id mismatch")
    return await svc.get_user_orders(user_id, session, bot_ctx.shop_id)


@router.get("/", response_model=OrderListResponse)
async def list_orders(
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    shop_id: int = Depends(get_owner_shop_id),
):
    return await svc.list_orders(status, page, per_page, session, shop_id, date_from, date_to)


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: int,
    session: AsyncSession = Depends(get_session),
    shop_id: int = Depends(get_owner_shop_id),
):
    return await svc.get_order(order_id, session, shop_id)


@router.patch("/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: int,
    data: OrderStatusUpdate,
    session: AsyncSession = Depends(get_session),
    shop_id: int = Depends(get_owner_shop_id),
):
    return await svc.update_order_status(order_id, data.status, data.comment, session, shop_id)


@router.post("/{order_id}/receipt")
async def send_receipt(
    order_id: int,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_auth),
):
    return await generate_and_send_receipt(order_id, session)
