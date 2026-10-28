"""收听统计：按天累计实际收听时长。"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, now_ts


class ListeningDaily(Base):
    """一行 = 某账号某一天听了多少秒。

    只统计「自然播放」推进的部分：拖动进度条（explicit_seek）不算，
    并按时长上限截断，避免离线补传时把几小时空白都算成收听。
    """

    __tablename__ = "listening_daily"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    # 本地日期 YYYY-MM-DD（服务器时区）
    day: Mapped[str] = mapped_column(Text, primary_key=True)
    seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[int] = mapped_column(Integer, nullable=False, default=now_ts)
