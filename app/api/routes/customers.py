"""
CRM эндпоинты — покупатели магазина.

GET   /customers/          — список с LTV и агрегатами
GET   /customers/{id}      — карточка покупателя
PATCH /customers/{id}      — обновить phone / notes
GET   /customers/{id}/orders — история заказов конкретного покупателя
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_shop_id
from app.api.schemas.order import OrderListResponse
from app.core.rbac import Perm
from app.db.session import get_session
from app.services import customer_service as svc
from app.services import order_service as order_svc

router = APIRouter(prefix="/customers", tags=["customers"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class CustomerResponse(BaseModel):
    id: int
    telegram_id: int
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]
    notes: Optional[str]
    is_active: bool
    total_orders: int
    total_spent: int
    first_order_at: Optional[str]
    last_order_at: Optional[str]
    created_at: str


class CustomerListResponse(BaseModel):
    items: list[CustomerResponse]
    total: int
    page: int
    per_page: int
    pages: int


class CustomerUpdate(BaseModel):
    phone: Optional[str] = None
    notes: Optional[str] = None


def _to_resp(c: svc.CustomerSummary) -> CustomerResponse:
    return CustomerResponse(
        id=c.id, telegram_id=c.telegram_id,
        username=c.username, first_name=c.first_name, last_name=c.last_name,
        phone=c.phone, notes=c.notes, is_active=c.is_active,
        total_orders=c.total_orders, total_spent=c.total_spent,
        first_order_at=c.first_order_at.isoformat() if c.first_order_at else None,
        last_order_at=c.last_order_at.isoformat() if c.last_order_at else None,
        created_at=c.created_at.isoformat(),
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/", response_model=CustomerListResponse)
async def list_customers(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=30, ge=1, le=200),
    search: Optional[str] = Query(default=None, max_length=100),
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.ORDERS_READ),
):
    items, total = await svc.list_customers(page, per_page, session, shop_id, search=search)
    return CustomerListResponse(
        items=[_to_resp(c) for c in items],
        total=total, page=page, per_page=per_page,
        pages=max(1, (total + per_page - 1) // per_page),
    )


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: int,
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.ORDERS_READ),
):
    return _to_resp(await svc.get_customer(customer_id, session, shop_id))


@router.patch("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: int,
    data: CustomerUpdate,
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.ORDERS_WRITE),
):
    return _to_resp(
        await svc.update_customer(customer_id, data.phone, data.notes, session, shop_id)
    )


@router.get("/{customer_id}/orders", response_model=OrderListResponse)
async def get_customer_orders(
    customer_id: int,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.ORDERS_READ),
):
    # Получаем telegram_id через customer
    c = await svc.get_customer(customer_id, session, shop_id)
    return await order_svc.list_orders(
        status=None, page=page, per_page=per_page,
        session=session, shop_id=shop_id,
        user_id=c.telegram_id,
    )
