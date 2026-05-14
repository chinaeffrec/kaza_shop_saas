"""HTTP-слой интеграции с ЮКасса."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import BotAuthContext, require_bot_auth, require_shop_id
from app.api.schemas.yookassa import (
    BotPaymentResponse,
    PaymentCreateResponse,
    PaymentStatusResponse,
    RefundResponse,
)
from app.core.config import get_settings
from app.core.rbac import Perm
from app.core.security import verify_yookassa_webhook_ip
from app.db.session import get_session
from app.services import yookassa_service as svc


def _real_client_ip(request: Request) -> str:
    """Returns the real client IP, respecting X-Forwarded-For behind a trusted proxy."""
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        # X-Forwarded-For: <client>, <proxy1>, <proxy2>
        # Nginx appends the direct peer; the leftmost entry is the original client.
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

router = APIRouter(prefix="/yookassa", tags=["yookassa"])


# ── Seller-panel endpoints (RBAC) ─────────────────────────────────────────────

@router.post("/payments/{order_id}", response_model=PaymentCreateResponse, status_code=201)
async def create_payment(
    order_id: int,
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.ORDERS_WRITE),
):
    """Создаёт платёж в ЮКасса для заказа. Возвращает ссылку на оплату."""
    return await svc.create_payment(order_id, shop_id, session)


@router.get("/payments/{order_id}", response_model=PaymentStatusResponse)
async def get_payment_status(
    order_id: int,
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.ORDERS_READ),
):
    """Актуальный статус платежа из ЮКасса."""
    return await svc.get_payment_status(order_id, shop_id, session)


@router.post("/payments/{order_id}/refund", response_model=RefundResponse, status_code=201)
async def create_refund(
    order_id: int,
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.ORDERS_WRITE),
):
    """Инициирует возврат по оплаченному заказу."""
    return await svc.create_refund(order_id, shop_id, session)


# ── Bot endpoints (X-Bot-Token) ───────────────────────────────────────────────

@router.post("/bot/payments/{order_id}", response_model=BotPaymentResponse, status_code=201)
async def bot_create_payment(
    order_id: int,
    session: AsyncSession = Depends(get_session),
    bot_ctx: BotAuthContext = Depends(require_bot_auth),
):
    """
    Создаёт или возвращает существующий платёж для заказа.
    Используется ботом для показа кнопки «💳 Оплатить».
    """
    result = await svc.create_payment(order_id, bot_ctx.shop_id, session)
    # get fresh status after creation
    status_info = await svc.get_payment_status(order_id, bot_ctx.shop_id, session)
    return BotPaymentResponse(
        payment_id=result["payment_id"],
        confirmation_url=result["confirmation_url"],
        order_id=order_id,
        payment_status=status_info["payment_status"],
    )


@router.get("/bot/payments/{order_id}", response_model=PaymentStatusResponse)
async def bot_get_payment_status(
    order_id: int,
    session: AsyncSession = Depends(get_session),
    bot_ctx: BotAuthContext = Depends(require_bot_auth),
):
    """Статус платежа для бота (кнопка «🔄 Проверить оплату»)."""
    return await svc.get_payment_status(order_id, bot_ctx.shop_id, session)


# ── Webhook (IP-restricted — YooKassa published ranges only) ──────────────────

@router.post("/webhook")
async def yookassa_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """
    Входящий webhook от ЮКасса.

    В production принимается только с IP-адресов из официального списка ЮKassa.
    В development проверка пропускается (ENV != "production").
    Идентификация платежа — по payment_id в базе данных (дополнительный барьер).
    """
    cfg = get_settings()
    if cfg.is_production:
        verify_yookassa_webhook_ip(_real_client_ip(request))

    try:
        payload = await request.json()
    except Exception:
        return {"status": "ignored"}

    await svc.handle_webhook(payload, session)
    return {"status": "ok"}
