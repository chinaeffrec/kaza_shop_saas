"""
Сервис загрузки файлов настроек (лого, штамп, QR) и FAQ.
"""
import uuid

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.settings import FaqItemResponse, FaqUpdate, SettingsResponse, SettingsUpdate
from app.core.security import check_image_magic
from app.core.storage import get_storage
from app.models.settings import FaqItem, ShopSettings
from app.services.settings_service import get_shop_settings, invalidate_settings_cache
ALLOWED_IMG = {"image/jpeg", "image/png", "image/webp", "image/svg+xml"}
ALLOWED_IMG_NO_SVG = {"image/jpeg", "image/png", "image/webp"}
MAX_UPLOAD = 5 * 1024 * 1024


def _mask_secret(value: str | None) -> str | None:
    """Возвращает маскированный секрет вида '••••••last4' или None."""
    if not value:
        return None
    if len(value) <= 4:
        return "••••"
    return "••••" + value[-4:]


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
        # CDEK
        cdek_enabled=bool(getattr(s, "cdek_enabled", False)),
        cdek_test_mode=bool(getattr(s, "cdek_test_mode", True)),
        cdek_client_id=getattr(s, "cdek_client_id", None),
        cdek_client_secret=_mask_secret(getattr(s, "cdek_client_secret", None)),
        cdek_sender_city_code=getattr(s, "cdek_sender_city_code", None),
        cdek_sender_address=getattr(s, "cdek_sender_address", None),
        cdek_default_weight=getattr(s, "cdek_default_weight", 500) or 500,
        # YooKassa
        yookassa_enabled=bool(getattr(s, "yookassa_enabled", False)),
        yookassa_shop_id=getattr(s, "yookassa_shop_id", None),
        yookassa_secret_key=_mask_secret(getattr(s, "yookassa_secret_key", None)),
        yookassa_return_url=getattr(s, "yookassa_return_url", None),
        # Mini App
        miniapp_url=getattr(s, "miniapp_url", None),
        # i18n
        default_language=getattr(s, "default_language", "ru") or "ru",
        shop_languages=getattr(s, "shop_languages", "ru") or "ru",
    )


async def read_settings(session: AsyncSession, shop_id: int = 1) -> SettingsResponse:
    s = await get_shop_settings(session, shop_id)
    return _to_response(s)


async def update_settings(
    data: SettingsUpdate, session: AsyncSession, shop_id: int = 1
) -> SettingsResponse:
    s = await get_shop_settings(session, shop_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        # Не перезаписываем секреты маскированными значениями
        if field in ("cdek_client_secret", "yookassa_secret_key") and value and value.startswith("••••"):
            continue
        setattr(s, field, value)
    await session.commit()
    invalidate_settings_cache()
    return _to_response(s)


def _check_svg_magic(content: bytes) -> bool:
    """Minimal SVG content check — must start with XML/SVG markers."""
    head = content.lstrip()[:256].lower()
    return b"<svg" in head or (b"<?xml" in head and b"svg" in head)


async def _upload_file(
    s: ShopSettings, field: str, file: UploadFile,
    prefix: str, allowed: set, session: AsyncSession,
) -> str:
    if file.content_type not in allowed:
        raise HTTPException(400, f"Unsupported type: {file.content_type}")
    content = await file.read()
    if len(content) > MAX_UPLOAD:
        raise HTTPException(413, "File too large. Max 5 MB.")

    # Validate actual file content (magic bytes), not just the declared content-type
    if file.content_type == "image/svg+xml":
        if not _check_svg_magic(content):
            raise HTTPException(400, "Invalid SVG file content.")
        ext = "svg"
    else:
        detected_fmt = check_image_magic(content)  # raises HTTPException on mismatch
        # Map detected format name to canonical file extension
        ext = "jpg" if detected_fmt == "jpeg" else detected_fmt

    storage = get_storage()
    old_fn = getattr(s, field, None)
    if old_fn:
        await storage.delete(old_fn)
    filename = f"{prefix}_{uuid.uuid4().hex[:8]}.{ext}"
    await storage.save(filename, content, file.content_type or "application/octet-stream")
    setattr(s, field, filename)
    await session.commit()
    invalidate_settings_cache()
    return storage.url(filename)


async def _delete_file(s: ShopSettings, field: str, session: AsyncSession) -> None:
    fn = getattr(s, field, None)
    if fn:
        await get_storage().delete(fn)
        setattr(s, field, None)
        await session.commit()
        invalidate_settings_cache()


async def upload_logo(file: UploadFile, session: AsyncSession, shop_id: int = 1) -> dict:
    s = await get_shop_settings(session, shop_id)
    url = await _upload_file(s, "logo_filename", file, "logo", ALLOWED_IMG, session)
    return {"logo_url": url}


async def delete_logo(session: AsyncSession, shop_id: int = 1) -> dict:
    s = await get_shop_settings(session, shop_id)
    await _delete_file(s, "logo_filename", session)
    return {"status": "ok"}


async def upload_stamp(file: UploadFile, session: AsyncSession, shop_id: int = 1) -> dict:
    s = await get_shop_settings(session, shop_id)
    url = await _upload_file(s, "stamp_filename", file, "stamp", ALLOWED_IMG_NO_SVG, session)
    return {"stamp_url": url}


async def delete_stamp(session: AsyncSession, shop_id: int = 1) -> dict:
    s = await get_shop_settings(session, shop_id)
    await _delete_file(s, "stamp_filename", session)
    return {"status": "ok"}


async def upload_payment_qr(file: UploadFile, session: AsyncSession, shop_id: int = 1) -> dict:
    s = await get_shop_settings(session, shop_id)
    url = await _upload_file(s, "payment_qr_filename", file, "payment_qr", ALLOWED_IMG_NO_SVG, session)
    return {"payment_qr_url": url}


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
