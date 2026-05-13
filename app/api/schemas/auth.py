from typing import Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    login: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    token: str
    login: str
    expires_in: int


class CredentialsUpdate(BaseModel):
    new_login: str = Field(min_length=3, max_length=64)
    new_password: str = Field(min_length=10)
    current_password: str


class MeResponse(BaseModel):
    login: str
    authenticated: bool


class CredentialsUpdateResponse(BaseModel):
    ok: bool
    token: str
    login: str


class UploadResponse(BaseModel):
    status: str
    slot: Optional[int] = None
    filename: Optional[str] = None
    url: Optional[str] = None
