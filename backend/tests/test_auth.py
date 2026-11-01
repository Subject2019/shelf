"""M1-T03 验收：登录/刷新/登出/me 全通，错误密码与过期 token 返回 401。"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.api.v1 import auth as auth_module
from app.core.security import hash_password
from app.db.base import now_ts
from app.db.session import get_session_factory
from app.models import User

PASSWORD = "secret123"
DEVICE = {
    "id": "dev-pytest",
    "name": "pytest",
    "platform": "web",
    "app_version": "0.2.8",
}


@pytest.fixture(autouse=True)
def clean_auth_tables(database):
    auth_module._failures.clear()
    session = get_session_factory()()
    session.execute(text("DELETE FROM refresh_tokens"))
    session.execute(text("DELETE FROM devices"))
    session.execute(text("DELETE FROM users"))
    session.commit()
    session.close()
    yield


def _create_user(
    username: str = "alice", password: str = PASSWORD, role: str = "admin"
) -> None:
    session = get_session_factory()()
    session.add(
        User(
            username=username,
            password_hash=hash_password(password),
            display_name=username,
            role=role,
            created_at=now_ts(),
        )
    )
    session.commit()
    session.close()


def _login(client, password: str = PASSWORD):
    return client.post(
        "/api/v1/auth/login",
        json={"username": "alice", "password": password, "device": DEVICE},
    )


def test_bootstrap_endpoint_removed(client) -> None:
    """管理员只能带外创建：网页初始化接口已下线。"""
    response = client.post(
        "/api/v1/auth/bootstrap",
        json={"username": "root", "password": "password123"},
    )
    # 路由已删除；SPA 静态挂载只接受 GET，所以 POST 落到 405
    assert response.status_code in (404, 405)


def test_initial_admin_from_env(client, monkeypatch) -> None:
    """Docker 环境变量创建的初始管理员只生效一次，不会覆盖已有密码。"""
    from app.core.config import get_settings
    from app.core.security import verify_password
    from app.main import _ensure_initial_admin
    from sqlalchemy import select

    settings = get_settings()
    monkeypatch.setattr(settings, "admin_username", "root")
    monkeypatch.setattr(settings, "admin_password", "envpass123")
    monkeypatch.setattr(settings, "admin_password_file", None)
    _ensure_initial_admin(settings)

    session = get_session_factory()()
    user = session.scalar(select(User).where(User.username == "root"))
    assert user is not None and user.role == "admin"
    assert verify_password(user.password_hash, "envpass123")

    # 再次启动（密码变了）不应覆盖
    monkeypatch.setattr(settings, "admin_password", "changed123")
    _ensure_initial_admin(settings)
    session.refresh(user)
    assert verify_password(user.password_hash, "envpass123")
    session.close()


def test_initial_admin_from_password_file(client, monkeypatch, tmp_path) -> None:
    from app.core.config import get_settings
    from app.main import _ensure_initial_admin
    from sqlalchemy import select

    secret = tmp_path / "admin.pass"
    secret.write_text("filepass123\n", encoding="utf-8")

    settings = get_settings()
    monkeypatch.setattr(settings, "admin_username", "fileadmin")
    monkeypatch.setattr(settings, "admin_password", None)
    monkeypatch.setattr(settings, "admin_password_file", str(secret))
    _ensure_initial_admin(settings)

    session = get_session_factory()()
    user = session.scalar(select(User).where(User.username == "fileadmin"))
    assert user is not None and user.role == "admin"
    session.close()


def test_login_and_me(client) -> None:
    _create_user()
    response = _login(client)
    assert response.status_code == 200

    body = response.json()
    assert body["user"]["username"] == "alice"
    assert body["user"]["role"] == "admin"
    assert body["expires_in"] == 1800

    me = client.get(
        "/api/v1/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["username"] == "alice"


def test_login_wrong_password(client) -> None:
    _create_user()
    response = _login(client, password="wrong-password")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_me_requires_token(client) -> None:
    response = client.get("/api/v1/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_invalid_access_token(client) -> None:
    response = client.get("/api/v1/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401


def test_refresh_rotates_and_revokes_old(client) -> None:
    _create_user()
    tokens = _login(client).json()

    first = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert first.status_code == 200
    rotated = first.json()
    assert rotated["refresh_token"] != tokens["refresh_token"]

    reused = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert reused.status_code == 401


def test_logout_revokes_refresh_token(client) -> None:
    _create_user()
    tokens = _login(client).json()

    assert (
        client.post(
            "/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]}
        ).status_code
        == 204
    )
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        ).status_code
        == 401
    )


def test_change_password_revokes_all_refresh_tokens(client) -> None:
    _create_user()
    tokens = _login(client).json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    changed = client.patch(
        "/api/v1/me/password",
        headers=headers,
        json={"old_password": PASSWORD, "new_password": "newsecret456"},
    )
    assert changed.status_code == 204

    assert _login(client, password=PASSWORD).status_code == 401
    assert _login(client, password="newsecret456").status_code == 200
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        ).status_code
        == 401
    )


def test_login_rate_limited_after_five_failures(client) -> None:
    _create_user()
    for _ in range(5):
        assert _login(client, password="wrong-password").status_code == 401

    blocked = _login(client)
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "too_many_requests"


def test_admin_password_sync_from_env(client, monkeypatch) -> None:
    """显式开启同步后，环境变量会成为管理员密码的事实来源。"""
    from sqlalchemy import select

    from app.core.config import get_settings
    from app.core.security import verify_password
    from app.main import _ensure_initial_admin
    from app.models import User

    _create_user(username="admin", password="oldpass123", role="admin")

    settings = get_settings()
    monkeypatch.setattr(settings, "admin_password", "newpass123")
    monkeypatch.setattr(settings, "admin_password_file", None)
    monkeypatch.setattr(settings, "admin_sync_password", True)
    _ensure_initial_admin(settings)

    session = get_session_factory()()
    user = session.scalar(select(User).where(User.username == "admin"))
    assert verify_password(user.password_hash, "newpass123")
    assert not verify_password(user.password_hash, "oldpass123")
    session.close()


def test_admin_password_not_synced_by_default(client, monkeypatch) -> None:
    """默认不同步：改环境变量重启不会覆盖网页里改过的密码。"""
    from sqlalchemy import select

    from app.core.config import get_settings
    from app.core.security import verify_password
    from app.main import _ensure_initial_admin
    from app.models import User

    _create_user(username="admin", password="oldpass123", role="admin")

    settings = get_settings()
    monkeypatch.setattr(settings, "admin_password", "newpass123")
    monkeypatch.setattr(settings, "admin_password_file", None)
    monkeypatch.setattr(settings, "admin_sync_password", False)
    _ensure_initial_admin(settings)

    session = get_session_factory()()
    user = session.scalar(select(User).where(User.username == "admin"))
    assert verify_password(user.password_hash, "oldpass123")
    assert not verify_password(user.password_hash, "newpass123")
    session.close()
