import logging
import mimetypes
import signal
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

import app.models
from app.api.routes.cart import router as cart_router
from app.api.routes.catalog import router as catalog_router
from app.api.routes.health import router as health_router, set_app_ready
from app.api.routes.imports import router as import_router
from app.api.routes.orders import router as orders_router
from app.api.routes.audit import router as audit_router
from app.api.routes.members import router as members_router
from app.api.routes.platform_auth import router as platform_auth_router
from app.api.routes.shops import router as shops_router
from app.api.routes.products import router as products_router
from app.api.routes.settings import faq_router, router as settings_router
from app.api.routes.stats import router as stats_router
from app.api.routes.cdek import router as cdek_router
from app.api.routes.customers import router as customers_router
from app.api.routes.promos import router as promos_router
from app.api.routes.users import router as users_router
from app.api.routes.yookassa import router as yookassa_router
from app.api.routes.miniapp import router as miniapp_router
from app.api.routes.billing import router as billing_router
from app.api.routes.reviews import router as reviews_router
from app.api.routes.platform_control import router as platform_control_router
from app.api.routes.profile import router as profile_router
from app.core.config import get_settings
from app.core.middleware import (
    HTTPSRedirectMiddleware,
    MaxBodySizeMiddleware,
    SecurityHeadersMiddleware,
    TraceIDMiddleware,
)
from app.db.alembic_runner import run_migrations_to_head
from app.db.session import SessionLocal
from app.logging_setup import configure_logging

configure_logging("app")
logger = logging.getLogger(__name__)
cfg = get_settings()

# ── Sentry (optional — enabled when SENTRY_DSN is set) ────────────────────────
if cfg.sentry_dsn:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
        import logging as _logging

        sentry_sdk.init(
            dsn=cfg.sentry_dsn,
            environment=cfg.env,
            traces_sample_rate=cfg.sentry_traces_sample_rate,
            send_default_pii=False,  # GDPR: no IP/email in events
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
                # Capture ERROR+ logs as Sentry events; WARNING as breadcrumbs
                LoggingIntegration(level=_logging.WARNING, event_level=_logging.ERROR),
            ],
        )
        logger.info("Sentry initialized (env=%s, sample_rate=%.2f)", cfg.env, cfg.sentry_traces_sample_rate)
    except ImportError:
        logger.warning("sentry-sdk not installed — error tracking disabled")


# ── Lifespan (replaces @app.on_event — FastAPI best practice) ─────────────────
@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    configure_logging("app")
    await run_migrations_to_head()
    await _seed_super_admin()
    set_app_ready()
    logger.info("Kaza Shop API started (lifespan)")
    yield
    # ── Shutdown (SIGTERM / graceful stop) ────────────────────────────────────
    logger.info("Graceful shutdown initiated…")
    # Bot manager is in a separate process (bot service); nothing to stop here.
    # Flush pending logs, close DB pool.
    from app.db.engine import engine as _engine
    await _engine.dispose()
    logger.info("DB engine disposed — shutdown complete")

# Гарантируем корректный MIME-тип для WebP на любом Linux-образе.
# На minimal Docker images системный /etc/mime.types может не включать WebP,
# тогда StaticFiles отдаёт application/octet-stream + nosniff = браузер не
# отображает изображение. Явная регистрация решает.
mimetypes.add_type("image/webp", ".webp")

