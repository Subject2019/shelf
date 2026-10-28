"""书籍查询 DTO，对应 docs/API.md §3。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProgressBrief(BaseModel):
    position_sec: float
    percent: float
    is_finished: bool


class TrackOut(BaseModel):
    id: int
    track_no: int
    disc_no: int
    title: str | None
    duration_sec: float
    format: str | None
    bitrate: int | None
    stream_url: str


class ChapterOut(BaseModel):
    id: int
    idx: int
    title: str
    start_sec: float
    end_sec: float | None
    track_id: int


class BookOut(BaseModel):
    id: int
    library_id: int
    title: str
    author: str | None
    narrator: str | None
    series_name: str | None
    series_index: float | None
    language: str | None
    # 没有封面时为 None，前端用书名渐变兜底
    cover_url: str | None
    # 手工改过元数据后为 True，扫描不再覆盖
    manual_override: bool
    # 手工封面的上传者 id；扫描抽取的封面为 None
    cover_uploaded_by: int | None = None
    # 管理员在书架中隐藏
    hidden: bool = False
    total_duration_sec: float
    # 跳过片头/片尾（秒），0 表示不跳
    intro_sec: float = 0.0
    outro_sec: float = 0.0
    track_count: int
    size_bytes: int
    chapter_source: str | None
    added_at: int
    progress: ProgressBrief | None


class BookDetail(BookOut):
    subtitle: str | None
    publisher: str | None
    publish_year: int | None
    description: str | None
    rel_dir: str | None
    is_missing: bool
    updated_at: int
    tracks: list[TrackOut]
    # 章节超过 500 条时省略，客户端改用 /chapters 分页拉取
    chapters: list[ChapterOut] | None


class BookList(BaseModel):
    items: list[BookOut]
    total: int
    page: int
    page_size: int


class SeriesOut(BaseModel):
    """系列汇总：有声书常按卷拆成多本，系列是天然的归组维度。"""

    name: str
    book_count: int
    total_duration_sec: float
    # 卷号最小的一本，用它当系列封面；没有封面图时 cover_url 为 None
    cover_book_id: int | None
    cover_url: str | None
    latest_added_at: int


class SeriesList(BaseModel):
    items: list[SeriesOut]


class AuthorOut(BaseModel):
    """作者汇总：用来做「作者」视图（一人多书很常见）。"""

    name: str
    book_count: int
    total_duration_sec: float
    # 优先取有封面文件的一本；都没有封面时 cover_url 为 None
    cover_book_id: int | None
    cover_url: str | None
    latest_added_at: int


class AuthorList(BaseModel):
    items: list[AuthorOut]


class PlayTokenOut(BaseModel):
    token: str
    expires_in: int
    expires_at: int


class ChapterList(BaseModel):
    items: list[ChapterOut]
    total: int
    page: int
    page_size: int


class TranscodeOut(BaseModel):
    """整轨转码产物。"""

    track_id: int
    codec: str
    bitrate: int
    bytes: int
    content_type: str
    cache_key: str
    duration_sec: float | None = None
    # true = 本次调用才生成，false = 命中缓存
    created: bool = False


class ChapterAudioOut(BaseModel):
    """按章节切片的产物（给客户端离线缓存用）。"""

    book_id: int
    index: int
    title: str | None = None
    cache_key: str
    bytes: int
    content_type: str
    start_sec: float | None = None
    duration_sec: float | None = None
    # true 表示本次调用才生成，false 表示命中已有缓存
    created: bool = False


class ChapterCacheList(BaseModel):
    items: list[ChapterAudioOut]
    total_bytes: int


class BookUpdate(BaseModel):
    """PATCH 语义：只改传了的字段；空字符串会被当作「清空」。"""

    title: str | None = Field(default=None, min_length=1, max_length=512)
    subtitle: str | None = Field(default=None, max_length=512)
    author: str | None = Field(default=None, max_length=512)
    narrator: str | None = Field(default=None, max_length=256)
    publisher: str | None = Field(default=None, max_length=256)
    publish_year: int | None = Field(default=None, ge=0, le=3000)
    language: str | None = Field(default=None, max_length=32)
    series_name: str | None = Field(default=None, max_length=256)
    series_index: float | None = None
    description: str | None = None
    intro_sec: float | None = Field(default=None, ge=0, le=86400)
    outro_sec: float | None = Field(default=None, ge=0, le=86400)
    # 仅管理员可改；隐藏后普通用户不可见
    hidden: bool | None = None
