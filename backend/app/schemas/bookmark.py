"""书签 DTO，对应 docs/API.md §6。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class BookmarkCreate(BaseModel):
    position_sec: float = Field(ge=0)
    track_id: int | None = None
    note: str | None = Field(default=None, max_length=2000)


class BookmarkUpdate(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class BookmarkOut(BaseModel):
    id: int
    book_id: int
    position_sec: float
    track_id: int | None
    note: str | None
    created_at: int
