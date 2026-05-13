from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.bot.services.catalog_cache import CatalogCache, catalog_cache as _default_cache
from app.bot.services.navigation import navigation
from app.bot.services.render_engine import render_engine, render_product_card
from app.bot.states.screen import Screen

router = Router()


@router.callback_query(F.data.startswith("open_"))
async def open_handler(
    callback: CallbackQuery,
    catalog_cache: CatalogCache | None = None,
    shop_id: int = 1,
):
    cache = catalog_cache or _default_cache
    user_id = callback.from_user.id
    parts = callback.data.split("_")
    entity = parts[1]
    entity_id = int(parts[-1])

    if entity == "category":
        screen = Screen(type="subcategories", category_id=entity_id)
        navigation.push(user_id, screen)
    elif entity == "sub":
        screen = Screen(type="products", subcategory_id=entity_id)
        navigation.push(user_id, screen)
    elif entity == "product":
        screen = Screen(type="product", product_id=entity_id)
        current = navigation.peek(user_id)
        stack = navigation._stack.get(user_id)
        if current and current.type == "product" and stack:
            stack[-1] = screen
        else:
            navigation.push(user_id, screen)
    else:
        await callback.answer()
        return

    await render_engine.render(screen, callback.message, cache=cache, shop_id=shop_id)
    await callback.answer()


@router.callback_query(F.data == "back")
async def back(
    callback: CallbackQuery,
    catalog_cache: CatalogCache | None = None,
    shop_id: int = 1,
):
    cache = catalog_cache or _default_cache
    user_id = callback.from_user.id
    current = navigation.peek(user_id)

    if current and current.type == "product":
        product = cache.get_product(current.product_id)
        if product:
            navigation.reset(user_id)
            screen = Screen(type="products", subcategory_id=product.subcategory_id)
            navigation.push(user_id, screen)
            await render_engine.render(screen, callback.message, cache=cache, shop_id=shop_id)
            await callback.answer()
            return

    if current and current.type == "products":
        sub = cache.get_subcategory_by_id(current.subcategory_id)
        if sub:
            navigation.reset(user_id)
            screen = Screen(type="subcategories", category_id=sub.category_id)
            navigation.push(user_id, screen)
            await render_engine.render(screen, callback.message, cache=cache, shop_id=shop_id)
            await callback.answer()
            return

    navigation.reset(user_id)
    screen = Screen(type="categories")
    navigation.push(user_id, screen)
    await render_engine.render(screen, callback.message, cache=cache, shop_id=shop_id)
    await callback.answer()


@router.callback_query(F.data.startswith("photo_"))
async def photo_switch(
    callback: CallbackQuery,
    catalog_cache: CatalogCache | None = None,
    shop_id: int = 1,
):
    cache = catalog_cache or _default_cache
    parts = callback.data.split("_")
    product_id = int(parts[1])
    photo_idx = int(parts[2])

    product = cache.get_product(product_id)
    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    sub = cache.get_subcategory_by_id(product.subcategory_id)
    products_list = sub.products if sub else [product]
    product_idx = next((i for i, p in enumerate(products_list) if p.id == product_id), 0)

    await render_product_card(
        callback.message, product, product_idx, len(products_list),
        photo_idx, cache=cache, shop_id=shop_id,
    )
    await callback.answer()
