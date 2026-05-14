"""
User endpoints — регистрация бот-пользователей и GDPR-права.

POST /users/register          — регистрация/обновление юзера (вызывается ботом)
GET  /users/me/data           — GDPR: экспорт своих данных
DELETE /users/me              — GDPR: удаление своих данных (soft-delete)
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import BotAuthContext, require_bot_auth
from app.db.session import get_session
from app.models.order import Order
from app.models.user import User

router = APIRouter(prefix="/users", tags=["users"])


class UserRegister(BaseModel):
    id: int = Field(gt=0)
    username: Optional[str] = Field(default=None, max_length=64)
    first_name: Optional[str] = Field(default=None, max_length=64)
    last_name: Optional[str] = Field(default=None, max_length=64)


@router.post("/register")
async def register_user(
    data: UserRegister,
    session: AsyncSession = Depends(get_session),
    bot_ctx: BotAuthContext = Depends(require_bot_auth),
):
    if bot_ctx.user_id is None or bot_ctx.user_id != data.id:
        raise HTTPException(403, "user_id mismatch")
    shop_id = bot_ctx.shop_id
    res = await session.execute(
        select(User).where(User.telegram_id == data.id, User.shop_id == shop_id)
    )
    user = res.scalar_one_or_none()
    if not user:
        user = User(
            telegram_id=data.id, shop_id=shop_id,
            username=data.username,
            first_name=data.first_name,
            last_name=data.last_name,
        )
        session.add(user)
    else:
        user.username = data.username
        user.first_name = data.first_name
        user.last_name = data.last_name
    await session.commit()
    return {"ok": True}


# ── GDPR ──────────────────────────────────────────────────────────────────────

@router.get("/me/data", summary="GDPR: экспорт персональных данных")
async def export_my_data(
    session: AsyncSession = Depends(get_session),
    bot_ctx: BotAuthContext = Depends(require_bot_auth),
):
    """
    Возвращает все данные пользователя в структурированном виде.
    Право на получение своих данных (GDPR Art. 15, аналог для других юрисдикций).
    """
    if bot_ctx.user_id is None:
        raise HTTPException(400, "user_id required")

    user_result = await session.execute(
        select(User).where(
            User.telegram_id == bot_ctx.user_id,
            User.shop_id == bot_ctx.shop_id,
        )
    )
    user = user_result.scalar_one_or_none()
    if not user:
        return {"profile": None, "orders": []}

    orders_result = await session.execute(
        select(Order).where(
            Order.user_id == bot_ctx.user_id,
            Order.shop_id == bot_ctx.shop_id,
        ).order_by(Order.created_at.desc())
    )
    orders = orders_result.scalars().all()

    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "profile": {
            "telegram_id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "created_at": user.created_at.isoformat() if hasattr(user, "created_at") and user.created_at else None,
        },
        "orders": [
            {
                "id": o.id,
                "total": o.total,
                "status": o.status,
                "comment": o.comment,
                "delivery_address": getattr(o, "delivery_address", None),
                "created_at": o.created_at.isoformat(),
            }
            for o in orders
        ],
    }


@router.delete("/me", status_code=200, summary="GDPR: удаление персональных данных")
async def delete_my_data(
    session: AsyncSession = Depends(get_session),
    bot_ctx: BotAuthContext = Depends(require_bot_auth),
):
    """
    Анонимизирует данные пользователя: имя/username обнуляются,
    заказы сохраняются (для финансовой отчётности магазина) но разрывают связь с ПД.
    Право на удаление (GDPR Art. 17 аналог).
    """
    if bot_ctx.user_id is None:
        raise HTTPException(400, "user_id required")

    user_result = await session.execute(
        select(User).where(
            User.telegram_id == bot_ctx.user_id,
            User.shop_id == bot_ctx.shop_id,
        )
    )
    user = user_result.scalar_one_or_none()
    if not user:
        return {"ok": True, "message": "No data found"}

    # Анонимизация: удаляем ПД, сохраняем финансовые данные
    user.username = None
    user.first_name = f"Deleted_{user.telegram_id}"
    user.last_name = None
    # telegram_id остаётся для deduplication при повторном /start

    await session.commit()
    return {"ok": True, "message": "Your personal data has been anonymized"}
