"""
FastAPI-зависимости.

Platform auth (три уровня):
  require_platform_auth      — любой авторизованный пользователь платформы
  require_shop_owner         — авторизованный владелец с привязанным магазином
  require_super_admin        — суперадмин платформы
  require_permission(perm)   — RBAC: проверяет конкретное право, возвращает ctx

Bot auth:
  require_bot_auth           — внутренние эндпоинты бота; проверяет токен +
                               активность магазина в БД
"""
from dataclasses import dataclass, field
from typing import Callable, Optional

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import get_permissions
from app.db.session import get_session
from app.services import platform_auth_service as svc

_bearer = HTTPBearer(auto_error=False)


# ── Platform auth ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PlatformAuthContext:
    user_id: int
    email: str
    role: str                        # "owner" | "manager" | "support" | "super_admin"
    shop_id: Optional[int]
    is_super_admin: bool
    permissions: frozenset           # производные от role через ROLE_PERMISSIONS
    token_iat: int


async def require_platform_auth(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> PlatformAuthContext:
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

    if await svc.is_token_invalidated(user_id, iat):
        raise HTTPException(status_code=401, detail="Token invalidated: password changed")

    return PlatformAuthContext(
        user_id=user_id,
        email=payload.get("email", ""),
        role=role,
        shop_id=shop_id,
        is_super_admin=(role == "super_admin"),
        permissions=get_permissions(role),
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
    if ctx.is_super_admin:
        return ctx
    if ctx.shop_id is None:
        raise HTTPException(status_code=403, detail="No shop associated with this account")
    return ctx


def require_permission(permission: str) -> Callable:
    """
    RBAC-зависимость для эндпоинтов.

    Использование:
        from app.core.rbac import Perm
        from app.api.deps import require_permission

        @router.get("/products")
        async def list_products(
            ctx: PlatformAuthContext = require_permission(Perm.PRODUCTS_READ)
        ):
            ...
    """
    async def _check(
        ctx: PlatformAuthContext = Depends(require_platform_auth),
    ) -> PlatformAuthContext:
        if ctx.is_super_admin:
            return ctx
        if ctx.shop_id is None:
            raise HTTPException(status_code=403, detail="No shop associated with this account")
        if "*" in ctx.permissions or permission in ctx.permissions:
            return ctx
        raise HTTPException(
            status_code=403,
            detail=f"Permission required: {permission}",
        )

    return Depends(_check)


def get_owner_shop_id(
    ctx: PlatformAuthContext = Depends(require_shop_owner),
) -> int:
    """Legacy helper — use require_shop_id(Perm.X) for new endpoints."""
    return ctx.shop_id if ctx.shop_id is not None else 1


def require_shop_id(permission: str) -> int:
    """
    RBAC-зависимость: проверяет permission и возвращает shop_id как int.
    Drop-in замена get_owner_shop_id с гранулярным контролем доступа.

    Использование:
        from app.core.rbac import Perm
        from app.api.deps import require_shop_id

        @router.get("/")
        async def list_items(shop_id: int = require_shop_id(Perm.PRODUCTS_READ)):
            ...
    """
    async def _get(
        ctx: PlatformAuthContext = require_permission(permission),
    ) -> int:
        return ctx.shop_id if ctx.shop_id is not None else 1

    return Depends(_get)


def assert_shop_access(ctx: PlatformAuthContext, shop_id: int) -> None:
    if ctx.is_super_admin:
        return
    if ctx.shop_id != shop_id:
        raise HTTPException(status_code=403, detail="Access denied to this shop")


# ── Bot auth ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class BotAuthContext:
    """Контекст запроса от Telegram-бота: какой магазин + какой пользователь."""
    shop_id: int
    user_id: Optional[int]


# ── Mini App auth ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class MiniAppAuthContext:
    """Контекст авторизованного пользователя Telegram Mini App."""
    user_id: int
    shop_id: int


async def require_miniapp_auth(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> MiniAppAuthContext:
    """
    Проверяет JWT, выданный /miniapp/auth.
    Бросает 401 если токен отсутствует, недействителен или не является miniapp-токеном.
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Mini App: не авторизован")

    from app.services.miniapp_auth_service import decode_miniapp_token
    payload = decode_miniapp_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Mini App: токен недействителен или истёк")

    try:
        user_id = int(payload["sub"])
        shop_id = int(payload["shop_id"])
    except (KeyError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Mini App: повреждённый токен")

    return MiniAppAuthContext(user_id=user_id, shop_id=shop_id)


async def require_bot_auth(
    x_bot_token: Optional[str] = Header(default=None, alias="X-Bot-Token"),
    x_bot_user_id: Optional[int] = Header(default=None, alias="X-Bot-User-Id"),
    x_bot_shop_id: Optional[int] = Header(default=None, alias="X-Bot-Shop-Id"),
    session: AsyncSession = Depends(get_session),
) -> BotAuthContext:
    """
    Авторизация внутренних bot-only эндпоинтов.
    1. Проверяет X-Bot-Token == BOT_API_TOKEN.
    2. Проверяет X-Bot-Shop-Id — магазин должен существовать и быть active.
    Таким образом, даже утёкший BOT_API_TOKEN не даёт доступа
    к произвольному магазину.
    """
    from app.core.config import get_settings
    cfg = get_settings()

    if not cfg.bot_api_token:
        raise HTTPException(500, "BOT_API_TOKEN is not configured")
    if not x_bot_token or x_bot_token != cfg.bot_api_token:
        raise HTTPException(401, "Invalid bot token")
    if x_bot_shop_id is None:
        raise HTTPException(400, "X-Bot-Shop-Id header is required")

    # Verify the shop exists and is active
    from app.models.platform import Shop
    result = await session.execute(
        select(Shop.id).where(Shop.id == x_bot_shop_id, Shop.status == "active")
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(403, "Shop not found or not active")

    return BotAuthContext(shop_id=x_bot_shop_id, user_id=x_bot_user_id)
