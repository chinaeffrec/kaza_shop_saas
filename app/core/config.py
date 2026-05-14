"""
Централизованная конфигурация приложения через pydantic-settings.
Все переменные окружения читаются здесь и только здесь.
"""
from functools import lru_cache
from typing import Any, List

from pydantic import field_validator
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
    secret_key: str = ""          # Legacy: used by old /auth/* routes only
    platform_jwt_secret: str = "" # Platform JWT signing key (required in production)
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

    # Бэкапы
    backup_keep_days: int = 14

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
