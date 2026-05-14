"""
Super Admin Control Center.

GET    /platform/monitoring              — live-метрики платформы
GET    /platform/health/detailed         — расширенный health-check
POST   /platform/shops/{id}/impersonate  — токен-импersonation владельца магазина
GET    /platform/broadcast               — список системных сообщений
POST   /platform/broadcast               — создать системное сообщение
DELETE /platform/broadcast/{id}          — удалить сообщение
GET    /platform/maintenance             — текущее состояние техработ
POST   /platform/maintenance             — включить/выключить режим обслуживания
GET    /platform/feature-flags           — список feature-флагов
POST   /platform/feature-flags           — создать / обновить флаг
DELETE /platform/feature-flags/{key}     — удалить флаг
"""
import logging
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import PlatformAuthContext, require_super_admin
from app.core.maintenance import get_maintenance_state, set_maintenance
from app.core.redis_client import get_redis
from app.db.session import get_session
from app.models.feature_flag import FeatureFlag, PlatformBroadcast
from app.models.order import Order
from app.models.platform import Shop
from app.services.audit_service import audit_log, from_request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/platform", tags=["platform-control"])

# Process start time for uptime calc
_PROC_START = time.monotonic()


# ── Schemas ───────────────────────────────────────────────────────────────────

class MonitoringResponse(BaseModel):
    ts: str
    uptime_sec: int
    uptime_human: str
    active_shops: int
    db_size_bytes: int
    db_size_human: str
    redis_memory_bytes: int
    redis_memory_human: str
    orders_last_hour: int
    orders_today: int
    new_orders_count: int
    maintenance_active: bool


class HealthDetailedResponse(BaseModel):
    status: str
    uptime_sec: int
    uptime_human: str
    ts: str
    checks: dict


class ImpersonateResponse(BaseModel):
    access_token: str
    shop_id: int
    shop_name: str
    expires_in: int
    impersonated_by_email: str


class MaintenanceRequest(BaseModel):
    active: bool
    message: str = ""


class MaintenanceResponse(BaseModel):
    active: bool
    message: str
    started_at: Optional[str] = None
    started_by: Optional[str] = None


class BroadcastRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=256)
    body: str = Field(..., min_length=1)
    expires_at: Optional[datetime] = None


class BroadcastResponse(BaseModel):
    id: int
    title: str
    body: str
    is_active: bool
    created_by_email: Optional[str]
    created_at: datetime
    expires_at: Optional[datetime]


class FeatureFlagRequest(BaseModel):
    key: str = Field(..., min_length=1, max_length=128, pattern=r"^[a-z0-9_.:-]+$")
    is_enabled: bool = False
    description: Optional[str] = None


class FeatureFlagResponse(BaseModel):
    id: int
    key: str
    is_enabled: bool
    description: Optional[str]
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt_uptime(sec: int) -> str:
    d, rem = divmod(sec, 86400)
    h, rem = divmod(rem, 3600)
    m, s = divmod(rem, 60)
    parts: list[str] = []
    if d:
        parts.append(f"{d}д")
    if h:
        parts.append(f"{h}ч")
    if m:
        parts.append(f"{m}м")
    parts.append(f"{s}с")
    return " ".join(parts)


def _fmt_bytes(n: int) -> str:
    for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} ПБ"


# ── Monitoring ────────────────────────────────────────────────────────────────

@router.get("/monitoring", response_model=MonitoringResponse)
async def get_monitoring(
    _: PlatformAuthContext = Depends(require_super_admin),
    session: AsyncSession = Depends(get_session),
):
    """Live-метрики платформы: БД, Redis, заказы, магазины."""
    uptime_sec = int(time.monotonic() - _PROC_START)

    # Active shops count
    active_shops = await session.scalar(
        select(func.count(Shop.id)).where(Shop.status == "active")
    ) or 0

    # DB size
    db_size_bytes = await session.scalar(
        text("SELECT pg_database_size(current_database())")
    ) or 0

    # Orders stats
    now_utc = datetime.now(timezone.utc)
    hour_ago = now_utc - timedelta(hours=1)
    today_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)

    orders_last_hour = await session.scalar(
        select(func.count(Order.id)).where(Order.created_at >= hour_ago)
    ) or 0

    orders_today = await session.scalar(
        select(func.count(Order.id)).where(Order.created_at >= today_start)
    ) or 0

    new_orders_count = await session.scalar(
        select(func.count(Order.id)).where(Order.status == "new")
    ) or 0

    # Redis memory
    redis_memory_bytes = 0
    redis_memory_human = "N/A"
    try:
        r = get_redis()
        if r:
            info = await r.info("memory")
            redis_memory_bytes = int(info.get("used_memory", 0))
            redis_memory_human = info.get("used_memory_human", _fmt_bytes(redis_memory_bytes))
    except Exception as exc:
        logger.debug("Redis INFO failed: %s", exc)

    # Maintenance state
    maint = await get_maintenance_state()

    return MonitoringResponse(
        ts=now_utc.isoformat(),
        uptime_sec=uptime_sec,
        uptime_human=_fmt_uptime(uptime_sec),
        active_shops=active_shops,
        db_size_bytes=db_size_bytes,
        db_size_human=_fmt_bytes(db_size_bytes),
        redis_memory_bytes=redis_memory_bytes,
        redis_memory_human=redis_memory_human,
        orders_last_hour=orders_last_hour,
        orders_today=orders_today,
        new_orders_count=new_orders_count,
        maintenance_active=bool(maint),
    )


