"""Роуты статистики - только HTTP-слой."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_shop_id
from app.api.schemas.stats import AnalyticsResponse, DashboardResponse, ProductStatsResponse
from app.core.rate_limit import rate_limit
from app.core.rbac import Perm
from app.db.session import get_session
from app.services import stats_service as svc

router = APIRouter(prefix="/stats", tags=["stats"])

# A3: экспорт — тяжёлая операция, 10 запросов в минуту с одного IP
_export_limit = rate_limit("stats_export", max_requests=10, window=60)

_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx_response(output, filename: str) -> StreamingResponse:
    return StreamingResponse(
        output, media_type=_XLSX,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.STATS_READ),
):
    return await svc.get_dashboard(date_from, date_to, session, shop_id)


@router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    period: str = Query(default="day", pattern="^(day|week)$"),
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.STATS_READ),
):
    """
    Динамика выручки по дням/неделям + когортный анализ покупателей.

    - `period=day` — точки по дням (до 90 дней)
    - `period=week` — точки по неделям (до 1 года)
    """
    return await svc.get_analytics(date_from, date_to, period, session, shop_id)


@router.get("/export")
async def export_orders(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.STATS_EXPORT),
    _rl: None = _export_limit,
):
    output = await svc.export_orders_xlsx(date_from, date_to, status, session, shop_id)
    return _xlsx_response(output, f"orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")


@router.get("/customers/export")
async def export_customers(
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.STATS_EXPORT),
    _rl: None = _export_limit,
):
    """Экспорт списка покупателей с LTV-данными в Excel."""
    output = await svc.export_customers_xlsx(session, shop_id)
    return _xlsx_response(output, f"customers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")


@router.get("/products", response_model=ProductStatsResponse)
async def get_product_stats(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.STATS_READ),
):
    return await svc.get_product_stats(date_from, date_to, session, shop_id)


@router.get("/products/export")
async def export_product_stats(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.STATS_EXPORT),
    _rl: None = _export_limit,
):
    output = await svc.export_product_stats_xlsx(date_from, date_to, session, shop_id)
    return _xlsx_response(output, f"stats_products_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")


@router.post("/products/{product_id}/return")
async def track_return(
    product_id: int,
    session: AsyncSession = Depends(get_session),
):
    return await svc.track_return(product_id, session)
