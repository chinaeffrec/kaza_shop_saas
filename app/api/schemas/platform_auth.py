from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class PlatformLoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TotpChallengeResponse(BaseModel):
    """Возвращается вместо токена, если у пользователя включён 2FA."""
    requires_totp: bool = True
    challenge_token: str


class TotpVerifyLoginRequest(BaseModel):
    challenge_token: str
    totp_code: str = Field(min_length=6, max_length=8)


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class PlatformMeResponse(BaseModel):
    user_id: int
    email: str
    role: str
    shop_id: Optional[int]
    is_super_admin: bool
    permissions: List[str] = Field(default_factory=list)


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_strength(cls, v: str) -> str:
        import re
        if len(v) < 10:
            raise ValueError("Минимум 10 символов")
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("Нужна хотя бы одна буква")
        if not re.search(r"\d", v):
            raise ValueError("Нужна хотя бы одна цифра")
        return v


class CreatePlatformUserRequest(BaseModel):
    email: EmailStr
    password: str
    is_super_admin: bool = False

    @field_validator("password")
    @classmethod
    def validate_strength(cls, v: str) -> str:
        import re
        if len(v) < 10:
            raise ValueError("Минимум 10 символов")
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("Нужна хотя бы одна буква")
        if not re.search(r"\d", v):
            raise ValueError("Нужна хотя бы одна цифра")
        return v


class PlatformUserResponse(BaseModel):
    user_id: int
    email: str
    is_super_admin: bool
    is_active: bool

    model_config = {"from_attributes": True}


# ── Shop members ──────────────────────────────────────────────────────────────

class MemberInviteRequest(BaseModel):
    """Приглашение пользователя в команду магазина."""
    email: EmailStr
    role: Literal["owner", "manager", "support"] = "manager"


class MemberRoleUpdate(BaseModel):
    role: Literal["owner", "manager", "support"]


class ShopMemberResponse(BaseModel):
    id: int
    shop_id: int
    user_id: int
    email: str
    role: str
    invited_by_id: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Audit logs ────────────────────────────────────────────────────────────────

class AuditLogResponse(BaseModel):
    id: int
    actor_id: Optional[int] = None
    actor_email: Optional[str] = None
    actor_role: Optional[str] = None
    shop_id: Optional[int] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    before_data: Optional[dict] = None
    after_data: Optional[dict] = None
    extra: Optional[dict] = None
    ip_address: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    items: List[AuditLogResponse]
    total: int
    page: int
    per_page: int
