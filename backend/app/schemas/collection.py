"""个人书单 DTO。"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.schemas.book import BookOut


class CollectionName(BaseModel):
    name: str = Field(min_length=1, max_length=64)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("书单名称不能为空")
        return value


class CollectionCreate(CollectionName):
    pass


class CollectionUpdate(CollectionName):
    pass


class CollectionOut(BaseModel):
    id: int
    name: str
    book_count: int
    created_at: int
    cover_url: str | None = None
    # 仅在查询参数 book_id 存在时有意义，用于详情页的「加入书单」勾选状态
    contains_book: bool = False


class CollectionList(BaseModel):
    items: list[CollectionOut]


class CollectionDetail(CollectionOut):
    books: list[BookOut]


class CollectionBookCreate(BaseModel):
    book_id: int = Field(ge=1)
