"""认证相关 DTO，对应 docs/API.md §1。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DeviceIn(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    # 展示名，建议 "Chrome 141" / "Pixel 8" 这种
    name: str | None = Field(default=None, max_length=128)
    platform: str | None = Field(default=None, max_length=32)
    app_version: str | None = Field(default=None, max_length=32)
    os: str | None = Field(default=None, max_length=64)
    form_factor: str | None = Field(default=None, max_length=16)
    screen: str | None = Field(default=None, max_length=32)
    user_agent: str | None = Field(default=None, max_length=512)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)
    device: DeviceIn | None = None


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str | None
    role: str
    libraries: list[int]
    created_at: int


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    user: UserOut


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=512)


class PasswordChangeRequest(BaseModel):
    old_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=8, max_length=256)