_OPENAPI_TAGS = [
    {"name": "auth", "description": "Аутентификация платформы: вход, выход, refresh, 2FA (TOTP)"},
    {"name": "profile", "description": "Профиль пользователя: аватар, display name, настройка 2FA"},
    {"name": "products", "description": "Каталог товаров: CRUD, фото, видимость"},
    {"name": "orders", "description": "Жизненный цикл заказов: создание, статусы, история"},
    {"name": "cart", "description": "Корзина покупателя (bot-scoped)"},
    {"name": "settings", "description": "Настройки магазина: лого, CDEK, YooKassa, Mini App"},
    {"name": "stats", "description": "Аналитика: дашборд, выручка, топ товаров"},
    {"name": "billing", "description": "Управление тарифным планом магазина"},
    {"name": "reviews", "description": "Отзывы на товары: публикация, модерация"},
    {"name": "cdek", "description": "Интеграция CDEK v2: расчёт стоимости, тарифы, города"},
    {"name": "yookassa", "description": "Интеграция YooKassa v3: создание платежей, webhook"},
    {"name": "miniapp", "description": "Telegram Mini App: авторизация init-data, каталог"},
    {"name": "members", "description": "RBAC участников магазина: owner / manager / support"},
    {"name": "platform", "description": "Суперадмин: управление магазинами, импersonation"},
    {"name": "health", "description": "Проверка работоспособности сервиса"},
]

app = FastAPI(
    title="Kaza Shop API",
    version="1.0.0",
    description=(
        "## Kaza Shop — Multi-tenant Telegram Bot Storefront API\n\n"
        "Каждый магазин работает на отдельном Telegram-боте, но все боты "
        "используют единый FastAPI-бэкенд (multi-tenant via `shop_id`).\n\n"
        "### Аутентификация\n\n"
        "- **Seller/Admin**: `Authorization: Bearer <access_token>` — JWT HS256, TTL 1 час\n"
        "- **Bot requests**: `X-Bot-Token`, `X-Bot-Shop-Id`, `X-Bot-User-Id` headers\n"
        "- **2FA**: двухшаговый вход — `/platform/auth/login` → challenge token → "
        "`/platform/auth/2fa/verify` → access+refresh tokens\n\n"
        "### Мультиарендность\n\n"
        "`shop_id` всегда берётся из JWT-токена, а не из тела запроса. "
        "Прямая подстановка чужого `shop_id` невозможна (IDOR-защита).\n\n"
        "### Окружения\n\n"
        "| Среда | URL |\n"
        "|---|---|\n"
        "| Development | `http://localhost:8000` |\n"
        "| Staging | `https://staging-api.example.com` |\n"
        "| Production | `https://api.example.com` |"
    ),
    openapi_tags=_OPENAPI_TAGS,
    docs_url="/docs" if not cfg.is_production else None,
    redoc_url="/redoc" if not cfg.is_production else None,
    openapi_url="/openapi.json" if not cfg.is_production else None,
    lifespan=lifespan,
)


# ── OpenTelemetry (optional — enabled when OTLP_ENDPOINT is set) ──────────────
# Instruments FastAPI, SQLAlchemy, and httpx automatically.
# Compatible with Grafana Tempo, Jaeger, Honeycomb, Datadog OTLP, AWS X-Ray.
# Export format: OTLP/HTTP (proto), endpoint e.g. http://tempo:4318/v1/traces
if cfg.otlp_endpoint:
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        _otel_resource = Resource.create({SERVICE_NAME: cfg.otlp_service_name})
        _otel_provider = TracerProvider(resource=_otel_resource)
        _otel_provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=cfg.otlp_endpoint))
        )
        trace.set_tracer_provider(_otel_provider)

        # Instrument FastAPI — wraps each endpoint in a span with HTTP attributes
        FastAPIInstrumentor.instrument_app(
            app,
            excluded_urls="/health,/metrics",
            tracer_provider=_otel_provider,
        )
        # Instrument SQLAlchemy — every DB query becomes a child span
        SQLAlchemyInstrumentor().instrument(tracer_provider=_otel_provider)
        # Instrument httpx — outgoing calls (YooKassa, CDEK) become child spans
        HTTPXClientInstrumentor().instrument(tracer_provider=_otel_provider)

        logger.info(
            "OpenTelemetry tracing enabled → %s (service=%s)",
            cfg.otlp_endpoint,
            cfg.otlp_service_name,
        )
    except ImportError as _otel_err:
        logger.warning("opentelemetry packages not installed — tracing disabled: %s", _otel_err)


