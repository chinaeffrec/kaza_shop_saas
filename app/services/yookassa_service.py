"""
Бизнес-логика интеграции с ЮКасса.

Возможности:
  - Создание платёжной ссылки для заказа (с чеком 54-ФЗ если есть email/телефон)
  - Обработка входящего webhook (payment.succeeded → заказ в paid)
  - Инициирование возврата (при переходе заказа в returned)
  - Получение актуального статуса платежа

Учётные данные ЮКасса хранятся в ShopSettings (yookassa_shop_id, yookassa_secret_key).
Секрет маскируется при чтении через API.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations import yookassa_client as api
from app.integrations.yookassa_client import YooKassaError
from app.models.order import Order, OrderItem
from app.models.user import User
from app.services.settings_service import get_shop_settings

logger = logging.getLogger(__name__)

# Маппинг YooKassa event → человекочитаемый статус
_EVENT_LABELS = {
    "payment.succeeded": "Оплачен",
    "payment.canceled": "Отменён",
    "refund.succeeded": "Возврат выполнен",
}


# ── Auth helper ───────────────────────────────────────────────────────────────

async def _creds(shop_id: int, session: AsyncSession) -> tuple[str, str]:
    """Возвращает (yookassa_shop_id, secret_key). Бросает HTTPException если не настроено."""
    cfg = await get_shop_settings(session, shop_id)
    if not getattr(cfg, "yookassa_enabled", False):
        raise HTTPException(400, "ЮКасса не включена в настройках магазина")
    yk_id = getattr(cfg, "yookassa_shop_id", None)
    yk_key = getattr(cfg, "yookassa_secret_key", None)
    if not yk_id or not yk_key:
        raise HTTPException(400, "ЮКасса: не заданы shop_id или secret_key в настройках")
    return yk_id, yk_key


# ── Receipt builder (54-ФЗ) ───────────────────────────────────────────────────

def _build_receipt(order: Order, items: list[OrderItem], user: Optional[User]) -> Optional[dict]:
    """
    Формирует объект receipt для передачи в YooKassa.
    Возвращает None если нет контакта покупателя (обязательно по 54-ФЗ).
    """
    phone = getattr(user, "phone", None) if user else None
    # Если телефон не задан — чек не передаём (ЮКасса отклонит невалидный контакт)
    if not phone:
        return None

    receipt_items = []
    for it in items:
        receipt_items.append({
            "description": it.name[:128],
            "quantity": str(it.quantity),
            "amount": {
                "value": f"{it.price / 100:.2f}",  # цена в рублях
                "currency": "RUB",
            },
            "vat_code": 1,             # 1 = без НДС
            "payment_mode": "full_payment",
            "payment_subject": "commodity",
        })

    return {
        "customer": {"phone": phone},
        "items": receipt_items,
    }


# ── Public service methods ────────────────────────────────────────────────────

async def create_payment(
    order_id: int,
    shop_id: int,
    session: AsyncSession,
) -> dict:
    """
    Создаёт платёж в ЮКасса для заказа.
    Сохраняет payment_id и payment_status='pending' в Order.
    Возвращает {payment_id, confirmation_url, order_id}.
    """
    yk_id, yk_key = await _creds(shop_id, session)
    cfg = await get_shop_settings(session, shop_id)

    res = await session.execute(
        select(Order).where(Order.id == order_id, Order.shop_id == shop_id)
    )
    order = res.scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Заказ не найден")
    if order.payment_status == "succeeded":
        raise HTTPException(400, "Заказ уже оплачен")

    # Загружаем состав заказа для чека
    items_res = await session.execute(
        select(OrderItem).where(OrderItem.order_id == order_id)
    )
    items = items_res.scalars().all()

    # Пытаемся получить пользователя для чека
    user_res = await session.execute(
        select(User).where(User.telegram_id == order.user_id, User.shop_id == shop_id)
    )
    user = user_res.scalar_one_or_none()
    receipt = _build_receipt(order, items, user)

    return_url = (
        getattr(cfg, "yookassa_return_url", None)
        or f"https://t.me/"  # fallback — просто возврат в Telegram
    )

    total_rub = max(1, order.total // 100)   # YooKassa принимает рубли

    try:
        result = await api.create_payment(
            yookassa_shop_id=yk_id,
            secret_key=yk_key,
            amount_rub=total_rub,
            order_id=order_id,
            description=f"Заказ #{order_id} — {cfg.shop_name or 'Магазин'}",
            return_url=return_url,
            receipt=receipt,
            idempotency_key=f"order_{order_id}_v1",
        )
    except YooKassaError as exc:
        logger.error("YooKassa create_payment failed order_id=%s: %s", order_id, exc)
        raise HTTPException(502, f"Ошибка ЮКасса: {exc}") from exc

    order.payment_id = result["id"]
    order.payment_status = result.get("status", "pending")
    await session.commit()

    logger.info("YooKassa payment created: order_id=%s payment_id=%s", order_id, result["id"])
    return {
        "payment_id": result["id"],
        "confirmation_url": result["confirmation_url"],
        "order_id": order_id,
    }


async def get_payment_status(
    order_id: int,
    shop_id: int,
    session: AsyncSession,
) -> dict:
    """Актуальный статус платежа из ЮКасса."""
    res = await session.execute(
        select(Order).where(Order.id == order_id, Order.shop_id == shop_id)
    )
    order = res.scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Заказ не найден")
    if not order.payment_id:
        raise HTTPException(400, "Платёж не создан")

    yk_id, yk_key = await _creds(shop_id, session)
    try:
        info = await api.get_payment(order.payment_id, yk_id, yk_key)
    except YooKassaError as exc:
        raise HTTPException(502, str(exc)) from exc

    # Синхронизируем статус
    new_status = info.get("status", "")
    if new_status and order.payment_status != new_status:
        order.payment_status = new_status
        await session.commit()

    return {
        "order_id": order_id,
        "payment_id": order.payment_id,
        "payment_status": new_status,
        "paid": info.get("paid", False),
        "refundable": info.get("refundable", False),
    }


async def create_refund(
    order_id: int,
    shop_id: int,
    session: AsyncSession,
) -> dict:
    """
    Создаёт возврат по платежу.
    Обновляет order.refund_id и order.payment_status='refunded'.
    """
    res = await session.execute(
        select(Order).where(Order.id == order_id, Order.shop_id == shop_id)
    )
    order = res.scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Заказ не найден")
    if not order.payment_id:
        raise HTTPException(400, "Платёж не найден — возврат невозможен")
    if order.payment_status != "succeeded":
        raise HTTPException(400, "Возврат возможен только для оплаченного заказа")
    if order.refund_id:
        raise HTTPException(400, "Возврат уже выполнен")

    yk_id, yk_key = await _creds(shop_id, session)
    total_rub = max(1, order.total // 100)

    try:
        result = await api.create_refund(
            payment_id=order.payment_id,
            amount_rub=total_rub,
            yookassa_shop_id=yk_id,
            secret_key=yk_key,
            description=f"Возврат по заказу #{order_id}",
        )
    except YooKassaError as exc:
        logger.error("YooKassa refund failed order_id=%s: %s", order_id, exc)
        raise HTTPException(502, f"Ошибка возврата ЮКасса: {exc}") from exc

    order.refund_id = result["id"]
    order.payment_status = "refunded"
    await session.commit()

    logger.info("YooKassa refund created: order_id=%s refund_id=%s", order_id, result["id"])
    return {"order_id": order_id, "refund_id": result["id"], "status": result["status"]}


async def handle_webhook(payload: dict, session: AsyncSession) -> None:
    """
    Обрабатывает входящий webhook от ЮКасса.

    События:
      payment.succeeded  → order.status = paid, payment_status = succeeded
      payment.canceled   → payment_status = canceled
      refund.succeeded   → payment_status = refunded
    """
    event = payload.get("event", "")
    obj = payload.get("object", {})
    payment_id = obj.get("id", "")

    if not payment_id:
        return

    res = await session.execute(
        select(Order).where(Order.payment_id == payment_id)
    )
    order = res.scalar_one_or_none()
    if not order:
        logger.warning("YooKassa webhook: unknown payment_id=%s event=%s", payment_id, event)
        return

    if event == "payment.succeeded":
        order.payment_status = "succeeded"
        if order.status == "new":
            order.status = "paid"

    elif event == "payment.canceled":
        order.payment_status = "canceled"

    elif event == "refund.succeeded":
        order.payment_status = "refunded"

    else:
        return  # неизвестное событие

    await session.commit()
    logger.info("YooKassa webhook: order_id=%s event=%s", order.id, event)

    # Уведомление покупателю
    from app.models.order import ORDER_STATUSES
    from app.services.order_service import _get_bot_token_for_shop, _send_telegram

    bot_token = await _get_bot_token_for_shop(order.shop_id, session)
    label = _EVENT_LABELS.get(event, event)
    amount_rub = int(obj.get("amount", {}).get("value", "0").split(".")[0])

    lines = [f"💳 <b>Заказ #{order.id}</b>", f"Статус оплаты: <b>{label}</b>"]
    if amount_rub:
        lines.append(f"Сумма: {amount_rub:,} ₽".replace(",", " "))
    if event == "payment.succeeded":
        lines.append("✅ Оплата подтверждена. Мы начали обработку заказа!")
    elif event == "refund.succeeded":
        lines.append("↩️ Средства возвращены на вашу карту в течение 3–10 рабочих дней.")

    await _send_telegram(bot_token, order.user_id, "\n".join(lines))
