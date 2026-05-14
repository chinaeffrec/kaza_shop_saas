"""
Настройка логирования.

Режимы (LOG_FORMAT env var):
  "text" (по умолчанию) — human-readable
  "json"                — структурированный JSON для Loki/ELK

В оба режима добавляется поле trace_id из ContextVar,
который устанавливает TraceIDMiddleware для каждого HTTP-запроса.
"""
import logging
import logging.handlers
import os
import sys
from contextvars import ContextVar
from pathlib import Path

# ContextVar для trace_id — устанавливается middleware на каждый запрос
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="-")

# Пути для файлового лога (перебираем по очереди, берём первый доступный для записи)
_LOG_DIRS = [
    Path("/app/logs"),
    Path("/app/data/logs"),
    Path("/tmp/kaza_logs"),
]


class _TraceIdFilter(logging.Filter):
    """Добавляет поле trace_id из ContextVar в каждый LogRecord."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = trace_id_var.get("-")  # type: ignore[attr-defined]
        return True


def _build_json_formatter() -> logging.Formatter:
    try:
        from pythonjsonlogger import jsonlogger  # type: ignore[import-untyped]

        class _TraceAwareJson(jsonlogger.JsonFormatter):
            def add_fields(self, log_record, record, message_dict):
                super().add_fields(log_record, record, message_dict)
                log_record["trace_id"] = getattr(record, "trace_id", "-")
                log_record["logger"] = record.name

        return _TraceAwareJson(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    except ImportError:
        logging.getLogger(__name__).warning(
            "python-json-logger not installed — using text format"
        )
        return logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | [%(trace_id)s] %(message)s"
        )


def configure_logging(name: str = "app") -> None:
    """Настраивает логирование: консоль + ротируемый файл.

    Безопасно вызывать несколько раз — дублирующие handlers не добавляются.
    Нужно вызывать как при импорте модуля, так и в startup-событии FastAPI,
    потому что uvicorn сбрасывает handlers через dictConfig при своём старте.
    """
    try:
        from app.core.config import get_settings
        cfg = get_settings()
        level_name = cfg.log_level.upper()
        log_format = cfg.log_format.lower()
    except Exception:
        level_name = os.getenv("LOG_LEVEL", "INFO").upper()
        log_format = os.getenv("LOG_FORMAT", "text").lower()

    level = getattr(logging, level_name, logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)

    # Trace-ID filter (добавляется один раз)
    if not any(isinstance(f, _TraceIdFilter) for f in root.filters):
        root.addFilter(_TraceIdFilter())

    if log_format == "json":
        formatter = _build_json_formatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | [%(trace_id)s] %(message)s"
        )

    root = logging.getLogger()
    root.setLevel(level)

    # Консоль — добавляем только если ещё нет stdout-обработчика
    has_stdout = any(
        isinstance(h, logging.StreamHandler)
        and getattr(h, "stream", None) is sys.stdout
        for h in root.handlers
    )
    if not has_stdout:
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(formatter)
        root.addHandler(console)

    # Файловый обработчик — добавляем только если нет ни одного RotatingFileHandler
    has_file = any(isinstance(h, logging.handlers.RotatingFileHandler) for h in root.handlers)
    if not has_file:
        _add_file_handler(root, formatter, name)

    # Приглушаем шумные библиотеки
    for noisy in ("sqlalchemy.engine", "aiogram", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _add_file_handler(
    root: logging.Logger, formatter: logging.Formatter, name: str
) -> None:
    """Пробует создать RotatingFileHandler; при ошибке переходит к следующему пути."""
    for log_dir in _LOG_DIRS:
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"{name}.log"
            # Проверяем доступность на запись до создания handler
            with log_file.open("a") as fh:
                fh.write("")
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10 MB
                backupCount=5,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)
            return
        except (PermissionError, OSError):
            continue
