"""
FastAPI-зависимости для platform-auth.

Три уровня доступа:
  require_platform_auth  — любой авторизованный пользователь платформы
  require_shop_owner     — авторизованный владелец с привязанным магазином
  require_super_admin    — суперадмин платформы
"""
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.services import platform_auth_service as svc

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class PlatformAuthContext:
    user_id: int
    email: str
    role: str           # "owner" | "super_admin"
    shop_id: Optional[int]
    is_super_admin: bool
    token_iat: int      # нужен для проверки инвалидации


async def require_platform_auth(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> PlatformAuthContext:
    """
    Валидирует Bearer-токен платформы.
    Проверяет подпись, TTL и инвалидацию при смене пароля.
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = svc.decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id_str = payload.get("sub")
    role = payload.get("role")
    shop_id = payload.get("shop_id")
    iat = payload.get("iat", 0)

    if not user_id_str or not role:
        raise HTTPException(status_code=401, detail="Malformed token")

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Malformed token")

    # Проверяем, не был ли токен инвалидирован сменой пароля
    if await svc.is_token_invalidated(user_id, iat):
        raise HTTPException(status_code=401, detail="Token invalidated: password changed")

    return PlatformAuthContext(
        user_id=user_id,
        email=payload.get("email", ""),
        role=role,
        shop_id=shop_id,
        is_super_admin=(role == "super_admin"),
        token_iat=iat,
    )


async def require_super_admin(
    ctx: PlatformAuthContext = Depends(require_platform_auth),
) -> PlatformAuthContext:
    if not ctx.is_super_admin:
        raise HTTPException(status_code=403, detail="Super admin access required")
    return ctx


async def require_shop_owner(
    ctx: PlatformAuthContext = Depends(require_platform_auth),
) -> PlatformAuthContext:
    """
    Разрешает доступ владельцу магазина или суперадмину (суперадмин может
    управлять любым магазином — shop_id передаётся через query param или путь).
    """
    if ctx.is_super_admin:
        return ctx
    if ctx.shop_id is None:
        raise HTTPException(
            status_code=403,
            detail="No shop associated with this account",
        )
    return ctx


def get_owner_shop_id(
    ctx: PlatformAuthContext = Depends(require_shop_owner),
) -> int:
    """
    Convenience dep for seller-panel admin routes.
    Returns the owner's shop_id from the platform JWT.
    Super-admins get 1 as a safe fallback (they normally use /platform/shops routes).
    """
    return ctx.shop_id if ctx.shop_id is not None else 1


def assert_shop_access(ctx: PlatformAuthContext, shop_id: int) -> None:
    """
    Проверяет доступ к конкретному магазину.
    Суперадмин имеет доступ к любому; владелец — только к своему.
    Бросает 403 при отсутствии доступа.
    """
    if ctx.is_super_admin:
        return
    if ctx.shop_id != shop_id:
        raise HTTPException(status_code=403, detail="Access denied to this shop")
