import logging
import logging.handlers
import os
import sys
from pathlib import Path

# Пути для файлового лога (перебираем по очереди, берём первый доступный для записи)
_LOG_DIRS = [
    Path("/app/logs"),
    Path("/app/data/logs"),
    Path("/tmp/kaza_logs"),
]


def configure_logging(name: str = "app") -> None:
    """Настраивает логирование: консоль + ротируемый файл.

    Безопасно вызывать несколько раз — дублирующие handlers не добавляются.
    Нужно вызывать как при импорте модуля, так и в startup-событии FastAPI,
    потому что uvicorn сбрасывает handlers через dictConfig при своём старте.
    """
    try:
        from app.core.config import get_settings
        level_name = get_settings().log_level.upper()
    except Exception:
        level_name = os.getenv("LOG_LEVEL", "INFO").upper()

    level = getattr(logging, level_name, logging.INFO)
    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    formatter = logging.Formatter(fmt)

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
