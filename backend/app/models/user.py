"""用户、设备与刷新令牌。"""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, now_ts


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 存小写，登录时先 lower() 再比对（docs/DATA_MODEL.md 2.1）
    username: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text)
    # admin = 全部权限；editor = 可改资料/传封面，只能删自己传的封面；listener = 只读
    role: Mapped[str] = mapped_column(
        Text, nullable=False, default="listener", server_default="listener"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    created_at: Mapped[int] = mapped_column(Integer, nullable=False, default=now_ts)
    last_login_at: Mapped[int | None] = mapped_column(Integer)


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(Text, primary_key=True)  # 客户端生成的 uuid
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str | None] = mapped_column(Text)  # 如 "Chrome 141"
    platform: Mapped[str | None] = mapped_column(Text)  # web / android
    app_version: Mapped[str | None] = mapped_column(Text)
    # 客户端上报的展示信息：系统、机型/形态、屏幕、原始 UA
    os: Mapped[str | None] = mapped_column(Text)
    form_factor: Mapped[str | None] = mapped_column(Text)  # phone / tablet / desktop
    screen: Mapped[str | None] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[int | None] = mapped_column(Integer)
    last_seen_at: Mapped[int | None] = mapped_column(Integer)
    # 客户端主动上报"离开"（关页面/切后台超时）；下一次请求会清空
    offline_at: Mapped[int | None] = mapped_column(Integer)
    # 非空 = 已踢下线：绑定的 access token 立即失效，refresh token 同时吊销
    revoked_at: Mapped[int | None] = mapped_column(Integer)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = (Index("idx_refresh_user", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    device_id: Mapped[str | None] = mapped_column(Text)
    # 只存 sha256，不存明文
    token_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    expires_at: Mapped[int] = mapped_column(Integer, nullable=False)
    revoked_at: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False, default=now_ts)
