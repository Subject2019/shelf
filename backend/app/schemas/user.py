"""用户管理（管理员）与注册。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.auth import DeviceIn


class UserAdminOut(BaseModel):
    id: int
    username: str
    display_name: str | None
    role: str
    is_active: bool
    passwordless: bool
    # 生效中的可见书库（公开库 + 显式授权），与 /me 的 libraries 一致
    libraries: list[int]
    created_at: int
    last_login_at: int | None


class UserAdminList(BaseModel):
    items: list[UserAdminOut]
    total: int
    page: int
    page_size: int


class UserCreateIn(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    # 免密账号不填密码；普通账号仍要求至少 8 位。
    password: str | None = Field(default=None, min_length=8, max_length=256)
    passwordless: bool = False
    display_name: str | None = Field(default=None, max_length=64)
    # 管理员只能由环境变量 / CLI 创建，接口不接受 admin
    role: Literal["editor", "listener"] = "listener"
    library_ids: list[int] = Field(default_factory=list)


class UserUpdateIn(BaseModel):
    display_name: str | None = Field(default=None, max_length=64)
    role: Literal["editor", "listener"] | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=256)
    passwordless: bool | None = None
    # 传入即整体替换；空数组表示不再单独授权（若书库是公开的仍然可见）
    library_ids: list[int] | None = None


class RegisterIn(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=8, max_length=256)
    display_name: str | None = Field(default=None, max_length=64)
    device: DeviceIn | None = None