# ── Detailed health ───────────────────────────────────────────────────────────

@router.get("/health/detailed", response_model=HealthDetailedResponse)
async def health_detailed(
    _: PlatformAuthContext = Depends(require_super_admin),
    session: AsyncSession = Depends(get_session),
):
    """Расширенный health-check: БД, Redis, диск, память."""
    uptime_sec = int(time.monotonic() - _PROC_START)
    checks: dict = {}

    # Database
    try:
        t0 = time.monotonic()
        await session.execute(text("SELECT 1"))
        latency_ms = int((time.monotonic() - t0) * 1000)
        checks["database"] = {"status": "ok", "latency_ms": latency_ms}
    except Exception as e:
        checks["database"] = {"status": "error", "error": str(e)}

    # Redis
    try:
        r = get_redis()
        if r:
            t0 = time.monotonic()
            await r.ping()
            latency_ms = int((time.monotonic() - t0) * 1000)
            info = await r.info("server")
            checks["redis"] = {
                "status": "ok",
                "latency_ms": latency_ms,
                "version": info.get("redis_version", "?"),
            }
        else:
            checks["redis"] = {"status": "unavailable"}
    except Exception as e:
        checks["redis"] = {"status": "error", "error": str(e)}

    # Disk
    import shutil
    for path in ("/app/media", "/tmp"):
        try:
            usage = shutil.disk_usage(path)
            pct = int(usage.used / usage.total * 100)
            checks["disk"] = {
                "status": "warn" if pct > 85 else "ok",
                "used_pct": pct,
                "free_gb": round(usage.free / 1024 ** 3, 1),
                "path": path,
            }
            break
        except Exception:
            continue

    # Memory
    try:
        with open("/proc/meminfo") as f:
            meminfo = {
                line.split(":")[0]: int(line.split(":")[1].strip().split()[0])
                for line in f
                if ":" in line
            }
        free_mb = meminfo.get("MemAvailable", 0) // 1024
        total_mb = meminfo.get("MemTotal", 0) // 1024
        checks["memory"] = {
            "status": "warn" if free_mb < 100 else "ok",
            "free_mb": free_mb,
            "total_mb": total_mb,
            "used_pct": int((total_mb - free_mb) / total_mb * 100) if total_mb else 0,
        }
    except Exception:
        checks["memory"] = {"status": "unknown"}

    # Bot tasks (read from Redis heartbeat keys)
    try:
        r = get_redis()
        if r:
            bot_keys = await r.keys("bot:heartbeat:*")
            checks["bots"] = {
                "status": "ok",
                "active_count": len(bot_keys),
                "note": "heartbeat keys present in Redis",
            }
        else:
            checks["bots"] = {"status": "unknown", "note": "Redis unavailable"}
    except Exception:
        checks["bots"] = {"status": "unknown"}

    # Maintenance
    maint = await get_maintenance_state()
    checks["maintenance"] = {
        "status": "warn" if maint else "ok",
        "active": bool(maint),
        "started_by": maint.get("started_by") if maint else None,
    }

    overall = "ok"
    for c in checks.values():
        s = c.get("status", "ok")
        if s == "error":
            overall = "error"
            break
        if s == "warn" and overall != "error":
            overall = "warn"

    return HealthDetailedResponse(
        status=overall,
        uptime_sec=uptime_sec,
        uptime_human=_fmt_uptime(uptime_sec),
        ts=datetime.now(timezone.utc).isoformat(),
        checks=checks,
    )


# ── Impersonation ─────────────────────────────────────────────────────────────

