"""扫描任务记录。"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, now_ts


class ScanTask(Base):
    __tablename__ = "scan_tasks"
    __table_args__ = (Index("idx_scan_library_status", "library_id", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    library_id: Mapped[int] = mapped_column(
        ForeignKey("libraries.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="queued", server_default="queued"
    )
    triggered_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    started_at: Mapped[int | None] = mapped_column(Integer)
    finished_at: Mapped[int | None] = mapped_column(Integer)
    files_seen: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    files_added: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    files_updated: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    files_removed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    books_created: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    books_updated: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False, default=now_ts)
