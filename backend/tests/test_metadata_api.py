"""M2-T11 验收：元数据编辑、字段清空、manual_override 与恢复自动识别。"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text

from app.api.v1 import auth as auth_module
from app.core.security import hash_password
from app.db.base import now_ts
from app.db.session import get_session_factory
from app.models import Book, Library, User

PASSWORD = "metapass123"

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
def meta_data(database, tmp_path: Path):
    auth_module._failures.clear()
    session = get_session_factory()()
    for table in CLEAN_TABLES:
        session.execute(text(f"DELETE FROM {table}"))
    session.commit()

    now = now_ts()
    admin = User(
        username="metaadmin",
        password_hash=hash_password(PASSWORD),
        role="admin",
        created_at=now,
    )
    viewer = User(
        username="metaviewer",
        password_hash=hash_password(PASSWORD),
        role="viewer",
        created_at=now,
    )
    library = Library(name="元数据库", root_path=str(tmp_path), created_at=now)
    session.add_all([admin, viewer, library])
    session.flush()

    book = Book(
        library_id=library.id,
        rel_dir="猫腻/间客",
        title="原始书名",
        author="原作者",
        narrator=None,
        description=None,
        added_at=now,
        updated_at=now,
    )
    session.add(book)
    session.commit()
    book_id = book.id
    session.close()
    return {"book_id": book_id}


@pytest.fixture()
def headers(client, meta_data):
    response = client.post(
        "/api/v1/auth/login", json={"username": "metaadmin", "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_patch_updates_fields_and_marks_manual(client, headers, meta_data) -> None:
    book_id = meta_data["book_id"]
    payload = {
        "title": "  间客·第一卷  ",
        "subtitle": "东林皆石",
        "author": "猫腻",
        "narrator": "李野墨",
        "publisher": "纵横中文网",
        "publish_year": 2009,
        "language": "zh-CN",
        "series_name": "间客",
        "series_index": 1,
        "description": "一个少年的故事。",
    }
    response = client.patch(f"/api/v1/books/{book_id}", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["title"] == "间客·第一卷"  # 首尾空白被裁剪
    assert body["manual_override"] is True

    # BookOut 不含出版信息，这些字段从详情接口回读
    detail = client.get(f"/api/v1/books/{book_id}", headers=headers).json()
    assert detail["subtitle"] == "东林皆石"
    assert detail["narrator"] == "李野墨"
    assert detail["publisher"] == "纵横中文网"
    assert detail["publish_year"] == 2009
    assert detail["language"] == "zh-CN"
    assert detail["series_name"] == "间客"
    assert detail["description"] == "一个少年的故事。"
    assert detail["manual_override"] is True


def test_patch_clears_field_with_empty_string(client, headers, meta_data) -> None:
    book_id = meta_data["book_id"]
    client.patch(
        f"/api/v1/books/{book_id}", json={"narrator": "李野墨"}, headers=headers
    )
    response = client.patch(
        f"/api/v1/books/{book_id}", json={"narrator": "   "}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["narrator"] is None


def test_patch_rejects_blank_title(client, headers, meta_data) -> None:
    book_id = meta_data["book_id"]
    response = client.patch(
        f"/api/v1/books/{book_id}", json={"title": "   "}, headers=headers
    )
    assert response.status_code == 400
    assert "书名" in response.json()["error"]["message"]


def test_patch_rejects_out_of_range_year(client, headers, meta_data) -> None:
    book_id = meta_data["book_id"]
    response = client.patch(
        f"/api/v1/books/{book_id}", json={"publish_year": 99999}, headers=headers
    )
    assert response.status_code == 422


def test_reset_metadata_clears_manual_override(client, headers, meta_data) -> None:
    book_id = meta_data["book_id"]
    client.patch(
        f"/api/v1/books/{book_id}", json={"author": "手改作者"}, headers=headers
    )
    reset = client.post(f"/api/v1/books/{book_id}/metadata/reset", headers=headers)
    assert reset.status_code == 200
    assert reset.json()["manual_override"] is False


def test_patch_requires_admin(client, meta_data) -> None:
    login = client.post(
        "/api/v1/auth/login", json={"username": "metaviewer", "password": PASSWORD}
    )
    viewer_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.patch(
        f"/api/v1/books/{meta_data['book_id']}",
        json={"title": "改个名"},
        headers=viewer_headers,
    )
    assert response.status_code == 403
