"""
Team management — участники магазина.

GET    /platform/shops/{id}/members              — список [super_admin | owner]
POST   /platform/shops/{id}/members              — пригласить [super_admin | owner]
PATCH  /platform/shops/{id}/members/{user_id}    — изменить роль [super_admin | owner]
DELETE /platform/shops/{id}/members/{user_id}    — удалить [super_admin | owner]
"""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import PlatformAuthContext, assert_shop_access, require_platform_auth, require_super_admin
from app.api.schemas.platform_auth import MemberInviteRequest, MemberRoleUpdate, ShopMemberResponse
from app.core.rbac import ROLE_OWNER, SHOP_ROLES
from app.db.session import get_session
from app.models.platform import PlatformUser, Shop, ShopMember
from app.services.audit_service import audit_log

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/platform/shops", tags=["platform-members"])


def _assert_member_access(ctx: PlatformAuthContext, shop_id: int) -> None:
    """Только super_admin или owner этого магазина может управлять участниками."""
    if ctx.is_super_admin:
        return
    assert_shop_access(ctx, shop_id)
    if ctx.role != ROLE_OWNER:
        raise HTTPException(403, "Only shop owner can manage team members")


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("/{shop_id}/members", response_model=List[ShopMemberResponse])
async def list_members(
    shop_id: int,
    session: AsyncSession = Depends(get_session),
    ctx: PlatformAuthContext = Depends(require_platform_auth),
):
    assert_shop_access(ctx, shop_id)
    result = await session.execute(
        select(ShopMember, PlatformUser)
        .join(PlatformUser, ShopMember.user_id == PlatformUser.id)
        .where(ShopMember.shop_id == shop_id)
        .order_by(ShopMember.created_at)
    )
    rows = result.all()
    return [
        ShopMemberResponse(
            id=m.id,
            shop_id=m.shop_id,
            user_id=m.user_id,
            email=u.email,
            role=m.role,
            invited_by_id=m.invited_by_id,
            created_at=m.created_at,
        )
        for m, u in rows
    ]


# ── Invite ────────────────────────────────────────────────────────────────────

@router.post("/{shop_id}/members", response_model=ShopMemberResponse, status_code=201)
async def invite_member(
    shop_id: int,
    data: MemberInviteRequest,
    session: AsyncSession = Depends(get_session),
    ctx: PlatformAuthContext = Depends(require_platform_auth),
):
    _assert_member_access(ctx, shop_id)

    # Проверяем что магазин существует
    shop = await session.get(Shop, shop_id)
    if not shop:
        raise HTTPException(404, "Shop not found")

    # Ищем пользователя по email
    user_result = await session.execute(
        select(PlatformUser).where(PlatformUser.email == data.email.lower())
    )
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, f"Platform user with email '{data.email}' not found. "
                                 "User must register first.")
    if not user.is_active:
        raise HTTPException(400, "User is deactivated")

    # Проверяем что пользователь ещё не в команде
    existing = await session.execute(
        select(ShopMember).where(
            ShopMember.shop_id == shop_id,
            ShopMember.user_id == user.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "User is already a member of this shop")

    member = ShopMember(
        shop_id=shop_id,
        user_id=user.id,
        role=data.role,
        invited_by_id=ctx.user_id,
    )
    session.add(member)
    await session.commit()
    await session.refresh(member)

    await audit_log(
        session=session, actor=ctx,
        action="shop.member_invited",
        entity_type="shop_member",
        entity_id=str(member.id),
        after={"user_email": user.email, "role": data.role},
        shop_id=shop_id,
    )

    logger.info(
        "Member invited: user=%d email=%s → shop=%d role=%s by actor=%d",
        user.id, user.email, shop_id, data.role, ctx.user_id,
    )
    return ShopMemberResponse(
        id=member.id, shop_id=member.shop_id, user_id=member.user_id,
        email=user.email, role=member.role,
        invited_by_id=member.invited_by_id, created_at=member.created_at,
    )


# ── Update role ───────────────────────────────────────────────────────────────

@router.patch("/{shop_id}/members/{member_user_id}", response_model=ShopMemberResponse)
async def update_member_role(
    shop_id: int,
    member_user_id: int,
    data: MemberRoleUpdate,
    session: AsyncSession = Depends(get_session),
    ctx: PlatformAuthContext = Depends(require_platform_auth),
):
    _assert_member_access(ctx, shop_id)

    result = await session.execute(
        select(ShopMember, PlatformUser)
        .join(PlatformUser, ShopMember.user_id == PlatformUser.id)
        .where(ShopMember.shop_id == shop_id, ShopMember.user_id == member_user_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(404, "Member not found")

    member, user = row
    old_role = member.role

    # Нельзя понижать единственного owner'а
    if old_role == ROLE_OWNER and data.role != ROLE_OWNER:
        owners_count = await session.execute(
            select(ShopMember).where(
                ShopMember.shop_id == shop_id,
                ShopMember.role == ROLE_OWNER,
            )
        )
        if len(owners_count.scalars().all()) <= 1:
            raise HTTPException(400, "Cannot demote the only owner of a shop")

    member.role = data.role
    await session.commit()

    await audit_log(
        session=session, actor=ctx,
        action="shop.member_role_changed",
        entity_type="shop_member", entity_id=str(member.id),
        before={"role": old_role}, after={"role": data.role},
        shop_id=shop_id,
    )

    return ShopMemberResponse(
        id=member.id, shop_id=member.shop_id, user_id=member.user_id,
        email=user.email, role=member.role,
        invited_by_id=member.invited_by_id, created_at=member.created_at,
    )


# ── Remove ────────────────────────────────────────────────────────────────────

@router.delete("/{shop_id}/members/{member_user_id}", status_code=204)
async def remove_member(
    shop_id: int,
    member_user_id: int,
    session: AsyncSession = Depends(get_session),
    ctx: PlatformAuthContext = Depends(require_platform_auth),
):
    _assert_member_access(ctx, shop_id)

    # Нельзя удалить самого себя (это не kick, это resign — отдельная операция в будущем)
    if member_user_id == ctx.user_id and not ctx.is_super_admin:
        raise HTTPException(400, "Use /leave endpoint to remove yourself from shop")

    result = await session.execute(
        select(ShopMember)
        .where(ShopMember.shop_id == shop_id, ShopMember.user_id == member_user_id)
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(404, "Member not found")

    # Нельзя удалить единственного owner'а
    if member.role == ROLE_OWNER:
        owners = await session.execute(
            select(ShopMember).where(
                ShopMember.shop_id == shop_id,
                ShopMember.role == ROLE_OWNER,
            )
        )
        if len(owners.scalars().all()) <= 1:
            raise HTTPException(400, "Cannot remove the only owner of a shop")

    await audit_log(
        session=session, actor=ctx,
        action="shop.member_removed",
        entity_type="shop_member", entity_id=str(member.id),
        before={"user_id": member_user_id, "role": member.role},
        shop_id=shop_id,
    )

    await session.delete(member)
    await session.commit()
