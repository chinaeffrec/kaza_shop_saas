"""Роуты настроек - только HTTP-слой."""
import os
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask

from app.api.deps import require_shop_id
from app.api.schemas.settings import (
    FaqCreate, FaqItemResponse, FaqUpdate, SettingsResponse, SettingsUpdate,
)
from app.core.rbac import Perm
from app.core.security import validate_url
from app.db.session import get_session
from app.services import settings_service_ext as svc
from app.services import db_transfer_service as db_svc

router = APIRouter(prefix="/settings", tags=["settings"])
_LOG_DIRS = [Path("/app/logs"), Path("/app/data/logs"), Path("/tmp/kaza_logs")]


def _bot_shop_id(x_bot_shop_id: Optional[int] = Header(default=None, alias="X-Bot-Shop-Id")) -> int:
    return x_bot_shop_id if x_bot_shop_id is not None else 1


@router.get("/public")
async def get_public_settings(
    session: AsyncSession = Depends(get_session),
    shop_id: int = Depends(_bot_shop_id),
):
    """Публичный эндпоинт для бота — только безопасные поля."""
    s = await svc.read_settings(session, shop_id)
    return {
        "shop_name": s.shop_name,
        "welcome_message": s.welcome_message,
        "hide_out_of_stock": s.hide_out_of_stock,
        "reviews_enabled": s.reviews_enabled,
        "payment_qr_url": s.payment_qr_url,
        "payment_qr_comment": s.payment_qr_comment,
        "seller_contact": s.seller_contact,
        "cdek_enabled": s.cdek_enabled,
        "yookassa_enabled": s.yookassa_enabled,
        "miniapp_url": s.miniapp_url,
        "default_language": s.default_language or "ru",
        "shop_languages": s.shop_languages or "ru",
    }


@router.get("/", response_model=SettingsResponse)
async def get_settings(
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.SETTINGS_READ),
):
    return await svc.read_settings(session, shop_id)


@router.patch("/", response_model=SettingsResponse)
async def update_settings(
    data: SettingsUpdate,
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.SETTINGS_WRITE),
):
    # SSRF prevention: validate miniapp_url before persisting
    if data.miniapp_url:
        data = data.model_copy(
            update={"miniapp_url": validate_url(data.miniapp_url, field_name="miniapp_url")}
        )
    # Validate yookassa_return_url similarly
    if data.yookassa_return_url:
        data = data.model_copy(
            update={"yookassa_return_url": validate_url(
                data.yookassa_return_url, field_name="yookassa_return_url"
            )}
        )
    return await svc.update_settings(data, session, shop_id)


@router.post("/logo")
async def upload_logo(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.SETTINGS_WRITE),
):
    return await svc.upload_logo(file, session, shop_id)


@router.delete("/logo")
async def delete_logo(
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.SETTINGS_WRITE),
):
    return await svc.delete_logo(session, shop_id)


@router.post("/stamp")
async def upload_stamp(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.SETTINGS_WRITE),
):
    return await svc.upload_stamp(file, session, shop_id)


@router.delete("/stamp")
async def delete_stamp(
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.SETTINGS_WRITE),
):
    return await svc.delete_stamp(session, shop_id)


@router.post("/payment-qr")
async def upload_payment_qr(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.SETTINGS_WRITE),
):
    return await svc.upload_payment_qr(file, session, shop_id)


@router.delete("/payment-qr")
async def delete_payment_qr(
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.SETTINGS_WRITE),
):
    return await svc.delete_payment_qr(session, shop_id)


@router.get("/db-export", summary="Экспорт базы данных в JSON")
async def db_export(
    session: AsyncSession = Depends(get_session),
    _: int = require_shop_id(Perm.SETTINGS_DESTRUCTIVE),
):
    content = await db_svc.export_db(session)
    filename = f"kaza_db_{datetime.now().strftime('%Y-%m-%d')}.json"
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/db-import", summary="Импорт базы данных из JSON")
async def db_import(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    _: int = require_shop_id(Perm.SETTINGS_DESTRUCTIVE),
    x_confirm: Optional[str] = Header(default=None, alias="X-Confirm-Destructive"),
):
    # A5: разрушительная операция требует явного подтверждения
    if x_confirm != "yes":
        raise HTTPException(
            status_code=400,
            detail="Это действие необратимо. Передайте заголовок X-Confirm-Destructive: yes",
        )
    content = await file.read()
    return await db_svc.import_db(content, session)


@router.get("/media-export", summary="Экспорт медиафайлов (ZIP)")
async def media_export(_: int = require_shop_id(Perm.SETTINGS_DESTRUCTIVE)):
    content = await db_svc.export_media()
    filename = f"kaza_media_{datetime.now().strftime('%Y-%m-%d')}.zip"
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/media-import", summary="Импорт медиафайлов из ZIP")
async def media_import(
    file: UploadFile = File(...),
    _: int = require_shop_id(Perm.SETTINGS_DESTRUCTIVE),
    x_confirm: Optional[str] = Header(default=None, alias="X-Confirm-Destructive"),
):
    # A5: перезапись медиафайлов требует явного подтверждения
    if x_confirm != "yes":
        raise HTTPException(
            status_code=400,
            detail="Это действие перезапишет медиафайлы. Передайте заголовок X-Confirm-Destructive: yes",
        )
    content = await file.read()
    return await db_svc.import_media(content)


@router.get("/logs/download")
async def download_logs(_: int = require_shop_id(Perm.SETTINGS_READ)):
    log_files = []
    for logs_dir in _LOG_DIRS:
        if logs_dir.exists():
            log_files.extend(p for p in logs_dir.glob("*.log*") if p.is_file())
    log_files = sorted(log_files, key=lambda p: p.stat().st_mtime, reverse=True)
    if not log_files:
        raise HTTPException(404, "Логи ещё не созданы")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    tmp.close()
    with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as arc:
        for p in log_files:
            arc.write(p, arcname=p.name)
    filename = f"kaza-logs-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"
    return FileResponse(
        tmp.name, media_type="application/zip", filename=filename,
        background=BackgroundTask(os.unlink, tmp.name),
    )


# ── FAQ ───────────────────────────────────────────────────────────────────────
faq_router = APIRouter(prefix="/faq", tags=["faq"])


@faq_router.get("/", response_model=list[FaqItemResponse])
async def list_faq(
    session: AsyncSession = Depends(get_session),
    shop_id: int = Depends(_bot_shop_id),
):
    """Публичный — используется ботом."""
    return await svc.list_faq(session, shop_id)


@faq_router.post("/", response_model=FaqItemResponse)
async def create_faq(
    data: FaqCreate,
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.FAQ_WRITE),
):
    return await svc.create_faq(data, session, shop_id)


@faq_router.patch("/{item_id}", response_model=FaqItemResponse)
async def update_faq(
    item_id: int,
    data: FaqUpdate,
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.FAQ_WRITE),
):
    return await svc.update_faq(item_id, data, session, shop_id)


@faq_router.delete("/{item_id}")
async def delete_faq(
    item_id: int,
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.FAQ_WRITE),
):
    return await svc.delete_faq(item_id, session, shop_id)
