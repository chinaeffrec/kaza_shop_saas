"""Бизнес-логика статистики и экспорта."""
from datetime import datetime, timezone
from io import BytesIO
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from openpyxl import Workbook
from openpyxl.styles import Border, Font, PatternFill, Side
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.stats import (
    DashboardResponse, ProductStatItem, ProductStatsSummary, ProductStatsResponse,
    RecentOrder, StatusStat, StatusStatItem, TopProduct,
)
from app.core.config import get_settings
from app.models.order import ORDER_STATUSES, Order, OrderItem
from app.models.product import Product
from app.models.product_stats import ProductStats
from app.models.user import User


def _fmt_price(price: int | float) -> str:
    return f"{int(price):,} ₽".replace(",", " ")


def _fmt_dt(dt: datetime | None) -> str:
    """Форматирует datetime из UTC в локальную временную зону."""
    if not dt:
        return ""
    tz = ZoneInfo(get_settings().timezone)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz).strftime("%d.%m.%Y %H:%M")


async def get_dashboard(
    date_from: Optional[str], date_to: Optional[str],
    session: AsyncSession, shop_id: int = 1,
) -> DashboardResponse:
    q = select(Order).where(Order.shop_id == shop_id).order_by(Order.created_at.desc())
    if date_from:
        q = q.where(Order.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        q = q.where(Order.created_at <= datetime.fromisoformat(date_to + "T23:59:59"))

    all_orders = (await session.execute(q)).scalars().all()
    REVENUE_STATUSES = {"paid", "confirmed", "assembled", "shipped", "delivered"}
    billable = [o for o in all_orders if o.status in REVENUE_STATUSES]
    total_revenue = sum(o.total for o in billable)
    avg_val = int(total_revenue / len(billable)) if billable else 0

    by_status: dict[str, int] = {}
    for o in all_orders:
        by_status[o.status] = by_status.get(o.status, 0) + 1

    user_ids = {o.user_id for o in all_orders}
    user_map: dict = {}
    if user_ids:
        users = (await session.execute(
            select(User).where(User.telegram_id.in_(user_ids), User.shop_id == shop_id)
        )).scalars().all()
        user_map = {u.telegram_id: u for u in users}

    recent = []
    for o in all_orders[:10]:
        u = user_map.get(o.user_id)
        name = f"ID:{o.user_id}"
        if u:
            name = f"{u.first_name or ''} {u.last_name or ''}".strip() or u.username or name
        recent.append(RecentOrder(
            id=o.id, user_id=o.user_id, user_name=name,
            status=o.status, status_label=ORDER_STATUSES.get(o.status, o.status),
            total=o.total, created_at=o.created_at.isoformat(),
        ))

    top_res = (await session.execute(
        select(ProductStats, Product)
        .outerjoin(Product, ProductStats.product_id == Product.id)
        .where(Product.shop_id == shop_id)
        .order_by(ProductStats.ordered.desc()).limit(10)
    )).all()
    top = [TopProduct(
        product_id=ps.product_id,
        name=p.name if p else f"ID:{ps.product_id}",
        ordered=ps.ordered or 0,
    ) for ps, p in top_res]

    status_order = list(ORDER_STATUSES.keys())
    sorted_statuses = [s for s in status_order if s in by_status] + \
                      [s for s in by_status if s not in status_order]

    return DashboardResponse(
        total_revenue=total_revenue, total_orders=len(all_orders),
        billable_orders=len(billable), average_order_value=avg_val,
        by_status={s: StatusStat(count=by_status[s], label=ORDER_STATUSES.get(s, s))
                   for s in sorted_statuses},
        orders_by_status=[
            StatusStatItem(status=s, count=by_status[s], label=ORDER_STATUSES.get(s, s))
            for s in sorted_statuses
        ],
        recent_orders=recent, top_products=top,
    )


async def export_orders_xlsx(
    date_from: Optional[str], date_to: Optional[str],
    status: Optional[str], session: AsyncSession, shop_id: int = 1,
) -> BytesIO:
    q = select(Order).where(Order.shop_id == shop_id).order_by(Order.created_at.desc())
    if date_from:
        q = q.where(Order.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        q = q.where(Order.created_at <= datetime.fromisoformat(date_to + "T23:59:59"))
    if status:
        q = q.where(Order.status == status)

    orders = (await session.execute(q)).scalars().all()
    user_ids = {o.user_id for o in orders}
    user_map: dict = {}
    if user_ids:
        users = (await session.execute(
            select(User).where(User.telegram_id.in_(user_ids), User.shop_id == shop_id)
        )).scalars().all()
        user_map = {u.telegram_id: u for u in users}

    wb = Workbook()
    ws = wb.active
    ws.title = "Заказы"
    hfill = PatternFill("solid", fgColor="4472C4")
    hfont = Font(bold=True, color="FFFFFF")
    thin = Side(style="thin")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    headers = ["ID", "Покупатель", "Контакт", "Сумма", "Статус", "Адрес", "Комментарий", "Дата"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = hfill; cell.font = hfont; cell.border = border

    for ri, order in enumerate(orders, 2):
        u = user_map.get(order.user_id)
        uname = f"ID:{order.user_id}"
        ucontact = ""
        if u:
            uname = f"{u.first_name or ''} {u.last_name or ''}".strip() or u.username or uname
            ucontact = f"@{u.username}" if u.username else ""
        row_data = [
            order.id, uname, ucontact, order.total,
            ORDER_STATUSES.get(order.status, order.status),
            getattr(order, "delivery_address", "") or "",
            order.comment or "",
            _fmt_dt(order.created_at),
        ]
        for col, val in enumerate(row_data, 1):
            ws.cell(row=ri, column=col, value=val).border = border

    out = BytesIO()
    wb.save(out)
    out.seek(0)
    return out


def _build_period_filter(q, date_from: Optional[str], date_to: Optional[str]):
    if date_from:
        q = q.where(Order.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        q = q.where(Order.created_at <= datetime.fromisoformat(date_to + "T23:59:59"))
    return q


async def get_product_stats(
    date_from: Optional[str], date_to: Optional[str],
    session: AsyncSession, shop_id: int = 1,
) -> ProductStatsResponse:
    ps_res = await session.execute(
        select(ProductStats, Product)
        .outerjoin(Product, ProductStats.product_id == Product.id)
        .where(Product.shop_id == shop_id)
        .order_by(ProductStats.ordered.desc())
    )
    rows = ps_res.all()

    oi_q = (
        select(
            OrderItem.product_id,
            func.sum(OrderItem.quantity).label("qty"),
            func.sum(OrderItem.quantity * OrderItem.price).label("revenue"),
        )
        .join(Order, OrderItem.order_id == Order.id)
        .where(Order.shop_id == shop_id)
        .where(Order.status.not_in(["cancelled", "returned"]))
        .group_by(OrderItem.product_id)
    )
    oi_q = _build_period_filter(oi_q, date_from, date_to)
    period_map: dict[int, tuple[int, int]] = {
        row.product_id: (int(row.qty), int(row.revenue))
        for row in (await session.execute(oi_q)).all()
    }

    order_count_q = (
        select(func.count(func.distinct(OrderItem.order_id)))
        .join(Order, OrderItem.order_id == Order.id)
        .where(Order.shop_id == shop_id)
        .where(Order.status.not_in(["cancelled", "returned"]))
    )
    order_count_q = _build_period_filter(order_count_q, date_from, date_to)
    order_count = (await session.execute(order_count_q)).scalar() or 0

    items: list[ProductStatItem] = []
    total_sold_qty = total_sold_sum = total_returned = 0

    for ps, product in rows:
        qty, revenue = period_map.get(ps.product_id, (0, 0))
        total_sold_qty += qty
        total_sold_sum += revenue
        total_returned += ps.returned or 0
        items.append(ProductStatItem(
            product_id=ps.product_id,
            name=product.name if product else f"ID:{ps.product_id}",
            added_to_cart=ps.added_to_cart or 0,
            ordered=ps.ordered or 0,
            returned=ps.returned or 0,
            period_sold_qty=qty,
            period_sold_sum=revenue,
        ))

    avg_price = int(total_sold_sum / total_sold_qty) if total_sold_qty else 0

    summary = ProductStatsSummary(
        total_sold_qty=total_sold_qty,
        total_sold_sum=total_sold_sum,
        avg_items_per_order=round(total_sold_qty / order_count, 1) if order_count else 0,
        avg_price=avg_price,
        total_returned=total_returned,
    )
    return ProductStatsResponse(items=items, summary=summary)


async def export_product_stats_xlsx(
    date_from: Optional[str], date_to: Optional[str],
    session: AsyncSession, shop_id: int = 1,
) -> BytesIO:
    result = await get_product_stats(date_from, date_to, session, shop_id)

    wb = Workbook()
    ws = wb.active
    ws.title = "Статистика товаров"
    hfill = PatternFill("solid", fgColor="4472C4")
    hfont = Font(bold=True, color="FFFFFF")
    thin = Side(style="thin")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    headers = ["Товар", "В корзину", "Заказано (всего)", "Возвраты", "Продано (период)", "Выручка (период)"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = hfill; cell.font = hfont; cell.border = border

    for ri, item in enumerate(result.items, 2):
        for col, val in enumerate([
            item.name, item.added_to_cart, item.ordered,
            item.returned, item.period_sold_qty, item.period_sold_sum,
        ], 1):
            ws.cell(row=ri, column=col, value=val).border = border

    out = BytesIO()
    wb.save(out)
    out.seek(0)
    return out


async def track_return(product_id: int, session: AsyncSession) -> dict:
    res = await session.execute(
        select(ProductStats).where(ProductStats.product_id == product_id)
    )
    ps = res.scalar_one_or_none()
    if not ps:
        raise HTTPException(404, "Product stats not found")
    ps.returned = (ps.returned or 0) + 1
    await session.commit()
    return {"ok": True, "product_id": product_id, "returned": ps.returned}
