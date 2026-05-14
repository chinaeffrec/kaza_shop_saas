"""
HTTP-слой Telegram Mini App.

Auth:     POST /miniapp/auth        — валидирует initData, возвращает JWT
Catalog:  GET  /miniapp/catalog     — категории + товары
Products: GET  /miniapp/products/{id}
Cart:     GET/POST/PATCH/DELETE /miniapp/cart
Orders:   GET/POST /miniapp/orders
Settings: GET  /miniapp/settings    — публичные настройки магазина
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import MiniAppAuthContext, require_miniapp_auth
from app.api.schemas.miniapp import (
    MiniAppAuthRequest, MiniAppAuthResponse,
    MiniCartAdd, MiniCartResponse, MiniCartUpdate,
    MiniCategory, MiniOrderCreate, MiniOrderResponse,
    MiniProduct,
)
from app.db.session import get_session
from app.models.cart import Cart
from app.models.category import Category
from app.models.order import ORDER_STATUSES, Order, OrderItem
from app.models.platform import Shop
from app.models.product import Product
from app.models.product_stats import ProductStats
from app.services.miniapp_auth_service import (
    create_miniapp_token,
    validate_init_data,
)
from app.services.settings_service import get_shop_settings

router = APIRouter(prefix="/miniapp", tags=["miniapp"])


# ── Auth ──────────────────────────────────────────────────────────────────────

@router.post("/auth", response_model=MiniAppAuthResponse)
async def miniapp_auth(
    data: MiniAppAuthRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Принимает Telegram initData, проверяет HMAC, возвращает JWT.
    Bot token берётся из БД для указанного shop_id.
    """
    # Получаем shop + расшифровываем bot_token
    res = await session.execute(
        select(Shop).where(Shop.id == data.shop_id, Shop.status == "active")
    )
    shop = res.scalar_one_or_none()
    if not shop:
        raise HTTPException(404, "Магазин не найден или не активен")

    raw_bot_token: str | None = None
    if shop.bot_token:
        try:
            from app.core.encryption import decrypt_field
            raw_bot_token = decrypt_field(shop.bot_token)
        except Exception:
            pass

    if not raw_bot_token:
        # fallback к глобальному BOT_TOKEN (для single-shop установок)
        from app.core.config import get_settings
        raw_bot_token = get_settings().bot_token

    if not raw_bot_token:
        raise HTTPException(400, "Бот не настроен для этого магазина")

    try:
        user = validate_init_data(data.init_data, raw_bot_token)
    except ValueError as exc:
        raise HTTPException(401, str(exc)) from exc

    user_id: int = user["id"]
    token = create_miniapp_token(user_id, data.shop_id)

    return MiniAppAuthResponse(
        token=token,
        user_id=user_id,
        first_name=user.get("first_name", ""),
        username=user.get("username"),
    )


# ── Public settings ───────────────────────────────────────────────────────────

@router.get("/settings")
async def miniapp_settings(
    shop_id: int = Query(...),
    session: AsyncSession = Depends(get_session),
):
    """Публичные настройки магазина для Mini App (без авторизации)."""
    cfg = await get_shop_settings(session, shop_id)
    return {
        "shop_name": cfg.shop_name,
        "welcome_message": cfg.welcome_message,
        "logo_url": f"/media/{cfg.logo_filename}" if cfg.logo_filename else None,
        "reviews_enabled": cfg.reviews_enabled,
        "yookassa_enabled": getattr(cfg, "yookassa_enabled", False),
    }


# ── Catalog ───────────────────────────────────────────────────────────────────

@router.get("/catalog", response_model=dict)
async def miniapp_catalog(
    shop_id: int = Query(...),
    session: AsyncSession = Depends(get_session),
):
    """Все категории + все товары одним запросом (публичный endpoint)."""
    cat_res = await session.execute(
        select(Category).where(Category.shop_id == shop_id).order_by(Category.id)
    )
    categories = [
        MiniCategory(id=c.id, name=c.name)
        for c in cat_res.scalars().all()
    ]

    prod_res = await session.execute(
        select(Product)
        .where(Product.shop_id == shop_id, Product.is_active.is_(True))
        .order_by(Product.category_id.asc(), Product.id.asc())
    )
    products = []
    settings = await get_shop_settings(session, shop_id)
    hide_oos = getattr(settings, "hide_out_of_stock", False)

    for p in prod_res.scalars().all():
        if hide_oos and p.stock is not None and p.stock <= 0:
            continue
        products.append(MiniProduct(
            id=p.id,
            name=p.name,
            description=p.description,
            price=p.price,
            image_url=f"/media/{p.image_filename}" if getattr(p, "image_filename", None) else None,
            in_stock=(p.stock is None or p.stock > 0),
            category_id=p.category_id,
        ))

    return {"categories": [c.model_dump() for c in categories], "products": [p.model_dump() for p in products]}


