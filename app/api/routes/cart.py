from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import BotAuthContext, require_bot_auth
from app.api.schemas.cart import CartAddRequest, CartItemAction
from app.db.session import get_session
from app.models.cart import Cart
from app.models.product import Product
from app.models.product_stats import ProductStats

router = APIRouter(prefix="/cart", tags=["cart"])


async def _inc_cart_stat(product_id: int, session: AsyncSession):
    res = await session.execute(
        select(ProductStats).where(ProductStats.product_id == product_id)
    )
    s = res.scalar_one_or_none()
    if not s:
        s = ProductStats(product_id=product_id, added_to_cart=0, ordered=0, returned=0)
        session.add(s)
        await session.flush()
    s.added_to_cart = (s.added_to_cart or 0) + 1


@router.post("/", response_model=None)
async def add_to_cart(
    data: CartAddRequest,
    session: AsyncSession = Depends(get_session),
    bot_ctx: BotAuthContext = Depends(require_bot_auth),
):
    if bot_ctx.user_id is None or bot_ctx.user_id != data.user_id:
        raise HTTPException(403, "user_id mismatch")
    user_id = data.user_id
    product_id = data.product_id
    quantity = data.quantity
    shop_id = bot_ctx.shop_id

    result = await session.execute(
        select(Cart)
        .where(Cart.user_id == user_id, Cart.product_id == product_id, Cart.shop_id == shop_id)
        .with_for_update()
    )
    cart_item = result.scalar_one_or_none()
    if cart_item:
        cart_item.quantity += quantity
    else:
        cart_item = Cart(user_id=user_id, product_id=product_id, quantity=quantity, shop_id=shop_id)
        session.add(cart_item)

    await _inc_cart_stat(product_id, session)
    await session.commit()
    return {"status": "ok"}


@router.get("/{user_id}")
async def get_cart(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    bot_ctx: BotAuthContext = Depends(require_bot_auth),
):
    if bot_ctx.user_id is None or bot_ctx.user_id != user_id:
        raise HTTPException(403, "user_id mismatch")
    shop_id = bot_ctx.shop_id
    result = await session.execute(
        select(Cart, Product).join(Product, Cart.product_id == Product.id)
        .where(Cart.user_id == user_id, Cart.shop_id == shop_id)
        .order_by(Cart.id.asc())
    )
    rows = result.all()
    items = []
    total = 0
    for cart, product in rows:
        item_total = product.price * cart.quantity
        total += item_total
        items.append({
            "product_id": product.id, "name": product.name,
            "price": product.price, "quantity": cart.quantity, "sum": item_total,
        })
    return {"items": items, "total": total}


@router.post("/inc")
async def inc_item(
    data: CartItemAction,
    session: AsyncSession = Depends(get_session),
    bot_ctx: BotAuthContext = Depends(require_bot_auth),
):
    if bot_ctx.user_id is None or bot_ctx.user_id != data.user_id:
        raise HTTPException(403, "user_id mismatch")
    shop_id = bot_ctx.shop_id
    result = await session.execute(
        select(Cart)
        .where(Cart.user_id == data.user_id, Cart.product_id == data.product_id, Cart.shop_id == shop_id)
        .with_for_update()
    )
    item = result.scalar_one_or_none()
    if item:
        item.quantity += 1
        await session.commit()
    return {"status": "ok"}


@router.post("/dec")
async def dec_item(
    data: CartItemAction,
    session: AsyncSession = Depends(get_session),
    bot_ctx: BotAuthContext = Depends(require_bot_auth),
):
    if bot_ctx.user_id is None or bot_ctx.user_id != data.user_id:
        raise HTTPException(403, "user_id mismatch")
    shop_id = bot_ctx.shop_id
    result = await session.execute(
        select(Cart)
        .where(Cart.user_id == data.user_id, Cart.product_id == data.product_id, Cart.shop_id == shop_id)
        .with_for_update()
    )
    item = result.scalar_one_or_none()
    if item:
        item.quantity -= 1
        if item.quantity <= 0:
            await session.delete(item)
        await session.commit()
    return {"status": "ok"}


@router.post("/remove")
async def remove_item(
    data: CartItemAction,
    session: AsyncSession = Depends(get_session),
    bot_ctx: BotAuthContext = Depends(require_bot_auth),
):
    if bot_ctx.user_id is None or bot_ctx.user_id != data.user_id:
        raise HTTPException(403, "user_id mismatch")
    shop_id = bot_ctx.shop_id
    result = await session.execute(
        select(Cart).where(
            Cart.user_id == data.user_id,
            Cart.product_id == data.product_id,
            Cart.shop_id == shop_id,
        )
    )
    item = result.scalar_one_or_none()
    if item:
        await session.delete(item)
        await session.commit()
    return {"status": "ok"}
