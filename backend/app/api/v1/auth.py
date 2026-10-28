"""认证接口。路由用同步 def：FastAPI 会放到线程池，避免 SQLite 阻塞事件循环。"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)
from app.db.base import now_ts
from app.db.session import get_db
from app.models import Device, RefreshToken, User
from app.services.permissions import visible_library_ids
from app.schemas.auth import (
    DeviceIn,
    LoginRequest,
    PasswordChangeRequest,
    RefreshRequest,
    TokenResponse,
    UserOut,
)
from app.schemas.user import RegisterIn

router = APIRouter(tags=["auth"])

# 单进程部署（ARCHITECTURE §1），进程内计数即可；重启清零可接受
_MAX_FAILURES = 5
_LOCK_SECONDS = 300
_failures: dict[str, tuple[int, float]] = {}


def _ensure_not_locked(username: str) -> None:
    _, locked_until = _failures.get(username, (0, 0.0))
    if locked_until > time.time():
        raise HTTPException(status_code=429, detail="登录失败次数过多，请稍后再试")


def _record_failure(username: str) -> None:
    count, _ = _failures.get(username, (0, 0.0))
    count += 1
    locked_until = time.time() + _LOCK_SECONDS if count >= _MAX_FAILURES else 0.0
    _failures[username] = (count, locked_until)


def _reset_failures(username: str) -> None:
    _failures.pop(username, None)


def _user_out(db: Session, user: User) -> UserOut:
    return UserOut(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        libraries=visible_library_ids(db, user),
        created_at=user.created_at,
    )


def _save_device(
    db: Session, user: User, info: DeviceIn | None, now: int
) -> str | None:
    """登记/更新设备，返回设备 id（未提供则不绑定设备）。"""
    if info is None:
        return None

    device = db.get(Device, info.id)
    if device is None:
        device = Device(id=info.id)
        db.add(device)
    device.user_id = user.id
    device.name = info.name
    device.platform = info.platform
    device.app_version = info.app_version
    # 旧客户端不传这些字段，只在有值时覆盖，避免把已有信息清空
    if info.os is not None:
        device.os = info.os
    if info.form_factor is not None:
        device.form_factor = info.form_factor
    if info.screen is not None:
        device.screen = info.screen
    if info.user_agent is not None:
        device.user_agent = info.user_agent
    if device.created_at is None:
        device.created_at = now
    device.last_seen_at = now
    # 被踢下线的设备重新登录即恢复：踢下线只阻断旧会话，不封禁这台机器
    device.revoked_at = None
    return info.id


def _issue_tokens(db: Session, user: User, device_id: str | None) -> TokenResponse:
    settings = get_settings()
    access_token, expires_in = create_access_token(user.id, device_id)
    plain_refresh, digest = new_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            device_id=device_id,
            token_hash=digest,
            expires_at=now_ts() + settings.refresh_token_ttl_sec,
        )
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=plain_refresh,
        expires_in=expires_in,
        user=_user_out(db, user),
    )


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    username = payload.username.strip().lower()
    _ensure_not_locked(username)

    user = db.scalar(select(User).where(User.username == username))
    if (
        user is None
        or not user.is_active
        or not verify_password(user.password_hash, payload.password)
    ):
        _record_failure(username)
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    _reset_failures(username)
    now = now_ts()
    user.last_login_at = now

    device_id = _save_device(db, user, payload.device, now)

    tokens = _issue_tokens(db, user, device_id)
    db.commit()
    return tokens


@router.post("/auth/register", response_model=TokenResponse, status_code=201)
def register(payload: RegisterIn, db: Session = Depends(get_db)) -> TokenResponse:
    """自助注册。仅在 `ECHOSHELF_ALLOW_REGISTRATION=true` 时开放。

    新账号角色固定为 `listener`（只读），没有任何书库授权——需要管理员在设置页分配。
    """
    settings = get_settings()
    if not settings.allow_registration:
        raise HTTPException(status_code=403, detail="未开放注册，请联系管理员创建账号")

    username = payload.username.strip().lower()
    exists = db.scalar(select(User.id).where(User.username == username))
    if exists:
        raise HTTPException(status_code=409, detail="用户名已存在")

    now = now_ts()
    user = User(
        username=username,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        role="listener",
        is_active=True,
        created_at=now,
        last_login_at=now,
    )
    db.add(user)
    db.flush()
    device_id = _save_device(db, user, payload.device, now)
    tokens = _issue_tokens(db, user, device_id)
    db.commit()
    return tokens


@router.post("/auth/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    digest = hash_refresh_token(payload.refresh_token)
    token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == digest))
    now = now_ts()
    if token is None or token.revoked_at is not None or token.expires_at <= now:
        raise HTTPException(status_code=401, detail="refresh token 无效或已过期")

    user = db.get(User, token.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="账号不可用")

    token.revoked_at = now  # 旋转：旧的立即吊销
    tokens = _issue_tokens(db, user, token.device_id)
    db.commit()
    return tokens


@router.post("/auth/logout", status_code=204)
def logout(payload: RefreshRequest, db: Session = Depends(get_db)) -> Response:
    digest = hash_refresh_token(payload.refresh_token)
    token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == digest))
    if token is not None and token.revoked_at is None:
        token.revoked_at = now_ts()
        db.commit()
    # 幂等：token 不存在也返回 204，避免客户端退出失败
    return Response(status_code=204)


@router.get("/me", response_model=UserOut)
def read_me(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> UserOut:
    return _user_out(db, current_user)


@router.patch("/me/password", status_code=204)
def change_password(
    payload: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    if not verify_password(current_user.password_hash, payload.old_password):
        raise HTTPException(status_code=400, detail="原密码不正确")

    current_user.password_hash = hash_password(payload.new_password)
    db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == current_user.id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now_ts())
    )
    db.commit()
    return Response(status_code=204)
