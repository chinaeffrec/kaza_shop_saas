"""
Бизнес-логика интеграции с СДЭК.

Связка: ShopSettings ← cdek_client_id/secret → cdek_client.py → СДЭК API.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations import cdek_client as api
from app.integrations.cdek_client import CdekError
from app.models.order import Order
from app.services.settings_service import get_shop_settings

logger = logging.getLogger(__name__)


# ── Auth helper ───────────────────────────────────────────────────────────────

async def _token(shop_id: int, session: AsyncSession) -> tuple[str, bool]:
    """Возвращает (access_token, is_test). Бросает HTTPException если CDEK не настроен."""
    cfg = await get_shop_settings(session, shop_id)

    if not getattr(cfg, "cdek_enabled", False):
        raise HTTPException(400, "CDEK не включён в настройках магазина")
    if not cfg.cdek_client_id or not cfg.cdek_client_secret:
        raise HTTPException(400, "CDEK: не заданы client_id или client_secret в настройках")

    test = bool(getattr(cfg, "cdek_test_mode", True))
    try:
        token = await api.get_token(
            cfg.cdek_client_id,
            cfg.cdek_client_secret,
            shop_id=shop_id,
            test=test,
        )
    except CdekError as exc:
        logger.error("CDEK auth failed for shop_id=%s: %s", shop_id, exc)
        raise HTTPException(502, f"Ошибка авторизации CDEK: {exc}") from exc

    return token, test


# ── Public service methods ────────────────────────────────────────────────────

async def search_cities(
    city_name: str,
    shop_id: int,
    session: AsyncSession,
) -> list[dict]:
    """Поиск городов СДЭК по части названия."""
    token, test = await _token(shop_id, session)
    try:
        raw = await api.search_cities(token, city_name, test=test)
    except CdekError as exc:
        raise HTTPException(502, str(exc)) from exc

    result = []
    for item in raw:
        result.append({
            "code": item.get("code"),
            "city": item.get("city", ""),
            "region": item.get("region", ""),
            "country_code": item.get("country_code", "RU"),
        })
    return result


async def get_pvz_list(
    city_code: int,
    shop_id: int,
    session: AsyncSession,
) -> dict:
    """Список ПВЗ в городе."""
    token, test = await _token(shop_id, session)

    # Получаем название города попутно с поиском
    city_name = str(city_code)
    try:
        cities = await api.search_cities(token, str(city_code), test=test, limit=1)
        if cities:
            city_name = cities[0].get("city", str(city_code))
    except CdekError:
        pass

    try:
        points = await api.get_pvz_list(token, city_code, test=test)
    except CdekError as exc:
        raise HTTPException(502, str(exc)) from exc

    from app.api.schemas.cdek import PvzPoint, PvzListResponse
    return PvzListResponse(
        items=[PvzPoint(**p) for p in points],
        total=len(points),
        city_code=city_code,
        city_name=city_name,
    )


async def calculate_tariff(
    to_city_code: int,
    weight_grams: int,
    shop_id: int,
    session: AsyncSession,
) -> dict:
    """Расчёт стоимости доставки из города магазина до to_city_code."""
    token, test = await _token(shop_id, session)
    cfg = await get_shop_settings(session, shop_id)

    from_city = getattr(cfg, "cdek_sender_city_code", None)
    if not from_city:
        raise HTTPException(400, "CDEK: не задан город отправки в настройках магазина")

    try:
        result = await api.calculate_tariff(
            token, from_city, to_city_code, weight_grams, test=test
        )
    except CdekError as exc:
        raise HTTPException(502, str(exc)) from exc

    return result


async def create_shipment(
    order_id: int,
    pvz_code: str,
    receiver_name: str,
    receiver_phone: str,
    weight_grams: int,
    comment: str,
    shop_id: int,
    session: AsyncSession,
) -> dict:
    """
    Создаёт заявку СДЭК для указанного заказа.
    Сохраняет cdek_order_uuid и pvz_address в Order.
    """
    token, test = await _token(shop_id, session)
    cfg = await get_shop_settings(session, shop_id)

    from_city = getattr(cfg, "cdek_sender_city_code", None)
    sender_address = getattr(cfg, "cdek_sender_address", "") or ""
    if not from_city:
        raise HTTPException(400, "CDEK: не задан город отправки")

    # Загружаем заказ
    res = await session.execute(
        select(Order).where(Order.id == order_id, Order.shop_id == shop_id)
    )
    order = res.scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Заказ не найден")
    if order.cdek_order_uuid:
        raise HTTPException(400, "Заявка СДЭК для этого заказа уже создана")

    # Получаем адрес ПВЗ
    pvz_address = pvz_code
    try:
        pvzs = await api.get_pvz_list(token, from_city, test=test)
        # Ищем в городе получателя — нужен to_city из cdek
        # Для простоты принимаем pvz_code как достаточный идентификатор
        matched = [p for p in pvzs if p.get("code") == pvz_code]
        if matched:
            pvz_address = matched[0].get("address", pvz_code)
    except CdekError:
        pass

    # Формируем payload СДЭК
    order_payload = {
        "tariff_code": 233,
        "comment": comment or f"Заказ #{order_id}",
        "sender": {
            "name": cfg.shop_name or "Интернет-магазин",
        },
        "recipient": {
            "name": receiver_name,
            "phones": [{"number": receiver_phone}],
        },
        "from_location": {
            "code": from_city,
            "address": sender_address,
        },
        "to_location": {
            "code": pvz_code,      # СДЭК принимает pvz code как to_location при type=PVZ
        },
        "delivery_point": pvz_code,
        "packages": [{
            "number": f"order_{order_id}",
            "weight": max(weight_grams, 50),
            "length": 20, "width": 15, "height": 10,
            "items": [{"name": f"Заказ #{order_id}", "ware_key": str(order_id),
                       "payment": {"value": 0}, "cost": order.total // 100,
                       "weight": max(weight_grams, 50), "amount": 1}],
        }],
    }

    try:
        result = await api.create_order(token, order_payload, test=test)
    except CdekError as exc:
        logger.error("CDEK create_order failed for order_id=%s: %s", order_id, exc)
        raise HTTPException(502, f"Ошибка создания заявки СДЭК: {exc}") from exc

    uuid = result["uuid"]
    order.cdek_order_uuid = uuid
    order.pvz_code = pvz_code
    order.pvz_address = pvz_address
    await session.commit()

    logger.info("CDEK shipment created: order_id=%s uuid=%s", order_id, uuid)
    return {"cdek_order_uuid": uuid, "message": "Заявка создана"}


async def get_shipment_status(
    order_id: int,
    shop_id: int,
    session: AsyncSession,
) -> dict:
    """Актуальный статус заявки СДЭК."""
    res = await session.execute(
        select(Order).where(Order.id == order_id, Order.shop_id == shop_id)
    )
    order = res.scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Заказ не найден")
    if not order.cdek_order_uuid:
        raise HTTPException(400, "Для этого заказа нет заявки СДЭК")

    token, test = await _token(shop_id, session)

    try:
        info = await api.get_order_info(token, order.cdek_order_uuid, test=test)
    except CdekError as exc:
        raise HTTPException(502, str(exc)) from exc

    # Обновляем трек-номер если появился
    if info.get("cdek_number") and order.cdek_track_number != info["cdek_number"]:
        order.cdek_track_number = info["cdek_number"]
        order.cdek_status = info.get("status_code", "")
        await session.commit()

    return {
        "cdek_order_uuid": order.cdek_order_uuid,
        "cdek_track_number": order.cdek_track_number,
        "status_code": info.get("status_code", ""),
        "status_name": info.get("status_name", ""),
        "track_url": info.get("track_url", ""),
    }


async def handle_webhook(payload: dict, session: AsyncSession) -> None:
    """
    Обрабатывает входящий webhook от СДЭК (ORDER_STATUS).
    Обновляет статус в БД и отправляет уведомление покупателю.
    """
    if payload.get("type") != "ORDER_STATUS":
        return

    uuid = payload.get("uuid")
    if not uuid:
        return

    res = await session.execute(
        select(Order).where(Order.cdek_order_uuid == uuid)
    )
    order = res.scalar_one_or_none()
    if not order:
        logger.warning("CDEK webhook: unknown uuid=%s", uuid)
        return

    attrs = payload.get("attributes", {})
    status_code = attrs.get("status_code", "")
    status_name = attrs.get("status_name", "")
    track_number = attrs.get("cdek_number", "") or order.cdek_track_number or ""

    order.cdek_status = status_code
    if track_number:
        order.cdek_track_number = track_number
    await session.commit()

    # Уведомление покупателю
    from app.services.order_service import _get_bot_token_for_shop, _send_telegram
    bot_token = await _get_bot_token_for_shop(order.shop_id, session)

    track_url = (
        f"\n🔗 Отследить: https://www.cdek.ru/ru/tracking?order_id={track_number}"
        if track_number else ""
    )
    text = (
        f"📦 <b>Посылка #{order.id}</b>\n"
        f"Статус СДЭК: <b>{status_name or status_code}</b>"
        f"{track_url}"
    )
    await _send_telegram(bot_token, order.user_id, text)
    logger.info("CDEK webhook processed: uuid=%s status=%s", uuid, status_code)
