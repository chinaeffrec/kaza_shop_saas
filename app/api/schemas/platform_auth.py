from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator


class PlatformLoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class PlatformMeResponse(BaseModel):
    user_id: int
    email: str
    role: str
    shop_id: Optional[int]
    is_super_admin: bool


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
