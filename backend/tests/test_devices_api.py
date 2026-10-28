"""设备列表、在线状态与踢下线。"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.api.v1 import auth as auth_module
from app.core.security import hash_password
from app.db.base import now_ts
from app.db.session import get_session_factory
from app.models import User

PASSWORD = "devicepass123"

CLEAN_TABLES = (
    "chapters",
    "tracks",
    "collection_books",
    "bookmarks",
    "progress",
    "media_files",
    "books",
    "scan_tasks",
    "library_users",
    "libraries",
    "refresh_tokens",
    "devices",
    "users",
)


@pytest.fixture()
def device_env():
    auth_module._failures.clear()
    session = get_session_factory()()
    for table in CLEAN_TABLES:
        session.execute(text(f"DELETE FROM {table}"))
    now = now_ts()
    session.add_all(
        [
            User(
                username="admin",
                password_hash=hash_password(PASSWORD),
                role="admin",
                created_at=now,
            ),
            User(
                username="member",
                password_hash=hash_password(PASSWORD),
                role="user",
                created_at=now,
            ),
        ]
    )
    session.commit()
    session.close()


def _login(client, username: str, device_id: str, name: str, platform: str):
    return client.post(
        "/api/v1/auth/login",
        json={
            "username": username,
            "password": PASSWORD,
            "device": {
                "id": device_id,
                "name": name,
                "platform": platform,
                "app_version": "0.1.0",
            },
        },
    )


def test_login_registers_device_and_lists_it(client, device_env):
    login = _login(client, "admin", "web-admin", "Chrome", "web")
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.get("/api/v1/devices", headers=headers)
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    device = items[0]
    assert device["id"] == "web-admin"
    assert device["name"] == "Chrome"
    assert device["platform"] == "web"
    assert device["online"] is True
    assert device["revoked_at"] is None


def test_device_profile_is_stored_and_returned(client, device_env):
    """浏览器 / 系统 / 形态 / 屏幕 / UA 都要能回显。"""
    user_agent = (
        "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36"
    )
    login = client.post(
        "/api/v1/auth/login",
        json={
            "username": "member",
            "password": PASSWORD,
            "device": {
                "id": "web-profile",
                "name": "Chrome 141",
                "platform": "web",
                "app_version": "0.1.0",
                "os": "Android 14",
                "form_factor": "phone",
                "screen": "390×844 · 3x",
                "user_agent": user_agent,
            },
        },
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    device = client.get("/api/v1/devices", headers=headers).json()["items"][0]
    assert device["name"] == "Chrome 141"
    assert device["os"] == "Android 14"
    assert device["form_factor"] == "phone"
    assert device["screen"] == "390×844 · 3x"
    assert device["user_agent"] == user_agent
    assert device["created_at"] is not None

    # 老客户端再次登录（不带这些字段）不应把已有信息清空
    again = client.post(
        "/api/v1/auth/login",
        json={
            "username": "member",
            "password": PASSWORD,
            "device": {"id": "web-profile", "name": "网页版", "platform": "web"},
        },
    )
    assert again.status_code == 200
    headers = {"Authorization": f"Bearer {again.json()['access_token']}"}
    device = client.get("/api/v1/devices", headers=headers).json()["items"][0]
    assert device["os"] == "Android 14"
    assert device["screen"] == "390×844 · 3x"
    assert device["name"] == "网页版"


def test_member_only_sees_own_devices_admin_sees_all(client, device_env):
    admin = _login(client, "admin", "web-admin", "Chrome", "web")
    member = _login(client, "member", "android-1", "Pixel", "android")
    admin_headers = {"Authorization": f"Bearer {admin.json()['access_token']}"}
    member_headers = {"Authorization": f"Bearer {member.json()['access_token']}"}

    own = client.get("/api/v1/devices", headers=member_headers).json()["items"]
    assert [item["id"] for item in own] == ["android-1"]

    everything = client.get("/api/v1/devices?all=true", headers=admin_headers).json()[
        "items"
    ]
    assert {item["id"] for item in everything} == {"web-admin", "android-1"}
    usernames = {item["id"]: item["username"] for item in everything}
    assert usernames == {"web-admin": "admin", "android-1": "member"}


def test_member_cannot_kick_others_device(client, device_env):
    admin = _login(client, "admin", "web-admin", "Chrome", "web")
    member = _login(client, "member", "android-1", "Pixel", "android")
    member_headers = {"Authorization": f"Bearer {member.json()['access_token']}"}

    response = client.delete("/api/v1/devices/web-admin", headers=member_headers)
    assert response.status_code == 403
    # 管理员设备仍然可用
    admin_headers = {"Authorization": f"Bearer {admin.json()['access_token']}"}
    assert client.get("/api/v1/devices", headers=admin_headers).status_code == 200


def test_kick_revokes_access_and_refresh_immediately(client, device_env):
    member = _login(client, "member", "android-1", "Pixel", "android")
    member_access = member.json()["access_token"]
    member_refresh = member.json()["refresh_token"]

    admin = _login(client, "admin", "web-admin", "Chrome", "web")
    admin_headers = {"Authorization": f"Bearer {admin.json()['access_token']}"}

    kicked = client.delete("/api/v1/devices/android-1", headers=admin_headers)
    assert kicked.status_code == 204

    # access token 立刻失效（不等 30 分钟）
    stale = {"Authorization": f"Bearer {member_access}"}
    assert client.get("/api/v1/devices", headers=stale).status_code == 401
    # refresh token 也失效
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": member_refresh}
        ).status_code
        == 401
    )

    devices = client.get("/api/v1/devices?all=true", headers=admin_headers).json()[
        "items"
    ]
    kicked_device = next(item for item in devices if item["id"] == "android-1")
    assert kicked_device["revoked_at"] is not None
    assert kicked_device["online"] is False


def test_kicked_device_can_login_again(client, device_env):
    """踢下线只让旧会话失效，重新登录应当恢复正常。"""
    _login(client, "member", "android-1", "Pixel", "android")
    admin = _login(client, "admin", "web-admin", "Chrome", "web")
    admin_headers = {"Authorization": f"Bearer {admin.json()['access_token']}"}

    assert (
        client.delete("/api/v1/devices/android-1", headers=admin_headers).status_code
        == 204
    )

    again = _login(client, "member", "android-1", "Pixel", "android")
    assert again.status_code == 200
    headers = {"Authorization": f"Bearer {again.json()['access_token']}"}
    assert client.get("/api/v1/devices", headers=headers).status_code == 200

    devices = client.get("/api/v1/devices", headers=headers).json()["items"]
    assert devices[0]["revoked_at"] is None
    assert devices[0]["online"] is True


def test_presence_offline_then_auto_online(client, device_env):
    """主动下线后立即离线；下一次任意请求自动恢复在线。"""
    login = _login(client, "member", "web-1", "Chrome 141", "web")
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert client.get("/api/v1/devices", headers=headers).json()["items"][0]["online"]

    offline = client.post(
        "/api/v1/devices/web-1/presence", headers=headers, json={"online": False}
    )
    assert offline.status_code == 200, offline.text
    assert offline.json()["online"] is False
    assert offline.json()["offline_at"] is not None

    # 别人（管理员）看到的也是离线
    admin = _login(client, "admin", "web-admin", "Chrome", "web")
    admin_headers = {"Authorization": f"Bearer {admin.json()['access_token']}"}
    items = client.get("/api/v1/devices?all=true", headers=admin_headers).json()[
        "items"
    ]
    target = next(item for item in items if item["id"] == "web-1")
    assert target["online"] is False

    # 该设备再发一次请求（这里借 GET /devices）就恢复在线
    back = client.get("/api/v1/devices", headers=headers).json()["items"][0]
    assert back["online"] is True
    assert back["offline_at"] is None


def test_presence_requires_ownership(client, device_env):
    admin = _login(client, "admin", "web-admin", "Chrome", "web")
    member = _login(client, "member", "web-1", "Chrome", "web")
    member_headers = {"Authorization": f"Bearer {member.json()['access_token']}"}

    # 成员不能改管理员的设备
    forbidden = client.post(
        "/api/v1/devices/web-admin/presence",
        headers=member_headers,
        json={"online": False},
    )
    assert forbidden.status_code == 403

    # 管理员可以代发
    admin_headers = {"Authorization": f"Bearer {admin.json()['access_token']}"}
    allowed = client.post(
        "/api/v1/devices/web-1/presence",
        headers=admin_headers,
        json={"online": False},
    )
    assert allowed.status_code == 200
    assert allowed.json()["online"] is False

    assert (
        client.post(
            "/api/v1/devices/web-1/presence", json={"online": False}
        ).status_code
        == 401
    )


def test_rename_device(client, device_env):
    login = _login(client, "member", "android-1", "Pixel", "android")
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.patch(
        "/api/v1/devices/android-1", headers=headers, json={"name": "Pixel 8 Pro"}
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Pixel 8 Pro"


def test_unknown_device_returns_404(client, device_env):
    login = _login(client, "admin", "web-admin", "Chrome", "web")
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.delete("/api/v1/devices/nope", headers=headers).status_code == 404


def test_token_without_device_still_works(client, device_env):
    """老客户端不带 device 登录，不应被设备校验挡住。"""
    login = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": PASSWORD}
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/v1/devices", headers=headers).json()["items"] == []
    assert client.get("/api/v1/libraries", headers=headers).status_code == 200
