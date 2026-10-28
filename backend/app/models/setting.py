"""运行期可改配置。密钥不落此表（见 docs/DATA_MODEL.md 2.13）。"""

from __future__ import annotations

from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, now_ts


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)  # JSON 字符串
    updated_at: Mapped[int] = mapped_column(Integer, nullable=False, default=now_ts)
