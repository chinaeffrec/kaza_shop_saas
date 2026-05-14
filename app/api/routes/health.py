"""
Health check endpoints.
GET /         - редирект на панель управления (для удобства)
GET /health   - быстрая проверка (nginx, Docker healthcheck)
GET /health/detail - детальная (только для авторизованных)
"""
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_owner_shop_id
from app.core.config import get_settings
from app.db.session import get_session
from app.core.circuit_breaker import cdek_cb, yookassa_cb

router = APIRouter(tags=["system"])
_start_time = time.monotonic()
_cfg = get_settings()

# Флаг выставляется из main.py после завершения миграций.
# До этого /health возвращает 503 — Docker не помечает контейнер healthy
# раньше времени и не пускает трафик пока приложение ещё не готово.
_app_ready: bool = False


def set_app_ready() -> None:
    global _app_ready
    _app_ready = True


@router.get("/", include_in_schema=False)
async def root():
    """Корневой URL - перенаправляем в панель управления."""
    if _cfg.domain and _cfg.domain != "localhost":
        url = f"https://{_cfg.domain}"
    else:
        url = "http://localhost:5173"
    return RedirectResponse(url=url, status_code=302)


@router.get("/health")
async def health():
    """Публичный - для nginx, Docker healthcheck, внешнего мониторинга."""
    from fastapi import Response
    if not _app_ready:
        return Response(
            content='{"status":"starting"}',
            status_code=503,
            media_type="application/json",
        )
    return {"status": "ok", "ts": datetime.now(timezone.utc).isoformat()}


@router.get("/health/detail")
async def health_detail(
    session: AsyncSession = Depends(get_session),
    _: int = Depends(get_owner_shop_id),
):
    """Детальный статус - только для администратора."""
    uptime_sec = int(time.monotonic() - _start_time)
    checks: dict = {}

    # БД
    db_ok = False
    db_latency_ms = -1
    try:
        t0 = time.monotonic()
        await session.execute(text("SELECT 1"))
        db_latency_ms = int((time.monotonic() - t0) * 1000)
        db_ok = True
    except Exception as e:
        checks["database"] = {"status": "error", "error": str(e)}

    if db_ok:
        checks["database"] = {"status": "ok", "latency_ms": db_latency_ms}

    # Диск
    import shutil
    try:
        usage = shutil.disk_usage("/app/media")
        disk_pct = int(usage.used / usage.total * 100)
        checks["disk"] = {
            "status": "warn" if disk_pct > 85 else "ok",
            "used_pct": disk_pct,
            "free_gb": round(usage.free / 1024 ** 3, 1),
        }
    except Exception:
        checks["disk"] = {"status": "unknown"}

    # RAM
    try:
        with open("/proc/meminfo") as f:
            meminfo = {
                line.split(":")[0]: int(line.split(":")[1].strip().split()[0])
                for line in f if ":" in line
            }
        free_mb = meminfo.get("MemAvailable", 0) // 1024
        checks["memory"] = {
            "status": "warn" if free_mb < 100 else "ok",
            "free_mb": free_mb,
        }
    except Exception:
        checks["memory"] = {"status": "unknown"}

    # Replica lag (если задан DB_REPLICA_HOST)
    replica_host = _cfg.db_replica_host
    if replica_host:
        try:
            from sqlalchemy.ext.asyncio import create_async_engine
            replica_url = (
                f"postgresql+asyncpg://{_cfg.db_user}:{_cfg.db_password}"
                f"@{replica_host}:{_cfg.db_replica_port}/{_cfg.db_name}"
            )
            rep_engine = create_async_engine(replica_url, pool_size=1, max_overflow=0, pool_pre_ping=False)
            async with rep_engine.connect() as conn:
                lag = await conn.scalar(
                    text(
                        "SELECT COALESCE(EXTRACT(EPOCH FROM (NOW() - pg_last_xact_replay_timestamp())), 0)"
                    )
                )
            await rep_engine.dispose()
            lag_sec = float(lag or 0)
            checks["replica"] = {
                "status": "warn" if lag_sec > 30 else "ok",
                "lag_sec": round(lag_sec, 1),
            }
        except Exception as e:
            checks["replica"] = {"status": "error", "error": str(e)}
    else:
        checks["replica"] = {"status": "not_configured"}

    # External service circuit breakers
    checks["circuit_breakers"] = {
        "cdek":      cdek_cb.status(),
        "yookassa":  yookassa_cb.status(),
    }

    overall = "ok"
    for c in checks.values():
        if isinstance(c, dict) and c.get("status") == "error":
            overall = "error"
            break
        if isinstance(c, dict) and c.get("status") == "warn" and overall != "error":
            overall = "warn"

    return {
        "status": overall,
        "uptime_sec": uptime_sec,
        "uptime_human": _fmt_uptime(uptime_sec),
        "ts": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }


def _fmt_uptime(sec: int) -> str:
    d, rem = divmod(sec, 86400)
    h, rem = divmod(rem, 3600)
    m, s = divmod(rem, 60)
    parts = []
    if d: parts.append(f"{d}д")
    if h: parts.append(f"{h}ч")
    if m: parts.append(f"{m}м")
    parts.append(f"{s}с")
    return " ".join(parts)
