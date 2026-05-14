"""
Audit log endpoints.

GET /platform/audit-logs                — все события платформы [super_admin]
GET /platform/shops/{id}/audit-logs     — события конкретного магазина [super_admin | owner]
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import PlatformAuthContext, assert_shop_access, require_platform_auth, require_super_admin
from app.api.schemas.platform_auth import AuditLogListResponse, AuditLogResponse
from app.db.session import get_session

router = APIRouter(prefix="/platform", tags=["platform-audit"])


@router.get("/audit-logs", response_model=AuditLogListResponse)
async def list_platform_audit_logs(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    action: Optional[str] = Query(default=None, description="Фильтр по action, например shop.status_changed"),
    actor_id: Optional[int] = Query(default=None),
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    session: AsyncSession = Depends(get_session),
    _: PlatformAuthContext = Depends(require_super_admin),
):
    return await _query_audit_logs(
        session, page, per_page,
        shop_id=None, action=action, actor_id=actor_id,
        date_from=date_from, date_to=date_to,
    )


@router.get("/shops/{shop_id}/audit-logs", response_model=AuditLogListResponse)
async def list_shop_audit_logs(
    shop_id: int,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    action: Optional[str] = Query(default=None),
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    session: AsyncSession = Depends(get_session),
    ctx: PlatformAuthContext = Depends(require_platform_auth),
):
    assert_shop_access(ctx, shop_id)
    return await _query_audit_logs(
        session, page, per_page,
        shop_id=shop_id, action=action, actor_id=None,
        date_from=date_from, date_to=date_to,
    )


async def _query_audit_logs(
    session: AsyncSession,
    page: int,
    per_page: int,
    shop_id: Optional[int] = None,
    action: Optional[str] = None,
    actor_id: Optional[int] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> AuditLogListResponse:
    """Общая логика выборки audit_logs с фильтрами."""

    # Строим WHERE условия через text() параметры
    conditions = []
    params: dict = {}

    if shop_id is not None:
        conditions.append("shop_id = :shop_id")
        params["shop_id"] = shop_id

    if action:
        # Частичное совпадение для удобства фильтрации (e.g. "shop." найдёт все shop.* события)
        conditions.append("action ILIKE :action")
        params["action"] = f"{action}%"

    if actor_id is not None:
        conditions.append("actor_id = :actor_id")
        params["actor_id"] = actor_id

    if date_from:
        conditions.append("created_at >= :date_from")
        params["date_from"] = date_from

    if date_to:
        conditions.append("created_at <= :date_to")
        params["date_to"] = date_to

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    # Общее количество
    count_q = text(f"SELECT COUNT(*) FROM audit_logs {where_clause}")
    total = (await session.execute(count_q, params)).scalar() or 0

    # Данные с пагинацией
    offset = (page - 1) * per_page
    data_q = text(f"""
        SELECT id, actor_id, actor_email, actor_role, shop_id, action,
               entity_type, entity_id, before_data, after_data, extra,
               ip_address, created_at
        FROM audit_logs
        {where_clause}
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :offset
    """)
    rows = (await session.execute(data_q, {**params, "limit": per_page, "offset": offset})).fetchall()

    items = [
        AuditLogResponse(
            id=r.id,
            actor_id=r.actor_id,
            actor_email=r.actor_email,
            actor_role=r.actor_role,
            shop_id=r.shop_id,
            action=r.action,
            entity_type=r.entity_type,
            entity_id=r.entity_id,
            before_data=r.before_data,
            after_data=r.after_data,
            extra=r.extra,
            ip_address=r.ip_address,
            created_at=r.created_at,
        )
        for r in rows
    ]

    return AuditLogListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
    )
