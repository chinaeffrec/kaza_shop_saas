"""HTTP-слой СДЭК-интеграции."""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_shop_id
from app.api.schemas.cdek import (
    CdekCity, CdekWebhookPayload,
    CdekStatusResponse, PvzListResponse,
    ShipmentRequest, ShipmentResponse,
    TariffRequest, TariffResponse,
)
from app.core.rbac import Perm
from app.db.session import get_session
from app.services import cdek_service as svc

router = APIRouter(prefix="/cdek", tags=["cdek"])


@router.get("/cities", response_model=List[CdekCity])
async def search_cities(
    q: str = Query(..., min_length=2, description="Часть названия города"),
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.SETTINGS_READ),
):
    """Поиск города СДЭК по названию для настройки/заказа."""
    return await svc.search_cities(q, shop_id, session)


@router.get("/pvz", response_model=PvzListResponse)
async def get_pvz(
    city_code: int = Query(..., description="Код города СДЭК"),
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.ORDERS_READ),
):
    """Список пунктов выдачи в городе."""
    return await svc.get_pvz_list(city_code, shop_id, session)


@router.post("/calculate", response_model=TariffResponse)
async def calculate(
    data: TariffRequest,
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.ORDERS_READ),
):
    """Расчёт стоимости доставки до ПВЗ."""
    result = await svc.calculate_tariff(
        data.to_city_code, data.weight_grams, shop_id, session
    )
    return result


@router.post("/orders/{order_id}/ship", response_model=ShipmentResponse, status_code=201)
async def create_shipment(
    order_id: int,
    data: ShipmentRequest,
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.ORDERS_WRITE),
):
    """Создаёт заявку СДЭК для указанного заказа."""
    result = await svc.create_shipment(
        order_id=order_id,
        pvz_code=data.pvz_code,
        receiver_name=data.receiver_name,
        receiver_phone=data.receiver_phone,
        weight_grams=data.weight_grams,
        comment=data.comment,
        shop_id=shop_id,
        session=session,
    )
    return result


@router.get("/orders/{order_id}/status", response_model=CdekStatusResponse)
async def get_status(
    order_id: int,
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.ORDERS_READ),
):
    """Актуальный статус отправления СДЭК."""
    return await svc.get_shipment_status(order_id, shop_id, session)


# ── Bot endpoint (no RBAC) ────────────────────────────────────────────────────

from app.api.deps import BotAuthContext, require_bot_auth  # noqa: E402


@router.get("/bot/pvz", response_model=PvzListResponse)
async def bot_get_pvz(
    city_code: int = Query(...),
    session: AsyncSession = Depends(get_session),
    bot_ctx: BotAuthContext = Depends(require_bot_auth),
):
    """ПВЗ-список для бота (по X-Bot-Token)."""
    return await svc.get_pvz_list(city_code, bot_ctx.shop_id, session)


@router.get("/bot/cities")
async def bot_search_cities(
    q: str = Query(..., min_length=2),
    session: AsyncSession = Depends(get_session),
    bot_ctx: BotAuthContext = Depends(require_bot_auth),
):
    """Поиск городов для бота."""
    return await svc.search_cities(q, bot_ctx.shop_id, session)


@router.post("/bot/calculate", response_model=TariffResponse)
async def bot_calculate(
    data: TariffRequest,
    session: AsyncSession = Depends(get_session),
    bot_ctx: BotAuthContext = Depends(require_bot_auth),
):
    """Расчёт стоимости доставки для бота."""
    return await svc.calculate_tariff(
        data.to_city_code, data.weight_grams, bot_ctx.shop_id, session
    )


# ── Webhook ───────────────────────────────────────────────────────────────────

@router.post("/webhook")
async def cdek_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """
    Входящий webhook от СДЭК (ORDER_STATUS).
    СДЭК не использует заголовки авторизации — идентификация по uuid заявки.
    """
    try:
        payload = await request.json()
    except Exception:
        return {"status": "ignored"}

    await svc.handle_webhook(payload, session)
    return {"status": "ok"}
