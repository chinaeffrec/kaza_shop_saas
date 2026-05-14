"""
Сервис аудит-логирования.

Каждое мутирующее действие super_admin (и, в будущих итерациях, owner)
записывается в таблицу audit_logs.

Принципы:
- Запись в аудит НЕ должна блокировать основное действие: ошибка аудита
  логируется, но не выбрасывает исключение.
- Запись производится ПОСЛЕ успешного commit основной транзакции, через
  отдельную сессию или через teh same session perед commit (flexible).
- JSONB-поля before/after позволяют строить полный diff изменений.

Использование:
    from app.services.audit_service import audit_log

    await audit_log(
        session=session,
        actor=ctx,                          # PlatformAuthContext
        action="shop.status_changed",
        entity_type="shop",
        entity_id=str(shop_id),
        before={"status": old_status},
        after={"status": new_status},
        request=request,                    # опционально, для IP/UA
    )
"""
import logging
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import PlatformAuthContext

logger = logging.getLogger(__name__)


async def audit_log(
    session: AsyncSession,
    actor: Optional[PlatformAuthContext],
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    before: Optional[dict] = None,
    after: Optional[dict] = None,
    extra: Optional[dict] = None,
    shop_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """
    Записывает событие в audit_logs.
    Ошибка записи логируется, но не прерывает выполнение.
    """
    import json as _json

    try:
        actor_id = actor.user_id if actor else None
        actor_email = actor.email if actor else None
        actor_role = actor.role if actor else None
        effective_shop_id = shop_id if shop_id is not None else (actor.shop_id if actor else None)

        await session.execute(
            text("""
                INSERT INTO audit_logs
                    (actor_id, actor_email, actor_role, shop_id, action,
                     entity_type, entity_id, before_data, after_data,
                     extra, ip_address, user_agent)
                VALUES
                    (:actor_id, :actor_email, :actor_role, :shop_id, :action,
                     :entity_type, :entity_id, :before_data::jsonb, :after_data::jsonb,
                     :extra::jsonb, :ip_address, :user_agent)
            """),
            {
                "actor_id": actor_id,
                "actor_email": actor_email,
                "actor_role": actor_role,
                "shop_id": effective_shop_id,
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "before_data": _json.dumps(before) if before else None,
                "after_data": _json.dumps(after) if after else None,
                "extra": _json.dumps(extra) if extra else None,
                "ip_address": ip_address,
                "user_agent": user_agent,
            },
        )
        # Не делаем отдельный commit — вызывающий код решает, когда коммитить
    except Exception as exc:
        logger.error("audit_log failed (action=%s): %s", action, exc)
        # Не пробрасываем — аудит не должен ломать бизнес-логику


def from_request(request: Any) -> tuple[Optional[str], Optional[str]]:
    """
    Извлекает IP и User-Agent из FastAPI Request.
    Возвращает (ip_address, user_agent).
    """
    try:
        ip = request.client.host if request.client else None
        ua = request.headers.get("User-Agent")
        return ip, ua
    except Exception:
        return None, None
