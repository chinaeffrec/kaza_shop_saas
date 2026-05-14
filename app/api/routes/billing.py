"""Биллинг — тарифы и подписки платформы."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    PlatformAuthContext,
    require_platform_auth,
    require_shop_id,
    require_super_admin,
)
from app.api.schemas.billing import (
    AssignPlanRequest,
    PlanResponse,
    SubscriptionResponse,
    UsageResponse,
)
from app.core.rbac import Perm
from app.db.session import get_session
from app.services import billing_service as svc

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/plans", response_model=list[PlanResponse], summary="Список тарифов (публичный)")
async def list_plans(session: AsyncSession = Depends(get_session)):
    """Публичный — используется в seller panel и на сайте."""
    plans = await svc.get_plans(session)
    return plans


@router.get(
    "/subscription",
    response_model=SubscriptionResponse,
    summary="Текущая подписка магазина",
)
async def get_subscription(
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.SETTINGS_READ),
):
    sub = await svc.get_or_create_sub(session, shop_id)
    await session.commit()  # persist auto-created free sub if needed
    return SubscriptionResponse(
        shop_id=sub.shop_id,
        plan=sub.plan,
        status=sub.status,
        started_at=sub.started_at,
        expires_at=sub.expires_at,
        trial_ends_at=sub.trial_ends_at,
    )


@router.get(
    "/usage",
    response_model=UsageResponse,
    summary="Использование ресурсов магазина",
)
async def get_usage(
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.SETTINGS_READ),
):
    return await svc.get_usage(session, shop_id)


@router.patch(
    "/subscription",
    response_model=SubscriptionResponse,
    summary="Назначить тариф магазину (только superadmin)",
)
async def assign_plan(
    data: AssignPlanRequest,
    session: AsyncSession = Depends(get_session),
    _: PlatformAuthContext = Depends(require_super_admin),
):
    sub = await svc.assign_plan(data, session)
    await session.commit()
    return SubscriptionResponse(
        shop_id=sub.shop_id,
        plan=sub.plan,
        status=sub.status,
        started_at=sub.started_at,
        expires_at=sub.expires_at,
        trial_ends_at=sub.trial_ends_at,
    )
