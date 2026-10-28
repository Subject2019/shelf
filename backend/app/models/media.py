"""物理音频文件索引。

与 tracks 分离：CUE 分轨时一个文件对应多条 track，扫描不重复解析大文件。
"""

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


class MediaFile(Base):
    __tablename__ = "media_files"
    __table_args__ = (
        # 判重键按 AGENTS.md 红线 3 用 (library_id, rel_path)，允许不同书库存在同名相对路径
        UniqueConstraint("library_id", "rel_path", name="uq_media_library_relpath"),
        Index("idx_media_library", "library_id"),
        Index("idx_media_missing", "is_missing"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    library_id: Mapped[int] = mapped_column(
        ForeignKey("libraries.id", ondelete="CASCADE"), nullable=False
    )
    rel_path: Mapped[str] = mapped_column(Text, nullable=False)  # 相对库根，/ 分隔
    format: Mapped[str] = mapped_column(Text, nullable=False)
    codec: Mapped[str | None] = mapped_column(Text)
    bitrate: Mapped[int | None] = mapped_column(Integer)  # kbps
    sample_rate: Mapped[int | None] = mapped_column(Integer)
    channels: Mapped[int | None] = mapped_column(Integer)
    duration_sec: Mapped[float | None] = mapped_column(Float)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    mtime: Mapped[int | None] = mapped_column(BigInteger)  # 幂等判重
    inode: Mapped[int | None] = mapped_column(BigInteger)  # NAS 上可能为 0
    has_embedded_chapters: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    embedded_chapters_json: Mapped[str | None] = mapped_column(Text)
    is_missing: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    first_seen_at: Mapped[int] = mapped_column(Integer, nullable=False, default=now_ts)
    last_seen_at: Mapped[int] = mapped_column(Integer, nullable=False, default=now_ts)
