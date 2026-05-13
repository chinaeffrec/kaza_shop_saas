import logging
import mimetypes
from pathlib import Path
# тест
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles

import app.models
from app.api.routes.auth import router as auth_router
from app.api.routes.cart import router as cart_router
from app.api.routes.catalog import router as catalog_router
from app.api.routes.health import router as health_router, set_app_ready
from app.api.routes.imports import router as import_router
from app.api.routes.orders import router as orders_router
from app.api.routes.platform_auth import router as platform_auth_router
from app.api.routes.shops import router as shops_router
from app.api.routes.products import router as products_router
from app.api.routes.settings import faq_router, router as settings_router
from app.api.routes.stats import router as stats_router
from app.api.routes.users import router as users_router
from app.core.config import get_settings
from app.core.middleware import SecurityHeadersMiddleware
from app.db.alembic_runner import run_migrations_to_head
from app.db.session import SessionLocal
from app.logging_setup import configure_logging

configure_logging("app")
logger = logging.getLogger(__name__)
cfg = get_settings()

# Гарантируем корректный MIME-тип для WebP на любом Linux-образе.
# На minimal Docker images системный /etc/mime.types может не включать WebP,
# тогда StaticFiles отдаёт application/octet-stream + nosniff = браузер не
# отображает изображение. Явная регистрация решает.
mimetypes.add_type("image/webp", ".webp")

app = FastAPI(
    title="Kaza Shop API",
    version="1.0.0",
    docs_url="/docs" if not cfg.is_production else None,
    redoc_url="/redoc" if not cfg.is_production else None,
    openapi_url="/openapi.json" if not cfg.is_production else None,
)


@app.on_event("startup")
async def startup():
    # Uvicorn сбрасывает logging handlers через dictConfig при старте.
    # Повторный вызов восстанавливает файловый обработчик после этого сброса.
    configure_logging("app")
    await run_migrations_to_head()
    await _seed_super_admin()
    set_app_ready()
    logger.info("DB migrations applied. Kaza Shop started.")


async def _seed_super_admin() -> None:
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# ── Static ─────────────────────────────────────────────────────────────────────
for d in (Path("/app/media"), Path("/app/data"), Path("/app/logs")):
    d.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory="/app/media"), name="media")

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(platform_auth_router)
app.include_router(shops_router)
app.include_router(products_router)
app.include_router(cart_router)
app.include_router(import_router)
app.include_router(catalog_router)
app.include_router(orders_router)
app.include_router(settings_router)
app.include_router(faq_router)
app.include_router(stats_router)
app.include_router(users_router)
