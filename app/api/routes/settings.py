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

from app.api.routes.auth import get_admin_shop_id, require_auth
from app.api.schemas.settings import (
    FaqCreate, FaqItemResponse, FaqUpdate, SettingsResponse, SettingsUpdate,
)
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
    }


@router.get("/", response_model=SettingsResponse)
async def get_settings(
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_auth),
    shop_id: int = Depends(get_admin_shop_id),
):
    return await svc.read_settings(session, shop_id)


@router.patch("/", response_model=SettingsResponse)
async def update_settings(
    data: SettingsUpdate,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_auth),
    shop_id: int = Depends(get_admin_shop_id),
):
    return await svc.update_settings(data, session, shop_id)


@router.post("/logo")
async def upload_logo(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_auth),
    shop_id: int = Depends(get_admin_shop_id),
):
    return await svc.upload_logo(file, session, shop_id)


@router.delete("/logo")
async def delete_logo(
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_auth),
    shop_id: int = Depends(get_admin_shop_id),
):
    return await svc.delete_logo(session, shop_id)


@router.post("/stamp")
async def upload_stamp(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_auth),
    shop_id: int = Depends(get_admin_shop_id),
):
    return await svc.upload_stamp(file, session, shop_id)


@router.delete("/stamp")
async def delete_stamp(
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_auth),
    shop_id: int = Depends(get_admin_shop_id),
):
    return await svc.delete_stamp(session, shop_id)


@router.post("/payment-qr")
async def upload_payment_qr(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_auth),
    shop_id: int = Depends(get_admin_shop_id),
):
    return await svc.upload_payment_qr(file, session, shop_id)


@router.delete("/payment-qr")
async def delete_payment_qr(
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_auth),
    shop_id: int = Depends(get_admin_shop_id),
):
    return await svc.delete_payment_qr(session, shop_id)


@router.get("/db-export", summary="Экспорт базы данных в JSON")
async def db_export(
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_auth),
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
    _: str = Depends(require_auth),
):
    content = await file.read()
    return await db_svc.import_db(content, session)


@router.get("/media-export", summary="Экспорт медиафайлов (ZIP)")
async def media_export(_: str = Depends(require_auth)):
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
    _: str = Depends(require_auth),
):
    content = await file.read()
    return await db_svc.import_media(content)


@router.get("/logs/download")
async def download_logs(_: str = Depends(require_auth)):
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
    _: str = Depends(require_auth),
    shop_id: int = Depends(get_admin_shop_id),
):
    return await svc.create_faq(data, session, shop_id)


@faq_router.patch("/{item_id}", response_model=FaqItemResponse)
async def update_faq(
    item_id: int,
    data: FaqUpdate,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_auth),
    shop_id: int = Depends(get_admin_shop_id),
):
    return await svc.update_faq(item_id, data, session, shop_id)


@faq_router.delete("/{item_id}")
async def delete_faq(
    item_id: int,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_auth),
    shop_id: int = Depends(get_admin_shop_id),
):
    return await svc.delete_faq(item_id, session, shop_id)
