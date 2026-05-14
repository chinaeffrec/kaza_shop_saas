"""
Сервис аутентификации платформы.

Принципы безопасности:
  - bcrypt rounds=12 для паролей
  - Access token: JWT HS256, TTL 1 час, payload содержит jti
  - Refresh token: непрозрачный UUID4, хранится в Redis (TTL 30 дней)
  - Ротация refresh-токенов: при каждом обновлении старый удаляется,
    выдаётся новая пара. Replay-атака аннулирует оба токена.
  - Инвалидация при смене пароля: записываем timestamp в Redis,
    при валидации токена сверяем с iat.
  - Rate limiting на login: 5 попыток / 60 сек с IP, Redis + in-memory fallback.
"""
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.redis_client import (
    redis_delete, redis_expire, redis_get, redis_incr, redis_set, redis_ttl,
)
from app.models.platform import PlatformUser, Shop

logger = logging.getLogger(__name__)
_cfg = get_settings()

# ── Rate limiting ──────────────────────────────────────────────────────────────
_RATE_LIMIT_MAX = 5
_RATE_LIMIT_WINDOW = 60


async def check_login_rate_limit(ip: str) -> tuple[bool, int]:
    """
    Возвращает (allowed, retry_after_seconds).
    Использует только Redis — fallback-in-memory намеренно удалён (B6):
    если Redis недоступен, логин не работает, что лучше чем обходить rate limit.
    """
    key = f"rl:platform_login:{ip}"
    count = await redis_incr(key)
    if count is None:
        # Redis недоступен — отказываем с 503 (вызывающий код обрабатывает None)
        return False, -1
    if count == 1:
        await redis_expire(key, _RATE_LIMIT_WINDOW)
    if count > _RATE_LIMIT_MAX:
        ttl = max(await redis_ttl(key), 1)
        return False, ttl
    return True, 0


async def clear_login_rate_limit(ip: str) -> None:
    await redis_delete(f"rl:platform_login:{ip}")


# ── 2FA attempt rate limiting ─────────────────────────────────────────────────
# Ограничивает перебор TOTP-кодов: max 5 попыток за TTL challenge-токена (5 мин).
# Ключ привязан к user_id, а не к IP — один пользователь на одном challenge.
_TOTP_MAX_ATTEMPTS = 5
_TOTP_ATTEMPT_WINDOW = 300  # 5 минут = TTL challenge-токена


async def check_totp_attempt(user_id: int) -> tuple[bool, int]:
    """
    Увеличивает счётчик попыток TOTP для пользователя.
    Возвращает (allowed, attempts_remaining).
    При недоступности Redis — fail-closed (блокируем, 0 попыток остаётся).
    """
    key = f"totp_attempts:{user_id}"
    count = await redis_incr(key)
    if count is None:
        return False, 0
    if count == 1:
        await redis_expire(key, _TOTP_ATTEMPT_WINDOW)
    remaining = max(_TOTP_MAX_ATTEMPTS - count, 0)
    return count <= _TOTP_MAX_ATTEMPTS, remaining


async def clear_totp_attempts(user_id: int) -> None:
    """Сбрасывает счётчик после успешного входа."""
    await redis_delete(f"totp_attempts:{user_id}")


# ── Пароли ────────────────────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False


# ── JWT (access token) ────────────────────────────────────────────────────────
def _require_platform_secret() -> str:
    """
    Использует PLATFORM_JWT_SECRET (приоритет) или SECRET_KEY как fallback.
    В продакшене PLATFORM_JWT_SECRET обязателен — задаётся отдельно от
    legacy SECRET_KEY, чтобы ротация одного не инвалидировала другой.
    """
    secret = _cfg.platform_jwt_secret or _cfg.secret_key
    if not secret:
        raise RuntimeError("PLATFORM_JWT_SECRET (or SECRET_KEY) must be set in environment")
    return secret


