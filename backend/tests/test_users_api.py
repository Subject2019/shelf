"""用户管理、注册开关与书库级授权的端到端行为。"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text

from app.api.v1 import auth as auth_module
from app.core.config import get_settings
from app.core.security import hash_password
from app.db.base import now_ts
from app.db.session import get_session_factory
from app.models import Book, Library, LibraryUser, User

PASSWORD = "managepass123"

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


def _clean() -> None:
    session = get_session_factory()()
    for table in CLEAN_TABLES:
        session.execute(text(f"DELETE FROM {table}"))
    session.commit()
    session.close()


@pytest.fixture()
def users_env(tmp_path: Path):
    """两个受限书库：A 授权给 member，B 只授权给 admin。"""
    _clean()
    auth_module._failures.clear()

    session = get_session_factory()()
    now = now_ts()
    admin = User(
        username="admin",
        password_hash=hash_password(PASSWORD),
        display_name="管理员",
        role="admin",
        created_at=now,
    )
    member = User(
        username="member",
        password_hash=hash_password(PASSWORD),
        display_name="听众",
        role="listener",
        created_at=now,
    )
    session.add_all([admin, member])
    session.flush()

    lib_a = Library(name="A 库", root_path=str(tmp_path / "a"), created_at=now)
    lib_b = Library(name="B 库", root_path=str(tmp_path / "b"), created_at=now)
    session.add_all([lib_a, lib_b])
    session.flush()

    session.add_all(
        [
            LibraryUser(library_id=lib_a.id, user_id=admin.id),
            LibraryUser(library_id=lib_a.id, user_id=member.id),
            LibraryUser(library_id=lib_b.id, user_id=admin.id),
        ]
    )

    book_a = Book(
        library_id=lib_a.id,
        rel_dir="a/1",
        title="A 库的书",
        total_duration_sec=600.0,
        track_count=1,
        size_bytes=1024,
        chapter_source="virtual",
        added_at=now,
        updated_at=now,
    )
    book_b = Book(
        library_id=lib_b.id,
        rel_dir="b/1",
        title="B 库的书",
        total_duration_sec=600.0,
        track_count=1,
        size_bytes=1024,
        chapter_source="virtual",
        added_at=now,
        updated_at=now,
    )
    session.add_all([book_a, book_b])
    session.commit()

    yield {
        "admin_id": admin.id,
        "member_id": member.id,
        "lib_a": lib_a.id,
        "lib_b": lib_b.id,
        "book_a": book_a.id,
        "book_b": book_b.id,
    }
    session.close()


def _login(client, username: str = "admin", password: str = PASSWORD):
    return client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )


def _headers(
    client, username: str = "admin", password: str = PASSWORD
) -> dict[str, str]:
    response = _login(client, username, password)
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_list_users_requires_admin(client, users_env):
    assert client.get("/api/v1/users").status_code == 401
    assert (
        client.get("/api/v1/users", headers=_headers(client, "member")).status_code
        == 403
    )

    response = client.get("/api/v1/users", headers=_headers(client))
    assert response.status_code == 200
    usernames = [item["username"] for item in response.json()["items"]]
    assert usernames == ["admin", "member"]


def test_create_user_with_library_grant(client, users_env):
    headers = _headers(client)
    response = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "username": "NewUser",
            "password": "newpass123",
            "display_name": "新用户",
            "role": "listener",
            "library_ids": [users_env["lib_a"]],
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    # 用户名统一小写
    assert payload["username"] == "newuser"
    assert payload["libraries"] == [users_env["lib_a"]]

    # 新用户只能看到 A 库：列表、直连、书库接口都受限
    member_headers = _headers(client, "newuser", "newpass123")
    libraries = client.get("/api/v1/libraries", headers=member_headers).json()
    assert [item["id"] for item in libraries["items"]] == [users_env["lib_a"]]
    assert (
        client.get(
            f"/api/v1/books/{users_env['book_b']}", headers=member_headers
        ).status_code
        == 403
    )
    assert (
        client.get(
            f"/api/v1/books?library_id={users_env['lib_b']}", headers=member_headers
        ).status_code
        == 403
    )
    assert (
        client.get(
            f"/api/v1/books/{users_env['book_a']}", headers=member_headers
        ).status_code
        == 200
    )


def test_duplicate_username_conflicts(client, users_env):
    response = client.post(
        "/api/v1/users",
        headers=_headers(client),
        json={"username": "MEMBER", "password": "whatever123"},
    )
    assert response.status_code == 409


def test_cannot_demote_or_disable_self(client, users_env):
    headers = _headers(client)
    admin_id = users_env["admin_id"]

    demote = client.patch(
        f"/api/v1/users/{admin_id}", headers=headers, json={"role": "listener"}
    )
    assert demote.status_code == 409

    disable = client.patch(
        f"/api/v1/users/{admin_id}", headers=headers, json={"is_active": False}
    )
    assert disable.status_code == 409

    delete = client.delete(f"/api/v1/users/{admin_id}", headers=headers)
    assert delete.status_code == 409


def test_disable_user_revokes_refresh_token(client, users_env):
    login = _login(client, "member")
    refresh_token = login.json()["refresh_token"]

    headers = _headers(client)
    response = client.patch(
        f"/api/v1/users/{users_env['member_id']}",
        headers=headers,
        json={"is_active": False},
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False

    refreshed = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
    )
    assert refreshed.status_code == 401

    # 停用后旧的 access token 也不再可用
    member_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/v1/libraries", headers=member_headers).status_code == 401


def test_reset_password_revokes_old_sessions(client, users_env):
    member_login = _login(client, "member")
    refresh_token = member_login.json()["refresh_token"]

    headers = _headers(client)
    updated = client.patch(
        f"/api/v1/users/{users_env['member_id']}",
        headers=headers,
        json={"password": "brandnew123"},
    )
    assert updated.status_code == 200

    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
        ).status_code
        == 401
    )
    assert _login(client, "member", "brandnew123").status_code == 200
    assert _login(client, "member", PASSWORD).status_code == 401


def test_update_library_grant_replaces_set(client, users_env):
    headers = _headers(client)
    response = client.patch(
        f"/api/v1/users/{users_env['member_id']}",
        headers=headers,
        json={"library_ids": [users_env["lib_b"]]},
    )
    assert response.status_code == 200
    assert response.json()["libraries"] == [users_env["lib_b"]]

    member_headers = _headers(client, "member")
    assert (
        client.get(
            f"/api/v1/books/{users_env['book_a']}", headers=member_headers
        ).status_code
        == 403
    )
    assert (
        client.get(
            f"/api/v1/books/{users_env['book_b']}", headers=member_headers
        ).status_code
        == 200
    )


def test_unknown_library_rejected(client, users_env):
    response = client.patch(
        f"/api/v1/users/{users_env['member_id']}",
        headers=_headers(client),
        json={"library_ids": [9999]},
    )
    assert response.status_code == 400


def test_delete_user_removes_account(client, users_env):
    headers = _headers(client)
    created = client.post(
        "/api/v1/users",
        headers=headers,
        json={"username": "tempuser", "password": "temppass123"},
    )
    user_id = created.json()["id"]

    assert client.delete(f"/api/v1/users/{user_id}", headers=headers).status_code == 204
    assert _login(client, "tempuser", "temppass123").status_code == 401


def test_register_respects_switch(client, users_env, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "allow_registration", False)
    blocked = client.post(
        "/api/v1/auth/register",
        json={"username": "selfsign", "password": "selfpass123"},
    )
    assert blocked.status_code == 403

    monkeypatch.setattr(settings, "allow_registration", True)
    created = client.post(
        "/api/v1/auth/register",
        json={
            "username": "SelfSign",
            "password": "selfpass123",
            "device": {"id": "web-selfsign", "name": "浏览器", "platform": "web"},
        },
    )
    assert created.status_code == 201, created.text
    payload = created.json()
    assert payload["user"]["username"] == "selfsign"
    assert payload["user"]["role"] == "listener"
    assert payload["user"]["libraries"] == []

    headers = {"Authorization": f"Bearer {payload['access_token']}"}
    assert client.get("/api/v1/libraries", headers=headers).status_code == 200


# ---------------------------------------------------------------- 三级角色


def test_created_user_defaults_to_listener(client, users_env) -> None:
    response = client.post(
        "/api/v1/users",
        headers=_headers(client),
        json={"username": "defaultrole", "password": "defaultpass123"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["role"] == "listener"


def test_legacy_user_role_is_rejected(client, users_env) -> None:
    """旧的 `user` 取值不再接受，避免与新语义混淆。"""
    response = client.post(
        "/api/v1/users",
        headers=_headers(client),
        json={"username": "oldrole", "password": "oldpass123", "role": "user"},
    )
    assert response.status_code == 422


def test_editor_can_edit_metadata_listener_cannot(client, users_env) -> None:
    admin_headers = _headers(client)
    for username, role in (("bookeditor", "editor"), ("booklistener", "listener")):
        created = client.post(
            "/api/v1/users",
            headers=admin_headers,
            json={
                "username": username,
                "password": "rolepass123",
                "role": role,
                "library_ids": [users_env["lib_a"]],
            },
        )
        assert created.status_code == 201, created.text

    editor = _headers(client, "bookeditor", "rolepass123")
    listener = _headers(client, "booklistener", "rolepass123")
    book_id = users_env["book_a"]

    edited = client.patch(
        f"/api/v1/books/{book_id}", headers=editor, json={"title": "编辑者改的书名"}
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["title"] == "编辑者改的书名"

    denied = client.patch(
        f"/api/v1/books/{book_id}", headers=listener, json={"title": "听众不该能改"}
    )
    assert denied.status_code == 403

    # 听众仍然可以读
    assert client.get(f"/api/v1/books/{book_id}", headers=listener).status_code == 200


def test_role_can_be_changed_between_three_levels(client, users_env) -> None:
    headers = _headers(client)
    created = client.post(
        "/api/v1/users",
        headers=headers,
        json={"username": "promote", "password": "promotepass123", "role": "listener"},
    )
    user_id = created.json()["id"]

    promoted = client.patch(
        f"/api/v1/users/{user_id}", headers=headers, json={"role": "editor"}
    )
    assert promoted.status_code == 200
    assert promoted.json()["role"] == "editor"

    demoted = client.patch(
        f"/api/v1/users/{user_id}", headers=headers, json={"role": "listener"}
    )
    assert demoted.status_code == 200
    assert demoted.json()["role"] == "listener"


def test_listener_cannot_touch_library_or_users(client, users_env) -> None:
    created = client.post(
        "/api/v1/users",
        headers=_headers(client),
        json={
            "username": "nothinguser",
            "password": "nothingpass123",
            "role": "listener",
            "library_ids": [users_env["lib_a"]],
        },
    )
    assert created.status_code == 201
    listener = _headers(client, "nothinguser", "nothingpass123")

    assert client.get("/api/v1/users", headers=listener).status_code == 403
    assert (
        client.post(
            "/api/v1/libraries",
            headers=listener,
            json={"name": "不该建出来的库", "root_path": "/tmp/whatever"},
        ).status_code
        == 403
    )


# ---------------------------------------------------------------- 管理员唯一


def test_cannot_create_admin_via_api(client, users_env) -> None:
    response = client.post(
        "/api/v1/users",
        headers=_headers(client),
        json={"username": "admin2", "password": "adminpass123", "role": "admin"},
    )
    assert response.status_code == 422


def test_cannot_promote_user_to_admin(client, users_env) -> None:
    created = client.post(
        "/api/v1/users",
        headers=_headers(client),
        json={"username": "promote2", "password": "promotepass123", "role": "editor"},
    )
    assert created.status_code == 201
    user_id = created.json()["id"]

    promoted = client.patch(
        f"/api/v1/users/{user_id}",
        headers=_headers(client),
        json={"role": "admin"},
    )
    assert promoted.status_code == 422
    assert promoted.json()["error"]["code"] == "validation_error"


def test_admin_row_role_unchanged(client, users_env) -> None:
    """管理员自己仍然是 admin；接口列表里只有这一个管理员。"""
    users = client.get("/api/v1/users", headers=_headers(client)).json()["items"]
    admins = [item["username"] for item in users if item["role"] == "admin"]
    assert admins == ["admin"]


# ---------------------------------------------------------------- 书籍隐藏


def test_admin_can_hide_book(client, users_env) -> None:
    from app.db.session import get_session_factory
    from app.models import Book

    admin = _headers(client)
    book_id = users_env["book_a"]

    hidden = client.patch(
        f"/api/v1/books/{book_id}", headers=admin, json={"hidden": True}
    )
    assert hidden.status_code == 200
    assert hidden.json()["hidden"] is True

    # 只是切换可见性，不该打上「手工改元数据」
    session = get_session_factory()()
    assert session.get(Book, book_id).manual_override is False
    session.close()

    # 管理员默认列表也不含隐藏书，显式 include_hidden 才看得到
    ids = [
        item["id"]
        for item in client.get("/api/v1/books", headers=admin).json()["items"]
    ]
    assert book_id not in ids
    ids = [
        item["id"]
        for item in client.get(
            "/api/v1/books?include_hidden=true", headers=admin
        ).json()["items"]
    ]
    assert book_id in ids

    # 听众：列表、详情、搜索都看不到；强行 include_hidden 被拒
    member = _headers(client, "member")
    ids = [
        item["id"]
        for item in client.get("/api/v1/books", headers=member).json()["items"]
    ]
    assert book_id not in ids
    assert client.get(f"/api/v1/books/{book_id}", headers=member).status_code == 404
    assert (
        client.get("/api/v1/books?include_hidden=true", headers=member).status_code
        == 403
    )

    # 取消隐藏后恢复可见
    restored = client.patch(
        f"/api/v1/books/{book_id}", headers=admin, json={"hidden": False}
    )
    assert restored.json()["hidden"] is False
    ids = [
        item["id"]
        for item in client.get("/api/v1/books", headers=member).json()["items"]
    ]
    assert book_id in ids


def test_editor_cannot_hide_book(client, users_env) -> None:
    admin = _headers(client)
    created = client.post(
        "/api/v1/users",
        headers=admin,
        json={
            "username": "editor2",
            "password": "editorpass123",
            "role": "editor",
            "library_ids": [users_env["lib_a"]],
        },
    )
    assert created.status_code == 201

    headers = _headers(client, "editor2", "editorpass123")
    response = client.patch(
        f"/api/v1/books/{users_env['book_a']}", headers=headers, json={"hidden": True}
    )
    assert response.status_code == 403
