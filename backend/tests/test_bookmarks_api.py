"""M1-T07 验收：书签增删改查与越权保护。"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text

from app.api.v1 import auth as auth_module
from app.core.security import hash_password
from app.db.base import now_ts
from app.db.session import get_session_factory
from app.models import Book, Bookmark, Library, LibraryUser, MediaFile, Track, User

PASSWORD = "bookmarkpass123"

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
def bookmark_data(database, tmp_path: Path):
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
    library = Library(name="测试库", root_path=str(media_dir), created_at=now)
    session.add_all([admin, library])
    session.flush()

    media = MediaFile(
        library_id=library.id,
        rel_path="book.mp3",
        format="mp3",
        size_bytes=16,
        mtime=now,
        first_seen_at=now,
        last_seen_at=now,
    )
    session.add(media)
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
    session.flush()

    track = Track(
        book_id=book.id,
        media_file_id=media.id,
        track_no=1,
        duration_sec=300.0,
        start_offset_sec=0.0,
    )
    session.add(track)
    session.flush()

    other = User(
        username="other",
        password_hash=hash_password(PASSWORD),
        role="user",
        created_at=now,
    )
    session.add(other)
    session.commit()

    data = {
        "library_id": library.id,
        "book_id": book.id,
        "track_id": track.id,
        "admin_id": admin.id,
        "other_id": other.id,
    }
    session.close()
    return data


@pytest.fixture()
def headers(client, bookmark_data) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": PASSWORD}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_create_and_list_bookmarks_sorted(client, headers, bookmark_data) -> None:
    book_id = bookmark_data["book_id"]
    track_id = bookmark_data["track_id"]

    later = client.post(
        f"/api/v1/books/{book_id}/bookmarks",
        headers=headers,
        json={"position_sec": 200.0, "track_id": track_id, "note": "后面"},
    )
    assert later.status_code == 201
    assert later.json()["note"] == "后面"

    earlier = client.post(
        f"/api/v1/books/{book_id}/bookmarks",
        headers=headers,
        json={"position_sec": 50.0, "note": "前面"},
    )
    assert earlier.status_code == 201

    listing = client.get(f"/api/v1/books/{book_id}/bookmarks", headers=headers).json()
    assert [item["position_sec"] for item in listing] == [50.0, 200.0]


def test_update_and_delete_bookmark(client, headers, bookmark_data) -> None:
    book_id = bookmark_data["book_id"]
    created = client.post(
        f"/api/v1/books/{book_id}/bookmarks",
        headers=headers,
        json={"position_sec": 10.0, "note": "旧备注"},
    ).json()
    bookmark_id = created["id"]

    updated = client.patch(
        f"/api/v1/bookmarks/{bookmark_id}", headers=headers, json={"note": "新备注"}
    )
    assert updated.status_code == 200
    assert updated.json()["note"] == "新备注"

    assert (
        client.delete(f"/api/v1/bookmarks/{bookmark_id}", headers=headers).status_code
        == 204
    )
    assert (
        client.get(f"/api/v1/books/{book_id}/bookmarks", headers=headers).json() == []
    )


def test_cannot_touch_others_bookmark(client, headers, bookmark_data) -> None:
    session = get_session_factory()()
    bookmark = Bookmark(
        user_id=bookmark_data["other_id"],
        book_id=bookmark_data["book_id"],
        position_sec=1.0,
        note="别人的",
        created_at=now_ts(),
    )
    session.add(bookmark)
    session.commit()
    bookmark_id = bookmark.id
    session.close()

    assert (
        client.patch(
            f"/api/v1/bookmarks/{bookmark_id}", headers=headers, json={"note": "改"}
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/v1/bookmarks/{bookmark_id}", headers=headers).status_code
        == 404
    )


def test_position_beyond_duration_rejected(client, headers, bookmark_data) -> None:
    response = client.post(
        f"/api/v1/books/{bookmark_data['book_id']}/bookmarks",
        headers=headers,
        json={"position_sec": 999.0},
    )
    assert response.status_code == 400


def test_bookmark_requires_library_visibility(client, bookmark_data) -> None:
    session = get_session_factory()()
    # 书库只授权给 admin，other 用户不可见
    session.add(
        LibraryUser(
            library_id=bookmark_data["library_id"], user_id=bookmark_data["admin_id"]
        )
    )
    session.commit()
    session.close()

    login = client.post(
        "/api/v1/auth/login", json={"username": "other", "password": PASSWORD}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.get(
        f"/api/v1/books/{bookmark_data['book_id']}/bookmarks", headers=headers
    )
    assert response.status_code == 403