@router.get("/products/{product_id}", response_model=MiniProduct)
async def miniapp_product(
    product_id: int,
    shop_id: int = Query(...),
    session: AsyncSession = Depends(get_session),
):
    """Детали товара (публичный endpoint)."""
    res = await session.execute(
        select(Product).where(
            Product.id == product_id,
            Product.shop_id == shop_id,
            Product.is_active.is_(True),
        )
    )
    p = res.scalar_one_or_none()
    if not p:
        raise HTTPException(404, "Товар не найден")
    return MiniProduct(
        id=p.id,
        name=p.name,
        description=p.description,
        price=p.price,
        image_url=f"/media/{p.image_filename}" if getattr(p, "image_filename", None) else None,
        in_stock=(p.stock is None or p.stock > 0),
        category_id=p.category_id,
    )


# ── Cart ──────────────────────────────────────────────────────────────────────

async def _build_cart_response(user_id: int, shop_id: int, session: AsyncSession) -> dict:
    result = await session.execute(
        select(Cart, Product)
        .join(Product, Cart.product_id == Product.id)
        .where(Cart.user_id == user_id, Cart.shop_id == shop_id)
        .order_by(Cart.id.asc())
    )
    items = []
    total = 0
    for cart, product in result.all():
        s = product.price * cart.quantity
        total += s
        items.append({
            "product_id": product.id,
            "name": product.name,
            "price": product.price,
            "quantity": cart.quantity,
            "sum": s,
            "image_url": f"/media/{product.image_filename}" if getattr(product, "image_filename", None) else None,
        })
    return {"items": items, "total": total}


@router.get("/cart", response_model=MiniCartResponse)
async def miniapp_get_cart(
    session: AsyncSession = Depends(get_session),
    ctx: MiniAppAuthContext = Depends(require_miniapp_auth),
):
    return await _build_cart_response(ctx.user_id, ctx.shop_id, session)


@router.post("/cart", response_model=MiniCartResponse)
async def miniapp_add_to_cart(
    data: MiniCartAdd,
    session: AsyncSession = Depends(get_session),
    ctx: MiniAppAuthContext = Depends(require_miniapp_auth),
):
    # Verify product exists in this shop
    prod_res = await session.execute(
        select(Product).where(
            Product.id == data.product_id,
            Product.shop_id == ctx.shop_id,
            Product.is_active.is_(True),
        )
    )
    if not prod_res.scalar_one_or_none():
        raise HTTPException(404, "Товар не найден")

    cart_res = await session.execute(
        select(Cart).where(
            Cart.user_id == ctx.user_id,
            Cart.product_id == data.product_id,
            Cart.shop_id == ctx.shop_id,
        ).with_for_update()
    )
    item = cart_res.scalar_one_or_none()
    if item:
        item.quantity += data.quantity
    else:
        item = Cart(
            user_id=ctx.user_id,
            product_id=data.product_id,
            quantity=data.quantity,
            shop_id=ctx.shop_id,
        )
        session.add(item)

    # Update stats
    stats_res = await session.execute(
        select(ProductStats).where(ProductStats.product_id == data.product_id)
    )
    stats = stats_res.scalar_one_or_none()
    if not stats:
        stats = ProductStats(product_id=data.product_id, added_to_cart=0, ordered=0, returned=0)
        session.add(stats)
        await session.flush()
    stats.added_to_cart = (stats.added_to_cart or 0) + 1

    await session.commit()
    return await _build_cart_response(ctx.user_id, ctx.shop_id, session)


