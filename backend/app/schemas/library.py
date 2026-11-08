"""书库与扫描任务 DTO，对应 docs/API.md §2。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LibraryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    # Docker 默认根目录为 /audiobooks，原生安装为安装时选择的有声书目录；
    # 允许子目录用于拆分多书库。
    root_path: str = Field(min_length=1, max_length=1024)
    user_ids: list[int] = Field(default_factory=list)


class LibraryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    enabled: bool | None = None
    # None = 不改授权；[] = 清空授权（回到全员可见）
    user_ids: list[int] | None = None


class ScanBrief(BaseModel):
    status: str
    finished_at: int | None


class LibraryOut(BaseModel):
    id: int
    name: str
    root_path: str
    enabled: bool
    book_count: int
    total_duration_sec: float
    last_scan_at: int | None
    scan: ScanBrief | None


class LibraryList(BaseModel):
    items: list[LibraryOut]
    total: int
    page: int
    page_size: int


class ScanTriggerOut(BaseModel):
    task_id: int
    status: str


class ScanStatusOut(BaseModel):
    task_id: int
    status: str
    started_at: int | None
    finished_at: int | None
    files_seen: int
    files_added: int
    files_updated: int
    files_removed: int
    books_created: int
    books_updated: int
    error: str | None
