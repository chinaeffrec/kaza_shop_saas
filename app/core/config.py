"""
Централизованная конфигурация приложения через pydantic-settings.
Все переменные окружения читаются здесь и только здесь.
"""
from functools import lru_cache
from typing import Any, List

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        # Отключаем авто-JSON-парсинг строк - разбираем сами через field_validator
        env_parse_none_str="null",
    )

    # Environment
    env: str = "development"

    # Database
    db_user: str = "kaza_user"
    db_password: str = "kaza_pass_local"
    db_host: str = "db"
    db_port: int = 5432
    db_name: str = "kaza_shop"

    # Security
    secret_key: str = ""           # Fernet key for field encryption (required in production)
    platform_jwt_secret: str = ""  # JWT signing key (required in production)
    # admin_password kept for backwards compat but unused — do not populate
    admin_password: str = ""

    # Platform super-admin seed (используется только при первом запуске)
    super_admin_email: str = ""
    super_admin_password: str = ""

    # Telegram
    bot_token: str = ""
    admin_tg_id: str = ""
    bot_api_token: str = ""

    # Redis (FSM-хранилище для бота)
    redis_url: str = "redis://redis:6379/0"

    # Мониторинг / алерты
    alert_bot_token: str = ""
    alert_chat_id: str = ""

    # Domain / CORS - хранится как строка, парсится в list через validator
    domain: str = "localhost"
    cors_origins: Any = ""   # Any чтобы pydantic-settings не пытался сам парсить JSON

    # Временная зона для отображения дат (экспорт, отчёты)
    timezone: str = "Europe/Moscow"

    # ── Media storage ─────────────────────────────────────────────────────────────
    # "local": write to media_dir and serve via /media/ (default, single-host)
    # "s3":    upload to S3-compatible bucket (enables multi-host horizontal scaling)
    storage_backend: str = "local"
    media_dir: str = "/app/media"

    # S3-compatible storage (AWS S3, MinIO, Yandex Object Storage, Cloudflare R2…)
    # Required when storage_backend="s3":
    s3_endpoint: str = ""      # e.g. https://s3.amazonaws.com or http://minio:9000
    s3_bucket: str = ""        # bucket name
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_public_url: str = ""    # CDN or public base URL for serving files

    # Бэкапы
    backup_keep_days: int = 14
    # AES-256-CBC key for backup archive encryption (passed to openssl enc -pass)
    backup_encryption_key: str = ""

    # ── High Availability ──────────────────────────────────────────────────────
    # PgBouncer: если задан — engine использует его вместо прямого подключения
    db_pgbouncer_url: str = ""

    # PostgreSQL replica для health-check replica lag (формат: host[:port])
    db_replica_host: str = ""
    db_replica_port: int = 5432

    # Redis Sentinel: "host1:26379,host2:26379,host3:26379"
    redis_sentinel_hosts: str = ""
    redis_sentinel_master: str = "mymaster"
    redis_sentinel_password: str = ""

    # Observability
    log_format: str = "text"          # "text" | "json"
    prometheus_enabled: bool = True   # включает /metrics endpoint

    # Лимиты импорта медиа
    media_import_max_archive_mb: int = 100
    media_import_max_files: int = 2000
    media_import_max_uncompressed_mb: int = 500

    # JWT TTL
    access_token_ttl: int = 3600        # 1 час
    refresh_token_ttl: int = 2592000    # 30 дней

    # Logging
    log_level: str = "INFO"

    # ── Error tracking & APM ───────────────────────────────────────────────────
    # Sentry: set SENTRY_DSN to enable. Leave empty to disable.
    sentry_dsn: str = ""
    # Sentry: fraction of transactions to send as performance traces (0.0 – 1.0)
    sentry_traces_sample_rate: float = 0.05

    # OpenTelemetry OTLP exporter: set OTLP_ENDPOINT to enable (e.g. http://tempo:4318)
    # Compatible with Grafana Tempo, Jaeger, Honeycomb, Datadog OTLP, AWS X-Ray, etc.
    otlp_endpoint: str = ""
    otlp_service_name: str = "kaza-shop"

    @model_validator(mode="after")
    def _validate_production_secrets(self) -> "Settings":
        """Blocks startup when required secrets are missing in production."""
        if self.env != "production":
            return self
        missing: list[str] = []
        if not self.platform_jwt_secret:
            missing.append("PLATFORM_JWT_SECRET")
        if not self.secret_key:
            missing.append("SECRET_KEY")
        if missing:
            raise ValueError(
                f"Required secrets are not set for production environment: "
                f"{', '.join(missing)}. "
                f"Generate them with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        origins = self.cors_origins if isinstance(self.cors_origins, list) else []
        if not origins:
            import warnings
            warnings.warn(
                "CORS_ORIGINS is empty in production. "
                "All cross-origin requests will be blocked. "
                "Set CORS_ORIGINS to the seller-panel and mini-app domains.",
                stacklevel=2,
            )
        if not self.backup_encryption_key:
            import warnings
            warnings.warn(
                "BACKUP_ENCRYPTION_KEY is not set. Backup archives will be stored unencrypted. "
                "A leaked backup file exposes the entire database. "
                "Generate with: python -c \"import secrets; print(secrets.token_hex(32))\"",
                stacklevel=2,
            )
        return self

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors(cls, v: Any) -> List[str]:
        """
        Принимает строку вида:
          "https://example.com"
          "https://a.com,https://b.com"
          ["https://a.com"]   ← уже список (из кода)
        """
        if isinstance(v, list):
            return [o.strip() for o in v if o.strip()]
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            # Если вдруг передали JSON-массив
            if v.startswith("["):
                import json
                try:
                    parsed = json.loads(v)
                    return [o.strip() for o in parsed if o.strip()]
                except Exception:
                    pass
            return [o.strip() for o in v.split(",") if o.strip()]
        return []

    @property
    def cors_origins_list(self) -> List[str]:
        return self.cors_origins if isinstance(self.cors_origins, list) else []

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def effective_alert_token(self) -> str:
        return self.alert_bot_token or self.bot_token

    @property
    def effective_alert_chat(self) -> str:
        return self.alert_chat_id or self.admin_tg_id

    @property
    def is_production(self) -> bool:
        return self.env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