@router.post("/shops/{shop_id}/impersonate", response_model=ImpersonateResponse)
async def impersonate_shop(
    shop_id: int,
    request: Request,
    ctx: PlatformAuthContext = Depends(require_super_admin),
    session: AsyncSession = Depends(get_session),
):
    """
    Создаёт короткоживущий токен (1ч) с правами owner указанного магазина.
    Действие записывается в audit_log.
    """
    shop = await session.scalar(select(Shop).where(Shop.id == shop_id))
    if not shop:
        raise HTTPException(status_code=404, detail="Магазин не найден")

    # Импersonation-токен: роль owner, shop_id цели, но sub = admin's user_id
    # Дополнительный claim impersonated_by позволяет frontend показать баннер
    import jwt as _jwt
    from app.core.config import get_settings
    _cfg = get_settings()
    secret = _cfg.platform_jwt_secret or _cfg.secret_key
    now = datetime.now(timezone.utc)
    ttl = 3600  # 1 час

    payload = {
        "sub": str(ctx.user_id),
        "role": "owner",
        "shop_id": shop_id,
        "email": ctx.email,
        "iat": int(now.timestamp()),
        "exp": int(now.timestamp()) + ttl,
        "jti": str(uuid.uuid4()),
        "impersonated_by": ctx.user_id,
        "impersonated_by_email": ctx.email,
        "impersonated_shop_name": shop.name,
    }
    token = _jwt.encode(payload, secret, algorithm="HS256")

    ip, ua = from_request(request)
    await audit_log(
        session=session,
        actor=ctx,
        action="admin.impersonate",
        entity_type="shop",
        entity_id=str(shop_id),
        after={"shop_name": shop.name, "shop_id": shop_id},
        ip_address=ip,
        user_agent=ua,
    )
    await session.commit()

    logger.warning(
        "IMPERSONATION: admin=%s (%d) → shop=%s (%d)",
        ctx.email, ctx.user_id, shop.name, shop_id,
    )

    return ImpersonateResponse(
        access_token=token,
        shop_id=shop_id,
        shop_name=shop.name,
        expires_in=ttl,
        impersonated_by_email=ctx.email,
    )


# ── Broadcast ─────────────────────────────────────────────────────────────────

@router.get("/broadcast", response_model=list[BroadcastResponse])
async def list_broadcasts(
    active_only: bool = Query(default=False),
    _: PlatformAuthContext = Depends(require_super_admin),
    session: AsyncSession = Depends(get_session),
):
    q = select(PlatformBroadcast).order_by(PlatformBroadcast.created_at.desc())
    if active_only:
        q = q.where(PlatformBroadcast.is_active.is_(True))
    rows = (await session.execute(q)).scalars().all()
    return [
        BroadcastResponse(
            id=r.id, title=r.title, body=r.body,
            is_active=r.is_active, created_by_email=r.created_by_email,
            created_at=r.created_at, expires_at=r.expires_at,
        )
        for r in rows
    ]


@router.post("/broadcast", response_model=BroadcastResponse, status_code=201)
async def create_broadcast(
    data: BroadcastRequest,
    request: Request,
    ctx: PlatformAuthContext = Depends(require_super_admin),
    session: AsyncSession = Depends(get_session),
):
    msg = PlatformBroadcast(
        title=data.title,
        body=data.body,
        created_by_id=ctx.user_id,
        created_by_email=ctx.email,
        is_active=True,
        expires_at=data.expires_at,
    )
    session.add(msg)
    ip, ua = from_request(request)
    await audit_log(
        session=session,
        actor=ctx,
        action="platform.broadcast",
        entity_type="broadcast",
        after={"title": data.title},
        ip_address=ip,
        user_agent=ua,
    )
    await session.commit()
    await session.refresh(msg)
    logger.info("Broadcast created: '%s' by %s", data.title, ctx.email)

    return BroadcastResponse(
        id=msg.id, title=msg.title, body=msg.body,
        is_active=msg.is_active, created_by_email=msg.created_by_email,
        created_at=msg.created_at, expires_at=msg.expires_at,
    )


@router.delete("/broadcast/{broadcast_id}", status_code=204)
async def delete_broadcast(
    broadcast_id: int,
    ctx: PlatformAuthContext = Depends(require_super_admin),
    session: AsyncSession = Depends(get_session),
):
    msg = await session.scalar(
        select(PlatformBroadcast).where(PlatformBroadcast.id == broadcast_id)
    )
    if not msg:
        raise HTTPException(status_code=404, detail="Сообщение не найдено")
    await session.delete(msg)
    await session.commit()


@router.patch("/broadcast/{broadcast_id}/deactivate", status_code=204)
async def deactivate_broadcast(
    broadcast_id: int,
    ctx: PlatformAuthContext = Depends(require_super_admin),
    session: AsyncSession = Depends(get_session),
):
    msg = await session.scalar(
        select(PlatformBroadcast).where(PlatformBroadcast.id == broadcast_id)
    )
    if not msg:
        raise HTTPException(status_code=404, detail="Сообщение не найдено")
    msg.is_active = False
    await session.commit()


