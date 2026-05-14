"""
Экспорт и импорт базы данных (JSON) и медиафайлов (ZIP).
Используется для переноса на другой сервер и резервного копирования через UI.
"""
import asyncio
import io
import json
import logging
import zipfile
from datetime import datetime, date
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.cache_service import invalidate_catalog_cache

MEDIA_DIR = Path("/app/media")
cfg = get_settings()

logger = logging.getLogger(__name__)

# Порядок экспорта (от независимых таблиц к зависимым)
_EXPORT_ORDER = [
    "shop_settings",
    "categories",
    "subcategories",
    "products",
    "users",
    "faq_items",
    "product_stats",
    "orders",
    "order_items",
    "cart",
]

# Таблицы с автоинкрементным id — последовательности нужно сбросить после импорта
_SEQUENCE_TABLES = [
    "shop_settings",
    "categories",
    "subcategories",
    "products",
    "faq_items",
    "orders",
    "order_items",
    "cart",
]


def _serialize(val):
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    return val


import re as _re
_DT_RE = _re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}')
_D_RE  = _re.compile(r'^\d{4}-\d{2}-\d{2}$')

def _deserialize(val):
    """Convert ISO date/datetime strings back to Python objects for asyncpg."""
    if not isinstance(val, str):
        return val
    if _DT_RE.match(val):
        try:
            return datetime.fromisoformat(val)
        except ValueError:
            pass
    if _D_RE.match(val):
        try:
            return date.fromisoformat(val)
        except ValueError:
            pass
    return val


async def export_db(session: AsyncSession) -> bytes:
    """Читает все таблицы и возвращает JSON-байты."""
    result: dict = {
        "version": "1",
        "exported_at": datetime.utcnow().isoformat(),
        "tables": {},
    }
    for table in _EXPORT_ORDER:
        rows = await session.execute(text(f"SELECT * FROM {table}"))
        result["tables"][table] = [
            {col: _serialize(val) for col, val in zip(rows.keys(), row)}
            for row in rows.fetchall()
        ]
    return json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8")


async def import_db(content: bytes, session: AsyncSession) -> dict:
    """
    Полностью заменяет содержимое базы данными из JSON.
    ВНИМАНИЕ: удаляет все текущие данные перед импортом.
    """
    try:
        payload = json.loads(content.decode("utf-8"))
    except Exception:
        raise HTTPException(400, "Файл повреждён или имеет неверный формат")

    if str(payload.get("version")) != "1":
        raise HTTPException(400, "Неподдерживаемая версия формата. Ожидается version=1.")

    tables = payload.get("tables")
    if not isinstance(tables, dict):
        raise HTTPException(400, "Отсутствует раздел 'tables' в файле импорта")

    try:
        # Одна транзакция: очистка + вставка
        # TRUNCATE RESTART IDENTITY CASCADE сбрасывает последовательности и
        # удаляет связанные строки через CASCADE - безопасно при полном импорте
        await session.execute(text(
            "TRUNCATE "
            + ", ".join(_EXPORT_ORDER)
            + " RESTART IDENTITY CASCADE"
        ))

        counts: dict[str, int] = {}
        for table in _EXPORT_ORDER:
            rows = tables.get(table, [])
            for row in rows:
                if not row:
                    continue
                cols = list(row.keys())
                placeholders = ", ".join(f":{c}" for c in cols)
                parsed = {k: _deserialize(v) for k, v in row.items()}
                await session.execute(
                    text(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})"),
                    parsed,
                )
            counts[table] = len(rows)

        # Сбрасываем последовательности по фактическому MAX(id)
        for table in _SEQUENCE_TABLES:
            await session.execute(text(f"""
                SELECT setval(
                    pg_get_serial_sequence('{table}', 'id'),
                    COALESCE((SELECT MAX(id) FROM {table}), 1)
                )
            """))

        await session.commit()
        logger.info("DB import complete: %s", counts)

        # Сбрасываем кэш каталога в боте - данные изменились
        await invalidate_catalog_cache()

        return {"ok": True, "counts": counts}

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.exception("DB import failed: %s", e)
        raise HTTPException(500, f"Ошибка импорта: {e}")


# ── Медиафайлы ────────────────────────────────────────────────────────────────

async def export_media() -> bytes:
    """Упаковывает /app/media/ в ZIP и возвращает байты. B4: ZIP в отдельном потоке."""
    def _zip() -> bytes:
        buf = io.BytesIO()
        MEDIA_DIR.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in MEDIA_DIR.iterdir():
                if path.is_file():
                    zf.write(path, arcname=path.name)
        buf.seek(0)
        return buf.getvalue()

    return await asyncio.to_thread(_zip)


async def import_media(content: bytes) -> dict:
    """
    Распаковывает ZIP с медиафайлами в /app/media/.
    Существующие файлы перезаписываются, лишние не удаляются.
    B4: разархивация выполняется в отдельном потоке.
    """
    # Быстрые проверки до запуска потока
    max_archive_bytes = cfg.media_import_max_archive_mb * 1024 * 1024
    if len(content) > max_archive_bytes:
        raise HTTPException(413, f"Архив слишком большой. Лимит: {cfg.media_import_max_archive_mb} MB")

    buf = io.BytesIO(content)
    if not zipfile.is_zipfile(buf):
        raise HTTPException(400, "Файл не является ZIP-архивом")

    def _extract() -> int:
        buf.seek(0)
        MEDIA_DIR.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(buf, "r") as zf:
            names = zf.namelist()
            # Защита от path traversal: принимаем только плоские имена файлов
            safe_names = [n for n in names if "/" not in n and "\\" not in n and n]
            if len(safe_names) > cfg.media_import_max_files:
                raise ValueError(f"Слишком много файлов. Лимит: {cfg.media_import_max_files}")
            total_uncompressed = sum(
                info.file_size for info in zf.infolist()
                if info.filename in safe_names
            )
            max_uncompressed = cfg.media_import_max_uncompressed_mb * 1024 * 1024
            if total_uncompressed > max_uncompressed:
                raise ValueError(
                    f"Суммарный размер распаковки превышает лимит "
                    f"{cfg.media_import_max_uncompressed_mb} MB"
                )
            for name in safe_names:
                zf.extract(name, MEDIA_DIR)
            return len(safe_names)

    try:
        extracted = await asyncio.to_thread(_extract)
        logger.info("Media import: extracted %d files", extracted)
        return {"ok": True, "files": extracted}
    except ValueError as e:
        raise HTTPException(413, str(e))
    except Exception as e:
        logger.exception("Media import failed: %s", e)
        raise HTTPException(500, f"Ошибка импорта медиафайлов: {e}")
