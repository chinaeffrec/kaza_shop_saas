"""
Точка входа для сервиса бота.

Запускает BotManager — один asyncio-task на каждый активный магазин.
HTTP-сервер на :8001 принимает сигналы invalidate_catalog_cache от app-сервиса
и роутит их к нужному BotInstance.
"""
import asyncio
import logging

from aiohttp import web

from app.bot.bot_manager import BotManager
from app.logging_setup import configure_logging

configure_logging("bot")
logger = logging.getLogger(__name__)

_manager: BotManager | None = None


async def _make_http_app(manager: BotManager) -> web.Application:
    app = web.Application()

    async def handle_reload(request: web.Request) -> web.Response:
        try:
            body = await request.json()
            shop_id = body.get("shop_id")
        except Exception:
            shop_id = None

        await manager.reload_cache(shop_id)
        logger.info("Cache reloaded via HTTP (shop_id=%s)", shop_id)
        return web.Response(text="ok")

    app.router.add_post("/reload-cache", handle_reload)
    return app


async def main():
    global _manager
    _manager = BotManager()
    await _manager.load_from_db()

    # HTTP control server (Docker-internal, not exposed to host)
    http_app = await _make_http_app(_manager)
    runner = web.AppRunner(http_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8001)
    await site.start()
    logger.info("Cache reload server on :8001 (Docker internal network only)")

    await _manager.start_all()

    try:
        await _manager.wait_all()
    finally:
        await runner.cleanup()
        await _manager.stop_all()


if __name__ == "__main__":
    asyncio.run(main())
