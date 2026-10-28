"""设备管理。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DeviceOut(BaseModel):
    id: str
    user_id: int
    username: str | None = None
    name: str | None
    platform: str | None
    app_version: str | None
    os: str | None
    form_factor: str | None
    screen: str | None
    user_agent: str | None
    created_at: int | None
    last_seen_at: int | None
    revoked_at: int | None
    # 客户端主动上报离开的时间；非空且没有新请求时判定离线
    offline_at: int | None
    # 在线 = 未被踢下线、未上报离开、且 2 分钟内有心跳
    online: bool


class PresenceIn(BaseModel):
    online: bool


class DeviceList(BaseModel):
    items: list[DeviceOut]


class DeviceUpdateIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
