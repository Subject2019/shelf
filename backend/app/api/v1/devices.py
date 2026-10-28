"""设备管理：在线状态与踢下线。

踢下线 = 标记 `devices.revoked_at` + 吊销该设备所有 refresh token。
由于 access token 里带了 `did` 声明，`get_current_user` 会检查设备状态，
所以旧 access token 也会立刻失效，而不是等 30 分钟自然过期。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.base import now_ts
from app.db.session import get_db
from app.models import Device, RefreshToken, User
from app.schemas.device import DeviceList, DeviceOut, DeviceUpdateIn, PresenceIn

router = APIRouter(tags=["devices"])

# 网页端每 45 秒心跳一次；2 分钟窗口留给后台标签页与网络抖动
ONLINE_WINDOW_SEC = 120


def _online(device: Device, now: int) -> bool:
    if device.revoked_at is not None or device.last_seen_at is None:
        return False
    if device.offline_at is not None:
        return False
    return now - device.last_seen_at <= ONLINE_WINDOW_SEC


def _to_out(device: Device, username: str | None, now: int) -> DeviceOut:
    return DeviceOut(
        id=device.id,
        user_id=device.user_id,
        username=username,
        name=device.name,
        platform=device.platform,
        app_version=device.app_version,
        os=device.os,
        form_factor=device.form_factor,
        screen=device.screen,
        user_agent=device.user_agent,
        created_at=device.created_at,
        last_seen_at=device.last_seen_at,
        revoked_at=device.revoked_at,
        offline_at=device.offline_at,
        online=_online(device, now),
    )


@router.get("/devices", response_model=DeviceList)
def list_devices(
    all: bool = Query(False, description="管理员可查看所有用户的设备"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeviceList:
    now = now_ts()
    query = select(Device).order_by(Device.last_seen_at.desc().nullslast(), Device.id)
    if not (all and current_user.role == "admin"):
        query = query.where(Device.user_id == current_user.id)

    devices = db.scalars(query).all()
    usernames = {
        user.id: user.username
        for user in db.scalars(
            select(User).where(User.id.in_({item.user_id for item in devices}))
        )
    }
    return DeviceList(
        items=[_to_out(item, usernames.get(item.user_id), now) for item in devices]
    )


def _load(db: Session, user: User, device_id: str) -> Device:
    device = db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="设备不存在")
    if device.user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="无权操作该设备")
    return device


@router.patch("/devices/{device_id}", response_model=DeviceOut)
def rename_device(
    device_id: str,
    payload: DeviceUpdateIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeviceOut:
    device = _load(db, current_user, device_id)
    device.name = payload.name.strip()
    db.commit()
    db.refresh(device)
    return _to_out(device, None, now_ts())


@router.post("/devices/{device_id}/presence", response_model=DeviceOut)
def set_presence(
    device_id: str,
    payload: PresenceIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeviceOut:
    """在线心跳 / 主动下线。

    客户端在页面可见时定期上报 `online=true`；关闭页面、切后台超时或 App 退到后台时
    上报 `online=false`。离线状态下只要再发任何请求（含本接口的 true）就会恢复。
    """
    device = _load(db, current_user, device_id)
    now = now_ts()
    device.last_seen_at = now
    device.offline_at = None if payload.online else now
    db.commit()
    db.refresh(device)
    return _to_out(device, None, now)


@router.delete("/devices/{device_id}", status_code=204)
def kick_device(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """踢下线：该设备的 access / refresh token 立刻失效。"""
    device = _load(db, current_user, device_id)
    now = now_ts()
    if device.revoked_at is None:
        device.revoked_at = now

    for token in db.scalars(
        select(RefreshToken).where(
            RefreshToken.device_id == device.id,
            RefreshToken.revoked_at.is_(None),
        )
    ):
        token.revoked_at = now

    db.commit()
    return Response(status_code=204)
