"""
Сервис загрузки файлов настроек (лого, штамп, QR) и FAQ.
"""
import uuid
from pathlib import Path

import aiofiles
from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.settings import FaqItemResponse, FaqUpdate, SettingsResponse, SettingsUpdate
from app.models.settings import FaqItem, ShopSettings
from app.services.settings_service import get_shop_settings, invalidate_settings_cache

MEDIA_DIR = Path("/app/media")
ALLOWED_IMG = {"image/jpeg", "image/png", "image/webp", "image/svg+xml"}
ALLOWED_IMG_NO_SVG = {"image/jpeg", "image/png", "image/webp"}
MAX_UPLOAD = 5 * 1024 * 1024


def _to_response(s: ShopSettings) -> SettingsResponse:
    return SettingsResponse(
        shop_name=s.shop_name,
        logo_filename=s.logo_filename,
        logo_url=f"/media/{s.logo_filename}" if s.logo_filename else None,
        reviews_enabled=s.reviews_enabled,
        welcome_message=s.welcome_message,
        seller_contact=s.seller_contact,
        admin_contact=s.admin_contact,
        hide_out_of_stock=s.hide_out_of_stock,
        stamp_filename=s.stamp_filename,
        stamp_url=f"/media/{s.stamp_filename}" if s.stamp_filename else None,
        payment_qr_filename=s.payment_qr_filename,
        payment_qr_url=f"/media/{s.payment_qr_filename}" if s.payment_qr_filename else None,
        payment_qr_comment=s.payment_qr_comment,
        legal_name=s.legal_name,
    )


async def read_settings(session: AsyncSession, shop_id: int = 1) -> SettingsResponse:
    s = await get_shop_settings(session, shop_id)
    return _to_response(s)


async def update_settings(
    data: SettingsUpdate, session: AsyncSession, shop_id: int = 1
) -> SettingsResponse:
    s = await get_shop_settings(session, shop_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(s, field, value)
    await session.commit()
    invalidate_settings_cache()
    return _to_response(s)


async def _upload_file(
    s: ShopSettings, field: str, file: UploadFile,
    prefix: str, allowed: set, session: AsyncSession,
) -> str:
    if file.content_type not in allowed:
        raise HTTPException(400, f"Unsupported type: {file.content_type}")
    content = await file.read()
    if len(content) > MAX_UPLOAD:
        raise HTTPException(413, "File too large. Max 5 MB.")
    old_fn = getattr(s, field, None)
    if old_fn:
        old = MEDIA_DIR / old_fn
        if old.exists():
            old.unlink()
    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else "png"
    filename = f"{prefix}_{uuid.uuid4().hex[:8]}.{ext}"
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(MEDIA_DIR / filename, "wb") as f:
        await f.write(content)
    setattr(s, field, filename)
    await session.commit()
    invalidate_settings_cache()
    return filename


async def _delete_file(s: ShopSettings, field: str, session: AsyncSession) -> None:
    fn = getattr(s, field, None)
    if fn:
        p = MEDIA_DIR / fn
        if p.exists():
            p.unlink()
        setattr(s, field, None)
        await session.commit()
        invalidate_settings_cache()


async def upload_logo(file: UploadFile, session: AsyncSession, shop_id: int = 1) -> dict:
    s = await get_shop_settings(session, shop_id)
    fn = await _upload_file(s, "logo_filename", file, "logo", ALLOWED_IMG, session)
    return {"logo_url": f"/media/{fn}"}


async def delete_logo(session: AsyncSession, shop_id: int = 1) -> dict:
    s = await get_shop_settings(session, shop_id)
    await _delete_file(s, "logo_filename", session)
    return {"status": "ok"}


async def upload_stamp(file: UploadFile, session: AsyncSession, shop_id: int = 1) -> dict:
    s = await get_shop_settings(session, shop_id)
    fn = await _upload_file(s, "stamp_filename", file, "stamp", ALLOWED_IMG_NO_SVG, session)
    return {"stamp_url": f"/media/{fn}"}


async def delete_stamp(session: AsyncSession, shop_id: int = 1) -> dict:
    s = await get_shop_settings(session, shop_id)
    await _delete_file(s, "stamp_filename", session)
    return {"status": "ok"}


async def upload_payment_qr(file: UploadFile, session: AsyncSession, shop_id: int = 1) -> dict:
    s = await get_shop_settings(session, shop_id)
    fn = await _upload_file(s, "payment_qr_filename", file, "payment_qr", ALLOWED_IMG_NO_SVG, session)
    return {"payment_qr_url": f"/media/{fn}"}


async def delete_payment_qr(session: AsyncSession, shop_id: int = 1) -> dict:
    s = await get_shop_settings(session, shop_id)
    await _delete_file(s, "payment_qr_filename", session)
    return {"status": "ok"}


# ── FAQ ────────────────────────────────────────────────────────────────────────

def _faq_to_response(f: FaqItem) -> FaqItemResponse:
    return FaqItemResponse(
        id=f.id, question=f.question, answer=f.answer,
        sort_order=f.sort_order, is_active=f.is_active,
    )


async def list_faq(session: AsyncSession, shop_id: int = 1) -> list[FaqItemResponse]:
    res = await session.execute(
        select(FaqItem)
        .where(FaqItem.shop_id == shop_id)
        .order_by(FaqItem.sort_order.asc(), FaqItem.id.asc())
    )
    return [_faq_to_response(f) for f in res.scalars().all()]


async def create_faq(data, session: AsyncSession, shop_id: int = 1) -> FaqItemResponse:
    item = FaqItem(**data.model_dump(), shop_id=shop_id)
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return _faq_to_response(item)


async def update_faq(
    item_id: int, data: FaqUpdate, session: AsyncSession, shop_id: int = 1
) -> FaqItemResponse:
    res = await session.execute(
        select(FaqItem).where(FaqItem.id == item_id, FaqItem.shop_id == shop_id)
    )
    item = res.scalar_one_or_none()
    if not item:
        raise HTTPException(404, "Not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(item, k, v)
    await session.commit()
    return _faq_to_response(item)


async def delete_faq(item_id: int, session: AsyncSession, shop_id: int = 1) -> dict:
    res = await session.execute(
        select(FaqItem).where(FaqItem.id == item_id, FaqItem.shop_id == shop_id)
    )
    item = res.scalar_one_or_none()
    if not item:
        raise HTTPException(404, "Not found")
    await session.delete(item)
    await session.commit()
    return {"status": "deleted"}
