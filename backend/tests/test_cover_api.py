"""M2-T12 验收：封面上传 / 替换 / 删除，以及占位图回落。"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import text

from app.api.v1 import auth as auth_module
from app.core.config import get_settings
from app.core.security import hash_password
from app.db.base import now_ts
from app.db.session import get_session_factory
from app.models import Book, Library, User
from app.services.covers import remove_cover

PASSWORD = "coverpass123"

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


def _image(size: tuple[int, int] = (800, 1100), color=(200, 90, 40)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, "PNG")
    return buffer.getvalue()


@pytest.fixture()
def cover_data(database, tmp_path: Path):
    auth_module._failures.clear()
    session = get_session_factory()()
    for table in CLEAN_TABLES:
        session.execute(text(f"DELETE FROM {table}"))
    session.commit()

    now = now_ts()
    admin = User(
        username="coveradmin",
        password_hash=hash_password(PASSWORD),
        role="admin",
        created_at=now,
    )
    viewer = User(
        username="coverviewer",
        password_hash=hash_password(PASSWORD),
        role="listener",
        created_at=now,
    )
    editor = User(
        username="covereditor",
        password_hash=hash_password(PASSWORD),
        role="editor",
        created_at=now,
    )
    other_editor = User(
        username="covereditor2",
        password_hash=hash_password(PASSWORD),
        role="editor",
        created_at=now,
    )
    library = Library(name="封面库", root_path=str(tmp_path), created_at=now)
    session.add_all([admin, viewer, editor, other_editor, library])
    session.flush()

    book = Book(
        library_id=library.id,
        rel_dir="",
        title="封面测试书",
        added_at=now,
        updated_at=now,
    )
    session.add(book)
    session.commit()
    book_id = book.id
    session.close()

    editor_id = editor.id
    yield {"book_id": book_id, "editor_id": editor_id}

    remove_cover(book_id, get_settings().covers_dir)


@pytest.fixture()
def headers(client, cover_data):
    response = client.post(
        "/api/v1/auth/login", json={"username": "coveradmin", "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_upload_cover_and_read_back(client, headers, cover_data) -> None:
    book_id = cover_data["book_id"]
    response = client.put(
        f"/api/v1/books/{book_id}/cover",
        files={"file": ("c.png", _image(), "image/png")},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["cover_url"].endswith(f"/books/{book_id}/cover?size=thumb")

    full = client.get(f"/api/v1/books/{book_id}/cover?size=full", headers=headers)
    thumb = client.get(f"/api/v1/books/{book_id}/cover?size=thumb", headers=headers)
    assert full.status_code == 200 and thumb.status_code == 200
    assert full.headers["content-type"] == "image/jpeg"
    assert full.content[:2] == b"\xff\xd8"  # JPEG SOI
    assert len(thumb.content) < len(full.content)

    stored = get_settings().covers_dir
    assert (stored / f"{book_id}.jpg").exists()
    assert (stored / f"{book_id}_thumb.jpg").exists()


def test_upload_replaces_existing_cover(client, headers, cover_data) -> None:
    book_id = cover_data["book_id"]
    for color in ((200, 90, 40), (40, 90, 200)):
        response = client.put(
            f"/api/v1/books/{book_id}/cover",
            files={"file": ("c.png", _image((600, 600), color), "image/png")},
            headers=headers,
        )
        assert response.status_code == 200
    assert (get_settings().covers_dir / f"{book_id}.jpg").exists()


def test_cover_rejects_non_image(client, headers, cover_data) -> None:
    book_id = cover_data["book_id"]
    response = client.put(
        f"/api/v1/books/{book_id}/cover",
        files={"file": ("note.txt", b"not an image", "text/plain")},
        headers=headers,
    )
    assert response.status_code == 400
    assert "图片" in response.json()["error"]["message"]


def test_cover_rejects_oversized(client, headers, cover_data) -> None:
    book_id = cover_data["book_id"]
    payload = b"\x00" * (5 * 1024 * 1024 + 1)
    response = client.put(
        f"/api/v1/books/{book_id}/cover",
        files={"file": ("big.png", payload, "image/png")},
        headers=headers,
    )
    assert response.status_code == 413


def test_delete_cover_falls_back_to_placeholder(client, headers, cover_data) -> None:
    book_id = cover_data["book_id"]
    client.put(
        f"/api/v1/books/{book_id}/cover",
        files={"file": ("c.png", _image(), "image/png")},
        headers=headers,
    )
    deleted = client.delete(f"/api/v1/books/{book_id}/cover", headers=headers)
    assert deleted.status_code == 200

    response = client.get(f"/api/v1/books/{book_id}/cover?size=thumb", headers=headers)
    assert response.status_code == 200
    assert not (get_settings().covers_dir / f"{book_id}.jpg").exists()


def test_cover_requires_admin(client, cover_data) -> None:
    login = client.post(
        "/api/v1/auth/login", json={"username": "coverviewer", "password": PASSWORD}
    )
    viewer_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.put(
        f"/api/v1/books/{cover_data['book_id']}/cover",
        files={"file": ("c.png", _image(), "image/png")},
        headers=viewer_headers,
    )
    assert response.status_code == 403


def test_cover_requires_login(client, cover_data) -> None:
    response = client.put(
        f"/api/v1/books/{cover_data['book_id']}/cover",
        files={"file": ("c.png", _image(), "image/png")},
    )
    assert response.status_code == 401


def _login_headers(client, username: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login", json={"username": username, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_editor_uploads_cover_and_records_uploader(client, cover_data) -> None:
    editor = _login_headers(client, "covereditor")
    book_id = cover_data["book_id"]

    uploaded = client.put(
        f"/api/v1/books/{book_id}/cover",
        headers=editor,
        files={"file": ("e.png", _image(), "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["cover_uploaded_by"] == cover_data["editor_id"]


def test_editor_can_only_delete_own_cover(client, cover_data) -> None:
    uploader = _login_headers(client, "covereditor")
    other = _login_headers(client, "covereditor2")
    book_id = cover_data["book_id"]

    assert (
        client.put(
            f"/api/v1/books/{book_id}/cover",
            headers=uploader,
            files={"file": ("e.png", _image(), "image/png")},
        ).status_code
        == 200
    )

    denied = client.delete(f"/api/v1/books/{book_id}/cover", headers=other)
    assert denied.status_code == 403
    assert "自己" in denied.json()["error"]["message"]

    # 上传者本人可以删
    assert (
        client.delete(f"/api/v1/books/{book_id}/cover", headers=uploader).status_code
        == 200
    )


def test_listener_cannot_touch_cover(client, cover_data) -> None:
    listener = _login_headers(client, "coverviewer")
    book_id = cover_data["book_id"]

    assert (
        client.put(
            f"/api/v1/books/{book_id}/cover",
            headers=listener,
            files={"file": ("l.png", _image(), "image/png")},
        ).status_code
        == 403
    )
    assert (
        client.delete(f"/api/v1/books/{book_id}/cover", headers=listener).status_code
        == 403
    )


def test_admin_can_delete_editor_cover(client, headers, cover_data) -> None:
    editor = _login_headers(client, "covereditor")
    book_id = cover_data["book_id"]

    assert (
        client.put(
            f"/api/v1/books/{book_id}/cover",
            headers=editor,
            files={"file": ("e.png", _image(), "image/png")},
        ).status_code
        == 200
    )
    assert (
        client.delete(f"/api/v1/books/{book_id}/cover", headers=headers).status_code
        == 200
    )
