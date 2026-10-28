"""收听进度与书签。"""

from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, now_ts


class Progress(Base):
    __tablename__ = "progress"
    __table_args__ = (
        # 升序复合索引反向扫描即可满足 ORDER BY updated_at DESC；
        # 用表达式 DESC 索引会导致 SQLite 无法反射、autogenerate 永远比对不上。
        Index("idx_progress_updated", "user_id", "updated_at"),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), primary_key=True
    )
    position_sec: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0"
    )
    track_id: Mapped[int | None] = mapped_column(
        ForeignKey("tracks.id", ondelete="SET NULL")
    )
    track_position_sec: Mapped[float | None] = mapped_column(Float)
    playback_rate: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0, server_default="1.0"
    )
    is_finished: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default="0"
    )
    device_id: Mapped[str | None] = mapped_column(Text)
    client_updated_at: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[int] = mapped_column(Integer, nullable=False, default=now_ts)


class Bookmark(Base):
    __tablename__ = "bookmarks"
    __table_args__ = (
        Index("idx_bookmarks_user_book", "user_id", "book_id", "position_sec"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), nullable=False
    )
    position_sec: Mapped[float] = mapped_column(Float, nullable=False)
    track_id: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False, default=now_ts)


class ProgressHistory(Base):
    """进度检查点：每本书保留最近 5 个「位置差异明显」的快照。

    权威进度仍然是 `progress` 表的一行；这里只是同账号同书的回溯点，
    用来在误拖进度、多设备打架之后找回之前听到的位置。
    """

    __tablename__ = "progress_history"
    __table_args__ = (
        Index("idx_progress_history_user_book", "user_id", "book_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), nullable=False
    )
    position_sec: Mapped[float] = mapped_column(Float, nullable=False)
    track_id: Mapped[int | None] = mapped_column(
        ForeignKey("tracks.id", ondelete="SET NULL")
    )
    device_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False, default=now_ts)