# Public endpoint: used by seller panel to check for active broadcasts
@router.get("/broadcast/active", response_model=list[BroadcastResponse], include_in_schema=False)
async def get_active_broadcasts(session: AsyncSession = Depends(get_session)):
    """Без авторизации — используется seller panel при загрузке."""
    now = datetime.now(timezone.utc)
    q = (
        select(PlatformBroadcast)
        .where(
            PlatformBroadcast.is_active.is_(True),
            (PlatformBroadcast.expires_at.is_(None)) | (PlatformBroadcast.expires_at > now),
        )
        .order_by(PlatformBroadcast.created_at.desc())
        .limit(5)
    )
    rows = (await session.execute(q)).scalars().all()
    return [
        BroadcastResponse(
            id=r.id, title=r.title, body=r.body,
            is_active=r.is_active, created_by_email=r.created_by_email,
            created_at=r.created_at, expires_at=r.expires_at,
        )
        for r in rows
    ]


# ── Maintenance ───────────────────────────────────────────────────────────────

@router.get("/maintenance", response_model=MaintenanceResponse)
async def get_maintenance(
    _: PlatformAuthContext = Depends(require_super_admin),
):
    state = await get_maintenance_state()
    if state is None:
        return MaintenanceResponse(active=False, message="")
    return MaintenanceResponse(
        active=state.get("active", False),
        message=state.get("message", ""),
        started_at=state.get("started_at"),
        started_by=state.get("started_by"),
    )


@router.post("/maintenance", response_model=MaintenanceResponse)
async def set_maintenance_mode(
    data: MaintenanceRequest,
    request: Request,
    ctx: PlatformAuthContext = Depends(require_super_admin),
    session: AsyncSession = Depends(get_session),
):
    state = await set_maintenance(
        active=data.active,
        message=data.message,
        started_by=ctx.email,
    )
    ip, ua = from_request(request)
    await audit_log(
        session=session,
        actor=ctx,
        action="platform.maintenance",
        after={"active": data.active, "message": data.message},
        ip_address=ip,
        user_agent=ua,
    )
    await session.commit()
    return MaintenanceResponse(
        active=state["active"],
        message=state["message"],
        started_at=state.get("started_at"),
        started_by=state.get("started_by"),
    )


# ── Feature Flags ─────────────────────────────────────────────────────────────

@router.get("/feature-flags", response_model=list[FeatureFlagResponse])
async def list_feature_flags(
    _: PlatformAuthContext = Depends(require_super_admin),
    session: AsyncSession = Depends(get_session),
):
    rows = (
        await session.execute(
            select(FeatureFlag).order_by(FeatureFlag.key)
        )
    ).scalars().all()
    return [_flag_resp(f) for f in rows]


@router.post("/feature-flags", response_model=FeatureFlagResponse)
async def upsert_feature_flag(
    data: FeatureFlagRequest,
    request: Request,
    ctx: PlatformAuthContext = Depends(require_super_admin),
    session: AsyncSession = Depends(get_session),
):
    """Создаёт флаг или обновляет существующий (по key)."""
    flag = await session.scalar(
        select(FeatureFlag).where(FeatureFlag.key == data.key)
    )
    if flag is None:
        flag = FeatureFlag(
            key=data.key,
            is_enabled=data.is_enabled,
            description=data.description,
            created_by=ctx.email,
        )
        session.add(flag)
    else:
        before = {"is_enabled": flag.is_enabled}
        flag.is_enabled = data.is_enabled
        if data.description is not None:
            flag.description = data.description
        ip, ua = from_request(request)
        await audit_log(
            session=session,
            actor=ctx,
            action="feature_flag.update",
            entity_type="feature_flag",
            entity_id=flag.key,
            before=before,
            after={"is_enabled": data.is_enabled},
            ip_address=ip,
            user_agent=ua,
        )

    await session.commit()
    await session.refresh(flag)
    return _flag_resp(flag)


@router.delete("/feature-flags/{key}", status_code=204)
async def delete_feature_flag(
    key: str,
    ctx: PlatformAuthContext = Depends(require_super_admin),
    session: AsyncSession = Depends(get_session),
):
    flag = await session.scalar(
        select(FeatureFlag).where(FeatureFlag.key == key)
    )
    if not flag:
        raise HTTPException(status_code=404, detail="Feature flag не найден")
    await session.delete(flag)
    await session.commit()


def _flag_resp(f: FeatureFlag) -> FeatureFlagResponse:
    return FeatureFlagResponse(
        id=f.id,
        key=f.key,
        is_enabled=f.is_enabled,
        description=f.description,
        created_by=f.created_by,
        created_at=f.created_at,
        updated_at=f.updated_at,
    )