@app.exception_handler(NotImplementedError)
async def _not_implemented_handler(request: Request, exc: NotImplementedError) -> JSONResponse:
    """
    Converts unimplemented payment/delivery provider stubs into HTTP 503.
    Without this handler FastAPI would return a raw 500 Internal Server Error,
    leaking a stack trace to the client and revealing which providers are stubs.
    """
    logger.warning("NotImplementedError on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "Этот платёжный провайдер или служба доставки ещё не подключён. "
                            "Обратитесь к владельцу магазина."},
    )


async def _seed_super_admin() -> None:  # noqa: E302
    from app.services.platform_auth_service import seed_super_admin
    async with SessionLocal() as session:
        try:
            await seed_super_admin(session)
        except Exception as exc:
            logger.error("Super admin seed failed: %s", exc)


# ── Middleware ─────────────────────────────────────────────────────────────────
# "app" и "bot" - имена контейнеров внутри Docker-сети
allowed_hosts = ["localhost", "127.0.0.1", "app", "bot"]
if cfg.domain and cfg.domain != "localhost":
    allowed_hosts.append(cfg.domain)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
app.add_middleware(SecurityHeadersMiddleware)
if cfg.is_production:
    app.add_middleware(HTTPSRedirectMiddleware)
from app.core.maintenance import get_maintenance_state, EXCLUDED_PREFIXES
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse as _JSONResponse

class MaintenanceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        if not any(path.startswith(p) for p in EXCLUDED_PREFIXES):
            state = await get_maintenance_state()
            if state:
                return _JSONResponse(
                    status_code=503,
                    content={"detail": state.get("message", "Технические работы"), "maintenance": True},
                    headers={"Retry-After": "300"},
                )
        return await call_next(request)

app.add_middleware(MaintenanceMiddleware)
app.add_middleware(TraceIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
# MaxBodySizeMiddleware is added last → outermost layer → first to see requests.
# Rejects oversized bodies before they reach any other middleware or handler.
app.add_middleware(MaxBodySizeMiddleware)

# ── Static ─────────────────────────────────────────────────────────────────────
for d in (Path("/app/media"), Path("/app/data"), Path("/app/logs")):
    d.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory="/app/media"), name="media")

# ── Routers ───────────────────────────────────────────────────────────────────
# Platform routes (internal admin API) — без версии
app.include_router(health_router)
app.include_router(platform_auth_router)

# ── Prometheus metrics (/metrics) ─────────────────────────────────────────────
if cfg.prometheus_enabled:
    try:
        from prometheus_fastapi_instrumentator import Instrumentator
        Instrumentator(
            should_group_status_codes=True,
            should_ignore_untemplated=True,
            excluded_handlers=["/health", "/metrics"],
        ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
        logger.info("Prometheus metrics endpoint enabled at /metrics")
    except ImportError:
        logger.warning("prometheus-fastapi-instrumentator not installed — /metrics disabled")
app.include_router(shops_router)
app.include_router(members_router)
app.include_router(audit_router)
app.include_router(platform_control_router)

# Tenant + bot routes — версионированные /api/v1/*
# Все внешние клиенты (seller-panel, bot, Mini App) используют этот prefix.
# Это позволяет вводить /api/v2/* без поломки существующих клиентов.
_V1 = "/api/v1"
app.include_router(products_router, prefix=_V1)
app.include_router(cart_router, prefix=_V1)
app.include_router(import_router, prefix=_V1)
app.include_router(catalog_router, prefix=_V1)
app.include_router(orders_router, prefix=_V1)
app.include_router(settings_router, prefix=_V1)
app.include_router(faq_router, prefix=_V1)
app.include_router(stats_router, prefix=_V1)
app.include_router(customers_router, prefix=_V1)
app.include_router(promos_router, prefix=_V1)
app.include_router(cdek_router, prefix=_V1)
app.include_router(yookassa_router, prefix=_V1)
app.include_router(miniapp_router, prefix=_V1)
app.include_router(users_router, prefix=_V1)
app.include_router(billing_router, prefix=_V1)
app.include_router(reviews_router, prefix=_V1)
app.include_router(profile_router, prefix=_V1)
