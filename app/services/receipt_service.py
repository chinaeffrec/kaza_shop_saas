"""PDF-чек: генерация и отправка покупателю."""
import os
import uuid as uuid_mod
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdf_canvas

from app.models.order import ORDER_STATUSES, Order, OrderItem
from app.models.settings import ShopSettings
from app.models.user import User
from app.services.order_service import _fmt_price, _send_document_telegram
from app.services.settings_service import get_shop_settings

MEDIA_DIR = Path("/app/media")
DEJAVU = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
DEJAVU_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

if os.path.exists(DEJAVU):
    pdfmetrics.registerFont(TTFont("DejaVu", DEJAVU))
    pdfmetrics.registerFont(TTFont("DejaVuBold", DEJAVU_BOLD))
    FONT = "DejaVu"
    FONT_BOLD = "DejaVuBold"
else:
    FONT = "Helvetica"
    FONT_BOLD = "Helvetica-Bold"

ORDER_STATUS_MARKUP = {
    "inline_keyboard": [[{"text": "🏠 Перейти в меню", "callback_data": "menu_back"}]]
}


async def generate_and_send_receipt(order_id: int, session: AsyncSession) -> dict:
    res = await session.execute(select(Order).where(Order.id == order_id))
    order = res.scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Order not found")

    items = (await session.execute(
        select(OrderItem).where(OrderItem.order_id == order_id)
    )).scalars().all()

    shop_id = getattr(order, "shop_id", None) or 1
    user = (await session.execute(
        select(User).where(User.telegram_id == order.user_id, User.shop_id == shop_id)
    )).scalar_one_or_none()

    shop = await get_shop_settings(session, shop_id)
    shop_name = shop.shop_name or "Kaza Shop"
    buyer_name = ""
    if user:
        buyer_name = (f"{user.first_name or ''} {user.last_name or ''}".strip()
                      or user.username or f"ID:{order.user_id}")

    receipt_id = uuid_mod.uuid4().hex[:8]
    filename = f"receipt_{order_id}_{receipt_id}.pdf"
    filepath = MEDIA_DIR / filename
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)

    c = pdf_canvas.Canvas(str(filepath), pagesize=A5)
    w, h = A5
    y = h - 15 * mm

    c.setFont(FONT_BOLD, 14)
    c.drawString(15 * mm, y, shop_name)
    y -= 8 * mm
    c.setFont(FONT_BOLD, 12)
    c.drawString(15 * mm, y, f"Товарный чек №{order.id}")
    y -= 6 * mm
    c.setFont(FONT, 9)
    c.drawString(15 * mm, y, f"Дата: {order.created_at.strftime('%d.%m.%Y %H:%M')}" if order.created_at else "Дата: —")
    y -= 5 * mm
    c.line(15 * mm, y, w - 15 * mm, y)
    y -= 5 * mm

    c.setFont(FONT_BOLD, 10)
    c.drawString(15 * mm, y, "Покупатель:")
    y -= 5 * mm
    c.setFont(FONT, 10)
    c.drawString(15 * mm, y, buyer_name or f"ID:{order.user_id}")
    if order.delivery_address:
        y -= 5 * mm
        c.drawString(15 * mm, y, f"Адрес: {order.delivery_address}")
    y -= 7 * mm

    c.setFont(FONT_BOLD, 9)
    for col, txt in [("15mm", "Товар"), ("85mm", "Цена"), ("110mm", "Кол"), ("125mm", "Сумма")]:
        c.drawString(float(col.replace("mm", "")) * mm, y, txt)
    y -= 5 * mm
    c.line(15 * mm, y, w - 15 * mm, y)
    y -= 3 * mm

    c.setFont(FONT, 9)
    for item in items:
        c.drawString(15 * mm, y, item.name[:40])
        c.drawString(85 * mm, y, _fmt_price(item.price))
        c.drawString(110 * mm, y, str(item.quantity))
        c.drawString(125 * mm, y, _fmt_price(item.price * item.quantity))
        y -= 5 * mm

    y -= 2 * mm
    c.line(15 * mm, y, w - 15 * mm, y)
    y -= 5 * mm
    c.setFont(FONT_BOLD, 11)
    c.drawString(15 * mm, y, f"Итого: {_fmt_price(order.total)}")
    y -= 5 * mm
    c.setFont(FONT, 9)
    c.drawString(15 * mm, y, f"Статус: {ORDER_STATUSES.get(order.status, order.status)}")
    y -= 8 * mm

    seller_label = shop.legal_name or shop.seller_contact or shop_name
    c.setFont(FONT_BOLD, 9)
    c.drawString(15 * mm, y, "Продавец:")
    y -= 5 * mm
    c.setFont(FONT, 9)
    for line in seller_label.split("\n"):
        c.drawString(15 * mm, y, line[:80])
        y -= 5 * mm

    if shop.stamp_filename:
        stamp_path = MEDIA_DIR / shop.stamp_filename
        if stamp_path.exists():
            try:
                c.drawImage(str(stamp_path), w - 40 * mm, y - 15 * mm,
                            width=25 * mm, height=25 * mm,
                            preserveAspectRatio=True, mask="auto")
            except Exception:
                pass
    y -= 12 * mm
    c.line(15 * mm, y, w - 15 * mm, y)
    y -= 6 * mm
    c.setFont(FONT, 8)
    c.drawString(15 * mm, y, "Спасибо за покупку!")
    c.save()

    caption = f"🧾 <b>Чек по заказу #{order.id}</b>\nСумма: {_fmt_price(order.total)}\nСпасибо за покупку!"
    sent = await _send_document_telegram(order.user_id, str(filepath), caption, ORDER_STATUS_MARKUP)

    # Удаляем временный PDF после отправки - он не нужен на диске
    try:
        filepath.unlink(missing_ok=True)
    except Exception:
        pass

    return {"status": "ok", "sent_to_buyer": sent}
