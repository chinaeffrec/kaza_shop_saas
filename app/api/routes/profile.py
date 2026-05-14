"""
Profile endpoints — управление профилем пользователя платформы.

GET    /api/v1/profile              — текущий профиль (display_name, avatar, 2FA статус)
PATCH  /api/v1/profile              — обновить display_name
POST   /api/v1/profile/avatar       — загрузить аватар (multipart)
POST   /api/v1/profile/2fa/setup    — сгенерировать TOTP секрет, вернуть QR URI
POST   /api/v1/profile/2fa/verify   — подтвердить TOTP код и включить 2FA
DELETE /api/v1/profile/2fa          — отключить 2FA
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import PlatformAuthContext, require_platform_auth
from app.core.security import check_image_magic, sanitize_filename
from app.db.session import get_session
from app.models.platform import PlatformUser
from app.services import platform_auth_service as svc

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/profile", tags=["profile"])

_AVATAR_DIR = Path("/app/media/avatars")
_ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
_MAX_SIZE = 5 * 1024 * 1024  # 5 MB


# ── Schemas ───────────────────────────────────────────────────────────────────

class ProfileResponse(BaseModel):
    user_id: int
    email: str
    display_name: Optional[str]
    avatar_url: Optional[str]
    totp_enabled: bool
    is_super_admin: bool


class ProfileUpdateRequest(BaseModel):
    display_name: Optional[str] = Field(default=None, max_length=128)


class TotpSetupResponse(BaseModel):
    otpauth_uri: str
    secret: str  # показывается один раз для ручного ввода


class TotpVerifyRequest(BaseModel):
    code: str = Field(min_length=6, max_length=8)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_platform_user(user_id: int, session: AsyncSession) -> PlatformUser:
    user = await svc.get_user_by_id(user_id, session)
    if not user:
        raise HTTPException(404, "Пользователь не найден")
    return user


def _profile_resp(user: PlatformUser) -> ProfileResponse:
    return ProfileResponse(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        totp_enabled=user.totp_enabled,
        is_super_admin=user.is_super_admin,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=ProfileResponse)
async def get_profile(
    ctx: PlatformAuthContext = Depends(require_platform_auth),
    session: AsyncSession = Depends(get_session),
):
    """Возвращает профиль текущего пользователя."""
    user = await _get_platform_user(ctx.user_id, session)
    return _profile_resp(user)


@router.patch("", response_model=ProfileResponse)
async def update_profile(
    body: ProfileUpdateRequest,
    ctx: PlatformAuthContext = Depends(require_platform_auth),
    session: AsyncSession = Depends(get_session),
):
    """Обновляет display_name пользователя."""
    user = await _get_platform_user(ctx.user_id, session)
    if body.display_name is not None:
        user.display_name = body.display_name.strip() or None
    await session.commit()
    await session.refresh(user)
    return _profile_resp(user)


@router.post("/avatar", response_model=ProfileResponse)
async def upload_avatar(
    file: UploadFile = File(...),
    ctx: PlatformAuthContext = Depends(require_platform_auth),
    session: AsyncSession = Depends(get_session),
):
    """Загружает аватар пользователя (JPEG / PNG / WebP, до 5 МБ)."""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_EXTS:
        raise HTTPException(400, f"Недопустимый формат файла. Допустимы: {', '.join(_ALLOWED_EXTS)}")

    data = await file.read()
    if len(data) > _MAX_SIZE:
        raise HTTPException(400, "Файл слишком большой (максимум 5 МБ)")

    # Validate actual file content via magic bytes (prevents polyglot exploits)
    detected = check_image_magic(data, field_name="file")
    # Remap detected format to canonical extension
    ext_map = {"jpeg": ".jpg", "png": ".png", "webp": ".webp", "gif": ".gif"}
    ext = ext_map.get(detected, ext)

    _AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{ctx.user_id}_{uuid.uuid4().hex[:8]}{ext}"
    dest = _AVATAR_DIR / filename

    dest.write_bytes(data)

    user = await _get_platform_user(ctx.user_id, session)
    # Удаляем старый аватар если есть
    if user.avatar_url:
        old_path = Path("/app/media") / user.avatar_url.lstrip("/media/")
        old_path.unlink(missing_ok=True)

    user.avatar_url = f"/media/avatars/{filename}"
    await session.commit()
    await session.refresh(user)
    logger.info("Avatar updated for user %d: %s", ctx.user_id, filename)
    return _profile_resp(user)


@router.post("/2fa/setup", response_model=TotpSetupResponse)
async def setup_2fa(
    ctx: PlatformAuthContext = Depends(require_platform_auth),
    session: AsyncSession = Depends(get_session),
):
    """
    Генерирует новый TOTP-секрет. Не включает 2FA — нужно подтвердить кодом.
    Секрет сохраняется в БД зашифрованным (Fernet); totp_enabled остаётся False.
    """
    user = await _get_platform_user(ctx.user_id, session)
    plaintext_secret = svc.generate_totp_secret()
    # Encrypt before persisting to DB
    user.totp_secret = svc.encrypt_totp_secret(plaintext_secret)
    # totp_enabled пока False — включится после verify
    await session.commit()

    # Return the plaintext secret for QR / manual entry (shown only once)
    uri = svc.get_totp_uri(plaintext_secret, user.email)
    return TotpSetupResponse(otpauth_uri=uri, secret=plaintext_secret)


@router.post("/2fa/verify", response_model=ProfileResponse)
async def verify_2fa(
    body: TotpVerifyRequest,
    ctx: PlatformAuthContext = Depends(require_platform_auth),
    session: AsyncSession = Depends(get_session),
):
    """
    Проверяет TOTP код и включает 2FA.
    Требует предварительного вызова /2fa/setup.
    """
    user = await _get_platform_user(ctx.user_id, session)
    if not user.totp_secret:
        raise HTTPException(400, "Сначала выполните /profile/2fa/setup")
    # Decrypt stored secret before passing to pyotp
    plaintext_secret = svc.decrypt_totp_secret(user.totp_secret)
    if not svc.verify_totp_code(plaintext_secret, body.code):
        raise HTTPException(400, "Неверный код. Проверьте время на устройстве.")
    user.totp_enabled = True
    await session.commit()
    await session.refresh(user)
    logger.info("2FA enabled for user %d (%s)", ctx.user_id, user.email)
    return _profile_resp(user)


@router.delete("/2fa", response_model=ProfileResponse)
async def disable_2fa(
    ctx: PlatformAuthContext = Depends(require_platform_auth),
    session: AsyncSession = Depends(get_session),
):
    """Отключает 2FA и удаляет TOTP-секрет."""
    user = await _get_platform_user(ctx.user_id, session)
    user.totp_enabled = False
    user.totp_secret = None
    await session.commit()
    await session.refresh(user)
    logger.info("2FA disabled for user %d (%s)", ctx.user_id, user.email)
    return _profile_resp(user)