@router.patch("/cart", response_model=MiniCartResponse)
async def miniapp_update_cart(
    data: MiniCartUpdate,
    session: AsyncSession = Depends(get_session),
    ctx: MiniAppAuthContext = Depends(require_miniapp_auth),
):
    """Устанавливает quantity для товара (0 = удалить из корзины)."""
    cart_res = await session.execute(
        select(Cart).where(
            Cart.user_id == ctx.user_id,
            Cart.product_id == data.product_id,
            Cart.shop_id == ctx.shop_id,
        ).with_for_update()
    )
    item = cart_res.scalar_one_or_none()
    if not item:
        raise HTTPException(404, "Товар не в корзине")

    if data.quantity <= 0:
        await session.delete(item)
    else:
        item.quantity = data.quantity

    await session.commit()
    return await _build_cart_response(ctx.user_id, ctx.shop_id, session)


@router.delete("/cart/{product_id}", response_model=MiniCartResponse)
async def miniapp_remove_from_cart(
    product_id: int,
    session: AsyncSession = Depends(get_session),
    ctx: MiniAppAuthContext = Depends(require_miniapp_auth),
):
    cart_res = await session.execute(
        select(Cart).where(
            Cart.user_id == ctx.user_id,
            Cart.product_id == product_id,
            Cart.shop_id == ctx.shop_id,
        )
    )
    item = cart_res.scalar_one_or_none()
    if item:
        await session.delete(item)
        await session.commit()
    return await _build_cart_response(ctx.user_id, ctx.shop_id, session)


@router.delete("/cart", response_model=MiniCartResponse)
async def miniapp_clear_cart(
    session: AsyncSession = Depends(get_session),
    ctx: MiniAppAuthContext = Depends(require_miniapp_auth),
):
    cart_res = await session.execute(
        select(Cart).where(Cart.user_id == ctx.user_id, Cart.shop_id == ctx.shop_id)
    )
    for item in cart_res.scalars().all():
        await session.delete(item)
    await session.commit()
    return MiniCartResponse(items=[], total=0)


# ── Orders ────────────────────────────────────────────────────────────────────

def _order_to_mini(order: Order, items: list[OrderItem]) -> dict:
    return {
        "id": order.id,
        "status": order.status,
        "status_label": ORDER_STATUSES.get(order.status, order.status),
        "total": order.total,
        "discount": order.discount or 0,
        "promo_code": order.promo_code,
        "delivery_address": order.delivery_address,
        "payment_status": order.payment_status,
        "payment_id": order.payment_id,
        "created_at": order.created_at.isoformat() if order.created_at else "",
        "items": [
            {"name": it.name, "price": it.price, "quantity": it.quantity, "sum": it.price * it.quantity}
            for it in items
        ],
    }


@router.post("/orders", response_model=dict, status_code=201)
async def miniapp_create_order(
    data: MiniOrderCreate,
    session: AsyncSession = Depends(get_session),
    ctx: MiniAppAuthContext = Depends(require_miniapp_auth),
):
    """
    Создаёт заказ из корзины текущего пользователя.
    Дублирует логику bot-order-create, но без bot-token auth.
    """
    from app.api.schemas.order import OrderCreateRequest
    from app.services import order_service as svc

    # Строим payload аналогично боту
    payload = OrderCreateRequest(
        user_id=ctx.user_id,
        comment=data.comment or "",
        delivery_address=data.delivery_address or "",
        promo_code=data.promo_code,
        user_first_name="",
        user_last_name="",
        user_username="",
    )
    order = await svc.create_order(payload, session, ctx.shop_id)
    return order


@router.get("/orders", response_model=list[dict])
async def miniapp_get_orders(
    session: AsyncSession = Depends(get_session),
    ctx: MiniAppAuthContext = Depends(require_miniapp_auth),
):
    """История заказов текущего пользователя."""
    res = await session.execute(
        select(Order)
        .where(Order.user_id == ctx.user_id, Order.shop_id == ctx.shop_id)
        .order_by(Order.created_at.desc())
    )
    orders = res.scalars().all()
    result = []
    for order in orders:
        items_res = await session.execute(
            select(OrderItem).where(OrderItem.order_id == order.id)
        )
        result.append(_order_to_mini(order, items_res.scalars().all()))
    return result
