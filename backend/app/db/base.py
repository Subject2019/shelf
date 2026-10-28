"""ORM 声明基类与通用时间戳，供模型与 Alembic 迁移共用。"""

from __future__ import annotations

import time

from sqlalchemy import Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now_ts() -> int:
    """统一用 epoch 秒，避免时区歧义（见 docs/DATA_MODEL.md）。"""
    return int(time.time())


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[int] = mapped_column(Integer, nullable=False, default=now_ts)
