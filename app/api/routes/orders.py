"""Роуты заказов - только HTTP-слой."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import BotAuthContext, require_bot_auth, require_shop_id
from app.api.schemas.order import (
    OrderCreateRequest, OrderListResponse, OrderResponse, OrderStatusUpdate, StatusItem,
)
from app.core.rbac import Perm
from app.db.session import get_session
from app.models.order import ORDER_STATUSES
from app.services import order_service as svc
from app.services.receipt_service import generate_and_send_receipt

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("/statuses", response_model=list[StatusItem])
async def get_statuses():
    return [StatusItem(value=k, label=v) for k, v in ORDER_STATUSES.items()]


@router.post(
    "/",
    summary="Создать заказ",
    response_description="Созданный заказ с ID и итоговой суммой",
    responses={
        200: {
            "description": "Заказ успешно создан",
            "content": {
                "application/json": {
                    "example": {
                        "id": 142,
                        "shop_id": 1,
                        "user_id": 123456789,
                        "status": "new",
                        "total": 2990.0,
                        "comment": "Позвоните перед доставкой",
                        "delivery_address": "г. Москва, ул. Тверская, д. 1",
                        "created_at": "2026-05-14T12:34:56Z",
                        "items": [
                            {"product_id": 7, "name": "Футболка L", "quantity": 2, "price": 1495.0}
                        ],
                    }
                }
            },
        },
        400: {"description": "Корзина пуста или товар недоступен"},
        402: {"description": "Достигнут лимит заказов по тарифному плану"},
        403: {"description": "user_id в запросе не совпадает с токеном бота"},
    },
)
async def create_order(
    data: OrderCreateRequest,
    session: AsyncSession = Depends(get_session),
    bot_ctx: BotAuthContext = Depends(require_bot_auth),
):
    """
    Создаёт заказ из текущей корзины пользователя.

    Вызывается Telegram-ботом. Требует заголовков:
    - `X-Bot-Token` — токен бота из настроек
    - `X-Bot-Shop-Id` — ID магазина
    - `X-Bot-User-Id` — Telegram ID покупателя

    Сервер пересчитывает итоговую сумму на стороне сервера
    (клиентская сумма игнорируется).
    """
    if bot_ctx.user_id is None or bot_ctx.user_id != data.user_id:
        raise HTTPException(403, "user_id mismatch")

    # Billing: check monthly order limit
    from app.services import billing_service as billing_svc
    allowed, current, limit = await billing_svc.check_order_limit(session, bot_ctx.shop_id)
    if not allowed:
        raise HTTPException(
            status_code=402,
            detail={
                "detail": f"Достигнут лимит заказов за месяц ({current}/{limit}). "
                          "Обратитесь к администратору магазина.",
                "limit_type": "orders",
                "current": current,
                "limit": limit,
                "upgrade_required": True,
            },
        )
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
    shop_id: int = require_shop_id(Perm.ORDERS_READ),
):
    return await svc.list_orders(status, page, per_page, session, shop_id, date_from, date_to)


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: int,
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.ORDERS_READ),
):
    return await svc.get_order(order_id, session, shop_id)


@router.patch("/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: int,
    data: OrderStatusUpdate,
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.ORDERS_WRITE),
):
    return await svc.update_order_status(
        order_id, data.status, data.comment, session, shop_id,
        staff_notes=data.staff_notes,
        force=data.force,
    )


@router.post("/{order_id}/receipt")
async def send_receipt(
    order_id: int,
    session: AsyncSession = Depends(get_session),
    _: int = require_shop_id(Perm.ORDERS_WRITE),
):
    return await generate_and_send_receipt(order_id, session)
