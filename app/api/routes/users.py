from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import BotAuthContext, require_bot_auth
from app.db.session import get_session
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
