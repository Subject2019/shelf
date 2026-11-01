"""书单接口验收：CRUD、书籍成员和用户隔离。"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text

from app.api.v1 import auth as auth_module
from app.core.security import hash_password
from app.db.base import now_ts
from app.db.session import get_session_factory
from app.models import Book, Library, User

PASSWORD = "collectionpass123"

CLEAN_TABLES = (
    "chapters",
    "tracks",
    "collection_books",
    "collections",
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
def collection_data(database, tmp_path: Path):
    auth_module._failures.clear()
    session = get_session_factory()()
    for table in CLEAN_TABLES:
        session.execute(text(f"DELETE FROM {table}"))
    session.commit()

    now = now_ts()
    media_dir = tmp_path / "library"
    media_dir.mkdir()
    (media_dir / "book.mp3").write_bytes(b"x" * 16)

    admin = User(
        username="admin",
        password_hash=hash_password(PASSWORD),
        role="admin",
        created_at=now,
    )
    other = User(
        username="other",
        password_hash=hash_password(PASSWORD),
        role="user",
        created_at=now,
    )
    library = Library(name="测试库", root_path=str(media_dir), created_at=now)
    session.add_all([admin, other, library])
    session.flush()

    book = Book(
        library_id=library.id,
        rel_dir="book",
        title="三体",
        total_duration_sec=300.0,
        track_count=1,
        size_bytes=16,
        chapter_source="virtual",
        added_at=now,
        updated_at=now,
    )
    session.add(book)
    session.commit()

    data = {
        "book_id": book.id,
        "admin_id": admin.id,
        "other_id": other.id,
    }
    session.close()
    return data


def _login(client, username: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login", json={"username": username, "password": PASSWORD}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def headers(client, collection_data) -> dict[str, str]:
    return _login(client, "admin")


@pytest.fixture()
def other_headers(client, collection_data) -> dict[str, str]:
    return _login(client, "other")


def test_collection_crud_and_duplicate_name(client, headers) -> None:
    created = client.post(
        "/api/v1/collections",
        headers=headers,
        json={"name": "  待听  "},
    )
    assert created.status_code == 201
    payload = created.json()
    assert payload["name"] == "待听"
    assert payload["book_count"] == 0
    collection_id = payload["id"]

    duplicate = client.post(
        "/api/v1/collections",
        headers=headers,
        json={"name": "待听"},
    )
    assert duplicate.status_code == 409

    listing = client.get("/api/v1/collections", headers=headers)
    assert listing.status_code == 200
    assert [item["name"] for item in listing.json()["items"]] == ["待听"]

    renamed = client.patch(
        f"/api/v1/collections/{collection_id}",
        headers=headers,
        json={"name": "推理"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "推理"

    assert (
        client.delete(f"/api/v1/collections/{collection_id}", headers=headers).status_code
        == 204
    )
    assert client.get(f"/api/v1/collections/{collection_id}", headers=headers).status_code == 404


def test_add_remove_book_and_membership(client, headers, collection_data) -> None:
    book_id = collection_data["book_id"]
    collection_id = client.post(
        "/api/v1/collections",
        headers=headers,
        json={"name": "科幻"},
    ).json()["id"]

    added = client.post(
        f"/api/v1/collections/{collection_id}/books",
        headers=headers,
        json={"book_id": book_id},
    )
    assert added.status_code == 200
    assert added.json()["book_count"] == 1

    listing = client.get(
        f"/api/v1/collections?book_id={book_id}",
        headers=headers,
    )
    assert listing.status_code == 200
    assert listing.json()["items"][0]["contains_book"] is True

    detail = client.get(
        f"/api/v1/collections/{collection_id}",
        headers=headers,
    )
    assert detail.status_code == 200
    assert detail.json()["books"][0]["title"] == "三体"

    assert (
        client.delete(
            f"/api/v1/collections/{collection_id}/books/{book_id}",
            headers=headers,
        ).status_code
        == 204
    )
    detail = client.get(
        f"/api/v1/collections/{collection_id}",
        headers=headers,
    )
    assert detail.json()["books"] == []
    assert detail.json()["book_count"] == 0


def test_collection_is_private_to_owner(
    client,
    headers,
    other_headers,
    collection_data,
) -> None:
    book_id = collection_data["book_id"]
    collection_id = client.post(
        "/api/v1/collections",
        headers=headers,
        json={"name": "私人书单"},
    ).json()["id"]

    assert (
        client.get(f"/api/v1/collections/{collection_id}", headers=other_headers).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/v1/collections/{collection_id}",
            headers=other_headers,
            json={"name": "篡改"},
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/v1/collections/{collection_id}", headers=other_headers).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/collections/{collection_id}/books",
            headers=other_headers,
            json={"book_id": book_id},
        ).status_code
        == 404
    )
    assert client.get("/api/v1/collections", headers=other_headers).json()["items"] == []
