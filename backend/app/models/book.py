"""书籍、逻辑播放轨与章节。"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, now_ts


class Book(Base):
    __tablename__ = "books"
    __table_args__ = (
        Index("idx_books_library", "library_id"),
        Index("idx_books_title", "title"),
        Index("idx_books_author", "author"),
        Index("idx_books_series", "series_name", "series_index"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    library_id: Mapped[int] = mapped_column(
        ForeignKey("libraries.id", ondelete="CASCADE"), nullable=False
    )
    rel_dir: Mapped[str | None] = mapped_column(Text)  # 相对库根
    title: Mapped[str] = mapped_column(Text, nullable=False)
    subtitle: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(Text)  # 多位用 , 分隔
    narrator: Mapped[str | None] = mapped_column(Text)
    publisher: Mapped[str | None] = mapped_column(Text)
    publish_year: Mapped[int | None] = mapped_column(Integer)
    language: Mapped[str | None] = mapped_column(Text)  # BCP-47
    description: Mapped[str | None] = mapped_column(Text)
    series_name: Mapped[str | None] = mapped_column(Text)
    series_index: Mapped[float | None] = mapped_column(Float)  # 支持 1.5
    cover_path: Mapped[str | None] = mapped_column(Text)  # 相对 covers 目录
    # 手工上传封面的用户 id（扫描抽取的为 NULL）；用于「上传者只能删自己传的封面」。
    # 不加外键约束：SQLite 加 FK 需要重建表，会连带丢掉 books_fts 的同步触发器。
    cover_uploaded_by: Mapped[int | None] = mapped_column(Integer)
    # 管理员隐藏：不出现在书架/搜索/系列/作者聚合，仅管理员仍可见
    hidden: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    # 跳过片头/片尾（秒），0 表示不跳；由管理员在详情页配置
    intro_sec: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0"
    )
    outro_sec: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0"
    )
    total_duration_sec: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0"
    )
    track_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    size_bytes: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    chapter_source: Mapped[str | None] = mapped_column(Text)
    is_missing: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    # 管理员手工改过元数据后置 1，扫描器不再覆盖书名/作者等字段（docs/API.md §3）
    manual_override: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    added_at: Mapped[int] = mapped_column(Integer, nullable=False, default=now_ts)
    updated_at: Mapped[int] = mapped_column(Integer, nullable=False, default=now_ts)


class Track(Base):
    __tablename__ = "tracks"
    __table_args__ = (
        UniqueConstraint("book_id", "disc_no", "track_no", name="uq_tracks_position"),
        Index("idx_tracks_book", "book_id", "track_no"),
        Index("idx_tracks_media", "media_file_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), nullable=False
    )
    media_file_id: Mapped[int] = mapped_column(
        ForeignKey("media_files.id", ondelete="CASCADE"), nullable=False
    )
    disc_no: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    track_no: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    title: Mapped[str | None] = mapped_column(Text)
    # CUE 分轨时指向物理文件内的起点
    start_offset_sec: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0"
    )
    duration_sec: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0"
    )
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)


class Chapter(Base):
    __tablename__ = "chapters"
    __table_args__ = (Index("idx_chapters_book", "book_id", "idx"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), nullable=False
    )
    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False
    )
    idx: Mapped[int] = mapped_column(Integer, nullable=False)  # 全书顺序，从 0 开始
    title: Mapped[str] = mapped_column(Text, nullable=False)
    # 相对全书开头的绝对秒数
    start_sec: Mapped[float] = mapped_column(Float, nullable=False)
    end_sec: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(Text, nullable=False)
