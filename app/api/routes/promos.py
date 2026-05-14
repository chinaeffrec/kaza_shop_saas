"""HTTP-слой промокодов."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_shop_id
from app.api.schemas.promo import (
    PromoCreate,
    PromoListResponse,
    PromoResponse,
    PromoUpdate,
    PromoValidateRequest,
    PromoValidateResponse,
)
from app.core.rbac import Perm
from app.db.session import get_session
from app.services import promo_service as svc

router = APIRouter(prefix="/promos", tags=["promos"])


@router.get("/", response_model=PromoListResponse)
async def list_promos(
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.PROMOS_READ),
):
    return await svc.list_promos(session, shop_id)


@router.post("/", response_model=PromoResponse, status_code=201)
async def create_promo(
    data: PromoCreate,
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.PROMOS_WRITE),
):
    return await svc.create_promo(data, session, shop_id)


@router.patch("/{promo_id}", response_model=PromoResponse)
async def update_promo(
    promo_id: int,
    data: PromoUpdate,
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.PROMOS_WRITE),
):
    return await svc.update_promo(promo_id, data, session, shop_id)


@router.delete("/{promo_id}", status_code=204)
async def delete_promo(
    promo_id: int,
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.PROMOS_WRITE),
):
    await svc.delete_promo(promo_id, session, shop_id)


@router.post("/validate", response_model=PromoValidateResponse)
async def validate_promo(
    data: PromoValidateRequest,
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.PROMOS_READ),
):
    """Валидация промокода без его применения (для превью в корзине)."""
    return await svc.validate_promo(data.code, data.cart_total, session, shop_id)


# ── Bot endpoint (no RBAC, uses X-Bot-Token) ─────────────────────────────────

from app.api.deps import BotAuthContext, require_bot_auth  # noqa: E402


@router.post("/bot/validate", response_model=PromoValidateResponse)
async def bot_validate_promo(
    data: PromoValidateRequest,
    session: AsyncSession = Depends(get_session),
    bot_ctx: BotAuthContext = Depends(require_bot_auth),
):
    """Валидация промокода из бота (без JWT, по X-Bot-Token)."""
    return await svc.validate_promo(data.code, data.cart_total, session, bot_ctx.shop_id)
