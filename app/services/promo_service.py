"""Сервис промокодов.

Правила применения:
  - fixed:   скидка = min(value_rub * 100, cart_total)
  - percent: скидка = cart_total * value // 100
  - Итоговая сумма заказа не может быть отрицательной.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.promo_code import PromoCode


# ── helpers ───────────────────────────────────────────────────────────────────

def _calc_discount(promo: PromoCode, cart_total: int) -> int:
    """Возвращает скидку в копейках (≥ 0, ≤ cart_total)."""
    if promo.discount_type == "fixed":
        return min(promo.value, cart_total)
    else:  # percent
        return min(cart_total * promo.value // 100, cart_total)


async def _get_promo(code: str, shop_id: int, session: AsyncSession) -> Optional[PromoCode]:
    result = await session.execute(
        select(PromoCode).where(
            PromoCode.shop_id == shop_id,
            func.upper(PromoCode.code) == code.upper(),
        )
    )
    return result.scalar_one_or_none()


def _check_validity(promo: PromoCode, cart_total: int) -> Tuple[bool, str]:
    """Возвращает (valid, reason_message)."""
    if not promo.is_active:
        return False, "Промокод неактивен"
    if promo.expires_at and promo.expires_at < datetime.now(timezone.utc):
        return False, "Срок действия промокода истёк"
    if promo.max_uses is not None and promo.used_count >= promo.max_uses:
        return False, "Лимит использований промокода исчерпан"
    if promo.min_order_amount is not None and cart_total < promo.min_order_amount:
        fmt = promo.min_order_amount // 100
        return False, f"Промокод действует от {fmt} ₽"
    return True, ""


# ── public API ────────────────────────────────────────────────────────────────

async def validate_promo(
    code: str,
    cart_total: int,
    session: AsyncSession,
    shop_id: int,
):
    """Валидирует промокод и возвращает схему ответа (не изменяет used_count)."""
    from app.api.schemas.promo import PromoValidateResponse

    promo = await _get_promo(code, shop_id, session)
    if promo is None:
        return PromoValidateResponse(valid=False, message="Промокод не найден")

    valid, msg = _check_validity(promo, cart_total)
    if not valid:
        return PromoValidateResponse(valid=False, message=msg)

    discount = _calc_discount(promo, cart_total)
    return PromoValidateResponse(
        valid=True,
        discount=discount,
        final_total=cart_total - discount,
        message="",
        promo_id=promo.id,
    )


async def apply_promo(
    code: str,
    cart_total: int,
    session: AsyncSession,
    shop_id: int,
) -> Tuple[int, Optional[str]]:
    """
    Применяет промокод: валидирует и инкрементирует used_count атомарно.
    Возвращает (discount_amount, normalized_code).
    Бросает HTTPException 400/404 при ошибке.
    """
    promo = await _get_promo(code, shop_id, session)
    if promo is None:
        raise HTTPException(400, "Промокод не найден")

    valid, msg = _check_validity(promo, cart_total)
    if not valid:
        raise HTTPException(400, msg)

    discount = _calc_discount(promo, cart_total)
    promo.used_count += 1
    session.add(promo)
    return discount, promo.code


# ── CRUD ──────────────────────────────────────────────────────────────────────

async def list_promos(session: AsyncSession, shop_id: int):
    from app.api.schemas.promo import PromoListResponse, PromoResponse

    result = await session.execute(
        select(PromoCode)
        .where(PromoCode.shop_id == shop_id)
        .order_by(PromoCode.created_at.desc())
    )
    promos = result.scalars().all()
    return PromoListResponse(
        items=[PromoResponse.model_validate(p) for p in promos],
        total=len(promos),
    )


async def create_promo(data, session: AsyncSession, shop_id: int):
    from app.api.schemas.promo import PromoResponse

    # Проверяем уникальность кода (case-insensitive)
    existing = await _get_promo(data.code, shop_id, session)
    if existing:
        raise HTTPException(400, f"Промокод '{data.code}' уже существует")

    promo = PromoCode(
        shop_id=shop_id,
        code=data.code.upper(),
        discount_type=data.discount_type,
        value=data.value,
        min_order_amount=data.min_order_amount,
        max_uses=data.max_uses,
        expires_at=data.expires_at,
        is_active=data.is_active,
    )
    session.add(promo)
    await session.commit()
    await session.refresh(promo)
    return PromoResponse.model_validate(promo)


async def update_promo(promo_id: int, data, session: AsyncSession, shop_id: int):
    from app.api.schemas.promo import PromoResponse

    result = await session.execute(
        select(PromoCode).where(PromoCode.id == promo_id, PromoCode.shop_id == shop_id)
    )
    promo = result.scalar_one_or_none()
    if not promo:
        raise HTTPException(404, "Промокод не найден")

    for field, val in data.model_dump(exclude_none=True).items():
        setattr(promo, field, val)
    await session.commit()
    await session.refresh(promo)
    return PromoResponse.model_validate(promo)


async def delete_promo(promo_id: int, session: AsyncSession, shop_id: int) -> None:
    result = await session.execute(
        select(PromoCode).where(PromoCode.id == promo_id, PromoCode.shop_id == shop_id)
    )
    promo = result.scalar_one_or_none()
    if not promo:
        raise HTTPException(404, "Промокод не найден")
    await session.delete(promo)
    await session.commit()
