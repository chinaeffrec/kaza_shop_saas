"""
Platform auth endpoints.

POST   /platform/auth/login         — вход по email + пароль
POST   /platform/auth/refresh       — обновление токенов (ротация)
POST   /platform/auth/logout        — отзыв refresh-токена
GET    /platform/auth/me            — профиль текущего пользователя
PATCH  /platform/auth/password      — смена пароля
POST   /platform/auth/users         — создание пользователя платформы [super_admin]
GET    /platform/auth/users         — список пользователей [super_admin]
PATCH  /platform/auth/users/{id}/deactivate — деактивация [super_admin]
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import PlatformAuthContext, require_platform_auth, require_super_admin
from app.api.schemas.platform_auth import (
    CreatePlatformUserRequest,
    PasswordChangeRequest,
    PlatformLoginRequest,
    PlatformMeResponse,
    PlatformUserResponse,
    TokenRefreshRequest,
    TokenResponse,
    TotpChallengeResponse,
    TotpVerifyLoginRequest,
)
from app.db.session import get_session
from app.models.platform import PlatformUser
from app.services import platform_auth_service as svc

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/platform/auth", tags=["auth"])


# ── Login ──────────────────────────────────────────────────────────────────────
@router.post(
    "/login",
    summary="Вход в seller panel",
    response_description="JWT access + refresh токены, или 2FA challenge при включённом TOTP",
    responses={
        200: {
            "description": "Успешный вход",
            "content": {
                "application/json": {
                    "examples": {
                        "success": {
                            "summary": "Вход без 2FA",
                            "value": {
                                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                                "refresh_token": "550e8400-e29b-41d4-a716-446655440000",
                                "token_type": "bearer",
                                "expires_in": 3600,
                            },
                        },
                        "totp_challenge": {
                            "summary": "2FA включён — нужен TOTP",
                            "value": {
                                "requires_totp": True,
                                "challenge_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                            },
                        },
                    }
                }
            },
        },
        401: {"description": "Неверный email или пароль"},
        429: {"description": "Слишком много попыток входа"},
    },
)
async def login(
    data: PlatformLoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """
    Логин по email + пароль.

    - Без 2FA: возвращает `access_token` + `refresh_token`
    - С 2FA: возвращает `{ requires_totp: true, challenge_token }` — передайте
      `challenge_token` и TOTP-код в `POST /platform/auth/2fa/verify`

    **Rate limit**: 5 попыток / 60 сек с одного IP.
    """
    ip = request.client.host if request.client else "unknown"
    allowed, retry_after = await svc.check_login_rate_limit(ip)
    if not allowed:
        if retry_after == -1:
            raise HTTPException(status_code=503, detail="Сервис временно недоступен (Redis)")
        raise HTTPException(
            status_code=429,
            detail=f"Слишком много попыток. Повторите через {retry_after} сек.",
            headers={"Retry-After": str(retry_after)},
        )

    user = await svc.authenticate_user(data.email, data.password, session)
    if user is None:
        raise HTTPException(status_code=401, detail="Неверный email или пароль")

    await svc.clear_login_rate_limit(ip)

    # 2FA: если включён — вернуть challenge вместо токенов
    if user.totp_enabled and user.totp_secret:
        challenge = svc.create_totp_challenge_token(user.id)
        logger.info("Platform login 2FA challenge: user=%d", user.id)
        return TotpChallengeResponse(challenge_token=challenge)

    role, shop_id = await svc.get_token_claims(user, session)
    refresh_jti = await svc.create_refresh_token(user.id)
    access_token = svc.create_access_token(user.id, role, shop_id, email=user.email)

    logger.info("Platform login: user=%d role=%s", user.id, role)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_jti,
        expires_in=svc._cfg.access_token_ttl,
    )


@router.post("/2fa/verify", response_model=TokenResponse)
async def verify_2fa_login(
    data: TotpVerifyLoginRequest,
    session: AsyncSession = Depends(get_session),
):
    """Второй шаг входа: проверяет TOTP-код по challenge_token, выдаёт полные токены."""
    user_id = svc.decode_totp_challenge_token(data.challenge_token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Недействительный или истёкший challenge_token")

    user = await svc.get_user_by_id(user_id, session)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Пользователь не найден или деактивирован")

    if not user.totp_secret:
        raise HTTPException(status_code=400, detail="2FA не настроена для этого пользователя")
    try:
        _plaintext_secret = svc.decrypt_totp_secret(user.totp_secret)
    except ValueError:
        raise HTTPException(status_code=500, detail="Ошибка расшифровки 2FA секрета")
    if not svc.verify_totp_code(_plaintext_secret, data.totp_code):
        raise HTTPException(status_code=400, detail="Неверный код. Проверьте время на устройстве.")

    role, shop_id = await svc.get_token_claims(user, session)
    refresh_jti = await svc.create_refresh_token(user.id)
    access_token = svc.create_access_token(user.id, role, shop_id, email=user.email)

    logger.info("Platform 2FA login success: user=%d role=%s", user.id, role)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_jti,
        expires_in=svc._cfg.access_token_ttl,
    )


# ── Refresh ────────────────────────────────────────────────────────────────────
@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    data: TokenRefreshRequest,
    session: AsyncSession = Depends(get_session),
):
    new_jti, user_id = await svc.rotate_refresh_token(data.refresh_token)
    if new_jti is None or user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    user = await svc.get_user_by_id(user_id, session)
    if not user or not user.is_active:
        # Отзываем новый токен, если пользователь деактивирован
        await svc.revoke_refresh_token(new_jti)
        raise HTTPException(status_code=401, detail="User deactivated")

    role, shop_id = await svc.get_token_claims(user, session)
    access_token = svc.create_access_token(user.id, role, shop_id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_jti,
        expires_in=svc._cfg.access_token_ttl,
    )


# ── Logout ─────────────────────────────────────────────────────────────────────
@router.post("/logout", status_code=204)
async def logout(
    data: TokenRefreshRequest,
    _: PlatformAuthContext = Depends(require_platform_auth),
):
    await svc.revoke_refresh_token(data.refresh_token)


# ── Me ─────────────────────────────────────────────────────────────────────────
@router.get("/me", response_model=PlatformMeResponse)
async def me(
    ctx: PlatformAuthContext = Depends(require_platform_auth),
    session: AsyncSession = Depends(get_session),
):
    user = await svc.get_user_by_id(ctx.user_id, session)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return PlatformMeResponse(
        user_id=user.id,
        email=user.email,
        role=ctx.role,
        shop_id=ctx.shop_id,
        is_super_admin=user.is_super_admin,
        permissions=sorted(ctx.permissions) if "*" not in ctx.permissions else ["*"],
    )


# ── Смена пароля ───────────────────────────────────────────────────────────────
@router.patch("/password", status_code=204)
async def change_password(
    data: PasswordChangeRequest,
    ctx: PlatformAuthContext = Depends(require_platform_auth),
    session: AsyncSession = Depends(get_session),
):
    await svc.change_password(ctx.user_id, data.current_password, data.new_password, session)


# ── Управление пользователями (super admin) ────────────────────────────────────
@router.post("/users", response_model=PlatformUserResponse, status_code=201)
async def create_user(
    data: CreatePlatformUserRequest,
    _: PlatformAuthContext = Depends(require_super_admin),
    session: AsyncSession = Depends(get_session),
):
    user = await svc.create_platform_user(
        data.email, data.password, data.is_super_admin, session
    )
    return PlatformUserResponse(
        user_id=user.id,
        email=user.email,
        is_super_admin=user.is_super_admin,
        is_active=user.is_active,
    )


@router.get("/users", response_model=list[PlatformUserResponse])
async def list_users(
    _: PlatformAuthContext = Depends(require_super_admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(PlatformUser).order_by(PlatformUser.created_at)
    )
    users = result.scalars().all()
    return [
        PlatformUserResponse(
            user_id=u.id,
            email=u.email,
            is_super_admin=u.is_super_admin,
            is_active=u.is_active,
        )
        for u in users
    ]


@router.patch("/users/{user_id}/deactivate", status_code=204)
async def deactivate_user(
    user_id: int,
    ctx: PlatformAuthContext = Depends(require_super_admin),
    session: AsyncSession = Depends(get_session),
):
    if user_id == ctx.user_id:
        raise HTTPException(status_code=400, detail="Нельзя деактивировать самого себя")

    user = await svc.get_user_by_id(user_id, session)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = False
    await session.commit()
    # Инвалидируем все активные токены пользователя
    await svc.mark_password_changed(user_id)
    logger.info("Platform user %d deactivated by admin %d", user_id, ctx.user_id)