def create_access_token(
    user_id: int,
    role: str,
    shop_id: Optional[int],
    email: str = "",
    jti: Optional[str] = None,
) -> str:
    secret = _require_platform_secret()
    now = datetime.now(timezone.utc)
    now_ts = int(now.timestamp())
    payload = {
        "sub": str(user_id),
        "role": role,
        "shop_id": shop_id,
        "email": email,
        "iat": now_ts,
        "nbf": now_ts,
        "exp": now_ts + _cfg.access_token_ttl,
        "jti": jti or str(uuid.uuid4()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_access_token(token: str) -> Optional[dict]:
    """
    Декодирует и валидирует access-токен.
    Возвращает payload или None при любой ошибке.
    """
    try:
        return jwt.decode(token, _require_platform_secret(), algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


# ── Refresh tokens (Redis) ────────────────────────────────────────────────────
_RT_PREFIX = "prt:"


def _rt_key(jti: str) -> str:
    return f"{_RT_PREFIX}{jti}"


async def create_refresh_token(user_id: int) -> str:
    """Создаёт refresh-токен, сохраняет user_id в Redis. Возвращает jti."""
    jti = str(uuid.uuid4())
    await redis_set(_rt_key(jti), str(user_id), ex=_cfg.refresh_token_ttl)
    return jti


async def rotate_refresh_token(old_jti: str) -> tuple[Optional[str], Optional[int]]:
    """
    Ротация: проверяет старый refresh-токен, создаёт новый.
    Возвращает (new_jti, user_id) или (None, None) если токен невалиден.

    При обнаружении повторного использования (replay) — удаляем оба токена.
    Поскольку мы не храним "использованные" отдельно, сам факт отсутствия
    ключа в Redis означает либо истечение, либо уже использованный токен.
    """
    value = await redis_get(_rt_key(old_jti))
    if value is None:
        return None, None

    user_id = int(value)
    # Атомарно: удаляем старый перед созданием нового
    await redis_delete(_rt_key(old_jti))
    new_jti = await create_refresh_token(user_id)
    return new_jti, user_id


async def revoke_refresh_token(jti: str) -> None:
    await redis_delete(_rt_key(jti))


# ── Инвалидация при смене пароля ──────────────────────────────────────────────
_PC_PREFIX = "pc:"


async def mark_password_changed(user_id: int) -> None:
    """
    Записывает timestamp смены пароля.
    Все токены с iat < этого timestamp будут отклонены.
    TTL = refresh_token_ttl, чтобы гарантированно покрыть долгоживущие токены.
    """
    key = f"{_PC_PREFIX}{user_id}"
    await redis_set(key, str(int(time.time())), ex=_cfg.refresh_token_ttl)


async def is_token_invalidated(user_id: int, iat: int) -> bool:
    """True если токен выдан до последней смены пароля."""
    key = f"{_PC_PREFIX}{user_id}"
    value = await redis_get(key)
    if value is None:
        return False
    try:
        return iat < int(value)
    except ValueError:
        return False


# ── CRUD платформенных пользователей ──────────────────────────────────────────
async def get_user_by_email(email: str, session: AsyncSession) -> Optional[PlatformUser]:
    result = await session.execute(
        select(PlatformUser).where(PlatformUser.email == email.lower())
    )
    return result.scalar_one_or_none()


async def get_user_by_id(user_id: int, session: AsyncSession) -> Optional[PlatformUser]:
    result = await session.execute(
        select(PlatformUser).where(PlatformUser.id == user_id)
    )
    return result.scalar_one_or_none()


async def create_platform_user(
    email: str,
    password: str,
    is_super_admin: bool,
    session: AsyncSession,
) -> PlatformUser:
    normalized_email = email.lower().strip()
    existing = await get_user_by_email(normalized_email, session)
    if existing:
        from fastapi import HTTPException
        raise HTTPException(409, f"Email {normalized_email} уже зарегистрирован")

    user = PlatformUser(
        email=normalized_email,
        password_hash=hash_password(password),
        is_super_admin=is_super_admin,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    logger.info("Platform user created: %s (super_admin=%s)", normalized_email, is_super_admin)
    return user


async def authenticate_user(
    email: str,
    password: str,
    session: AsyncSession,
) -> Optional[PlatformUser]:
    user = await get_user_by_email(email, session)
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


async def change_password(
    user_id: int,
    current_password: str,
    new_password: str,
    session: AsyncSession,
) -> None:
    from fastapi import HTTPException
    user = await get_user_by_id(user_id, session)
    if not user:
        raise HTTPException(404, "Пользователь не найден")
    if not verify_password(current_password, user.password_hash):
        raise HTTPException(400, "Неверный текущий пароль")
    user.password_hash = hash_password(new_password)
    await session.commit()
    await mark_password_changed(user_id)
    logger.info("Password changed for platform user %d", user_id)


# ── Определение роли и shop_id для токена ────────────────────────────────────
async def get_token_claims(
    user: PlatformUser,
    session: AsyncSession,
) -> tuple[str, Optional[int]]:
    """
    Возвращает (role, shop_id) для включения в JWT.

    Порядок проверки:
    1. super_admin → ("super_admin", None)
    2. Есть запись в shop_members → (member.role, member.shop_id)
    3. Fallback: shop.owner_id (legacy, до наполнения shop_members) → ("owner", shop.id)
    4. Нет магазина → ("owner", None)
    """
    if user.is_super_admin:
        return "super_admin", None

    from app.models.platform import Shop, ShopMember

    # Приоритет: shop_members — поддерживает manager/support роли
    member_result = await session.execute(
        select(ShopMember)
        .where(ShopMember.user_id == user.id)
        .order_by(ShopMember.created_at)
        .limit(1)
    )
    member = member_result.scalar_one_or_none()
    if member:
        return member.role, member.shop_id

    # Fallback для существующих владельцев, у которых ещё нет записи в shop_members
    shop_result = await session.execute(
        select(Shop)
        .where(Shop.owner_id == user.id, Shop.status != "suspended")
        .order_by(Shop.created_at)
        .limit(1)
    )
    shop = shop_result.scalar_one_or_none()
    return "owner", shop.id if shop else None


# ── 2FA (TOTP) ────────────────────────────────────────────────────────────────
_TOTP_CHALLENGE_TTL = 300  # 5 минут


def _totp_challenge_secret() -> str:
    return _require_platform_secret()


def create_totp_challenge_token(user_id: int) -> str:
    """Короткоживущий JWT (5 мин) для прохождения второго шага 2FA."""
    now = datetime.now(timezone.utc)
    now_ts = int(now.timestamp())
    payload = {
        "sub": str(user_id),
        "scope": "totp_challenge",
        "iat": now_ts,
        "nbf": now_ts,
        "exp": now_ts + _TOTP_CHALLENGE_TTL,
    }
    return jwt.encode(payload, _totp_challenge_secret(), algorithm="HS256")


def decode_totp_challenge_token(token: str) -> Optional[int]:
    """Возвращает user_id или None при ошибке/истечении/неверном scope."""
    try:
        payload = jwt.decode(token, _totp_challenge_secret(), algorithms=["HS256"])
        if payload.get("scope") != "totp_challenge":
            return None
        return int(payload["sub"])
    except Exception:
        return None


def generate_totp_secret() -> str:
    """Генерирует новый TOTP-секрет (base32, 32 символа)."""
    import pyotp
    return pyotp.random_base32()


def get_totp_uri(secret: str, email: str, issuer: str = "Kaza Shop") -> str:
    """Возвращает otpauth:// URI для QR-кода.
    `secret` здесь — открытый base32 (ещё не зашифрованный).
    """
    import pyotp
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)


def verify_totp_code(secret: str, code: str) -> bool:
    """Проверяет TOTP-код. Допускает ±1 временной интервал (30 сек каждый).
    `secret` здесь — открытый base32 (уже расшифрованный из БД).
    """
    import pyotp
    try:
        totp = pyotp.TOTP(secret)
        return totp.verify(code, valid_window=1)
    except Exception:
        return False


# ── Шифрование TOTP-секрета (Fernet) ─────────────────────────────────────────
# Использует тот же Fernet-ключ, что и encrypt_field() из encryption.py
# (ключ выводится из SECRET_KEY через SHA-256). Изменение SECRET_KEY требует
# повторного шифрования всех TOTP-секретов и bot_token'ов.

def encrypt_totp_secret(plaintext_secret: str) -> str:
    """Шифрует открытый TOTP base32-секрет.

    Возвращает строку вида ``enc:<fernet-token>``.
    Префикс ``enc:`` отличает зашифрованные значения от устаревших открытых
    текстов (обратная совместимость при миграции).
    """
    from app.core.encryption import _get_fernet
    try:
        token = _get_fernet().encrypt(plaintext_secret.encode()).decode()
        return "enc:" + token
    except RuntimeError:
        # SECRET_KEY не задан — только в development без шифрования
        logger.warning("SECRET_KEY not set — TOTP secret stored unencrypted (development only)")
        return plaintext_secret


def decrypt_totp_secret(stored_secret: str) -> str:
    """Расшифровывает TOTP-секрет из БД.

    Прозрачно обрабатывает оба формата — зашифрованный (``enc:…``) и
    устаревший открытый текст (обратная совместимость при миграции).
    """
    if not stored_secret.startswith("enc:"):
        return stored_secret
    from cryptography.fernet import InvalidToken
    from app.core.encryption import _get_fernet
    try:
        return _get_fernet().decrypt(stored_secret[4:].encode()).decode()
    except RuntimeError as exc:
        logger.error("SECRET_KEY not set but encrypted TOTP secret found in DB")
        raise ValueError("Cannot decrypt TOTP secret: SECRET_KEY is not configured") from exc
    except InvalidToken as exc:
        logger.error("Failed to decrypt TOTP secret — SECRET_KEY mismatch?")
        raise ValueError("Cannot decrypt TOTP secret") from exc


# ── Сид первого суперадмина ───────────────────────────────────────────────────
async def seed_super_admin(session: AsyncSession) -> None:
    """
    Вызывается при старте приложения.
    Создаёт суперадмина из env SUPER_ADMIN_EMAIL / SUPER_ADMIN_PASSWORD
    только если таблица platform_users пуста.
    """
    from sqlalchemy import func
    count_result = await session.execute(select(func.count()).select_from(PlatformUser))
    count = count_result.scalar()
    if count and count > 0:
        return

    email = _cfg.super_admin_email.strip().lower()
    password = _cfg.super_admin_password

    if not email or not password:
        logger.warning(
            "No platform users exist and SUPER_ADMIN_EMAIL/SUPER_ADMIN_PASSWORD "
            "are not set. Platform admin access will be unavailable."
        )
        return

    user = PlatformUser(
        email=email,
        password_hash=hash_password(password),
        is_super_admin=True,
    )
    session.add(user)
    await session.commit()
    logger.info("Super admin seeded: %s", email)
