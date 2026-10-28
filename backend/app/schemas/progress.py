"""进度 DTO，对应 docs/API.md §5。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProgressPut(BaseModel):
    track_id: int | None = None
    position_sec: float = Field(ge=0)
    playback_rate: float = Field(default=1.0, gt=0, le=4.0)
    device_id: str | None = Field(default=None, max_length=64)
    client_updated_at: int = Field(ge=0)
    explicit_seek: bool = False
    finished: bool = False


class ProgressOut(BaseModel):
    book_id: int
    position_sec: float
    track_id: int | None
    track_position_sec: float
    playback_rate: float
    is_finished: bool
    device_id: str | None
    client_updated_at: int
    updated_at: int


class ProgressPutOut(BaseModel):
    book_id: int
    position_sec: float
    track_id: int | None
    accepted: bool
    is_finished: bool
    updated_at: int


class RecentProgressItem(BaseModel):
    book_id: int
    title: str
    author: str | None
    cover_url: str | None
    position_sec: float
    total_duration_sec: float
    percent: float
    updated_at: int
    # 最后写入这条进度的设备，客户端据此判断「是不是我自己写的」
    device_id: str | None = None


class RecentProgressList(BaseModel):
    items: list[RecentProgressItem]


class ProgressHistoryItem(BaseModel):
    id: int
    position_sec: float
    track_id: int | None
    device_id: str | None
    created_at: int


class ProgressHistoryList(BaseModel):
    items: list[ProgressHistoryItem]
