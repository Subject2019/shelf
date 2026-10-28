"""M1-T08 验收：分页/搜索/筛选/排序、详情、章节、封面 ETag、书库增删改。"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select, text

from app.api.v1 import auth as auth_module
from app.core.security import hash_password
from app.db.base import now_ts
from app.db.session import get_session_factory
from app.models import Book, Chapter, Library, MediaFile, Progress, Track, User

PASSWORD = "bookpass123"

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

BOOK_SPECS = (
    ("三体", "刘慈欣", "地球往事", 1000.0, -300),
    ("球状闪电", "刘慈欣", None, 500.0, -200),
    ("活着", "余华", None, 300.0, -100),
)


@pytest.fixture()
def books_data(database, tmp_path: Path):
    auth_module._failures.clear()
    session = get_session_factory()()
    for table in CLEAN_TABLES:
        session.execute(text(f"DELETE FROM {table}"))
    session.commit()

    now = now_ts()
    media_dir = tmp_path / "library"
    media_dir.mkdir()
    (media_dir / "a.mp3").write_bytes(b"sample-bytes")

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
        rel_path="a.mp3",
        format="mp3",
        size_bytes=12,
        mtime=now,
        first_seen_at=now,
        last_seen_at=now,
    )
    session.add(media)
    session.flush()

    books: list[Book] = []
    for title, author, series, duration, offset in BOOK_SPECS:
        book = Book(
            library_id=library.id,
            rel_dir=title,
            title=title,
            author=author,
            series_name=series,
            total_duration_sec=duration,
            track_count=1,
            size_bytes=12,
            chapter_source="virtual",
            added_at=now + offset,
            updated_at=now + offset,
        )
        session.add(book)
        books.append(book)
    session.flush()

    for book in books:
        track = Track(
            book_id=book.id,
            media_file_id=media.id,
            track_no=1,
            duration_sec=book.total_duration_sec,
            start_offset_sec=0.0,
        )
        session.add(track)
        session.flush()
        session.add(
            Chapter(
                book_id=book.id,
                track_id=track.id,
                idx=0,
                title="第一章",
                start_sec=0.0,
                end_sec=book.total_duration_sec,
                source="virtual",
            )
        )

    session.add(
        Progress(
            user_id=admin.id,
            book_id=books[0].id,
            position_sec=500.0,
            playback_rate=1.0,
            is_finished=False,
            updated_at=now - 10,
        )
    )
    session.add(
        Progress(
            user_id=admin.id,
            book_id=books[1].id,
            position_sec=500.0,
            playback_rate=1.0,
            is_finished=True,
            updated_at=now - 5,
        )
    )
    session.commit()

    data = {
        "library_id": library.id,
        "book_ids": [book.id for book in books],
    }
    session.close()
    return data


@pytest.fixture()
def headers(client, books_data) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": PASSWORD}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _titles(payload: dict) -> list[str]:
    return [item["title"] for item in payload["items"]]


def test_list_all_sorted_by_added_desc(client, headers, books_data) -> None:
    response = client.get("/api/v1/books", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    assert _titles(payload) == ["活着", "球状闪电", "三体"]


def test_list_sort_title_asc(client, headers, books_data) -> None:
    payload = client.get("/api/v1/books?sort=title_asc", headers=headers).json()
    assert _titles(payload) == ["三体", "活着", "球状闪电"]


def test_list_sort_progress_desc(client, headers, books_data) -> None:
    payload = client.get("/api/v1/books?sort=progress_desc", headers=headers).json()
    assert _titles(payload)[:2] == ["球状闪电", "三体"]
    assert payload["items"][0]["progress"]["percent"] == 100.0


def test_search_and_filters(client, headers, books_data) -> None:
    assert client.get("/api/v1/books?q=刘慈欣", headers=headers).json()["total"] == 2
    assert client.get("/api/v1/books?q=三体", headers=headers).json()["total"] == 1
    assert client.get("/api/v1/books?author=余华", headers=headers).json()["total"] == 1
    assert (
        client.get("/api/v1/books?series=地球往事", headers=headers).json()["total"]
        == 1
    )
    assert (
        client.get("/api/v1/books?filter=in_progress", headers=headers).json()["total"]
        == 1
    )
    assert (
        client.get("/api/v1/books?filter=finished", headers=headers).json()["total"]
        == 1
    )
    assert (
        client.get("/api/v1/books?filter=unplayed", headers=headers).json()["total"]
        == 1
    )
    assert (
        client.get("/api/v1/books?filter=downloaded", headers=headers).json()["total"]
        == 0
    )


def test_pagination(client, headers, books_data) -> None:
    payload = client.get("/api/v1/books?page=2&page_size=2", headers=headers).json()
    assert payload["total"] == 3
    assert payload["page"] == 2
    assert payload["page_size"] == 2
    assert _titles(payload) == ["三体"]


def test_book_detail_includes_tracks_and_chapters(client, headers, books_data) -> None:
    book_id = books_data["book_ids"][0]
    response = client.get(f"/api/v1/books/{book_id}", headers=headers)
    assert response.status_code == 200
    payload = response.json()

    assert payload["title"] == "三体"
    # 该样本没有封面，返回 None，前端用书名渐变兜底
    assert payload["cover_url"] is None
    assert payload["progress"]["position_sec"] == 500.0
    assert payload["progress"]["percent"] == 50.0
    assert len(payload["tracks"]) == 1
    assert payload["tracks"][0]["stream_url"].endswith(
        f"/books/{book_id}/tracks/{payload['tracks'][0]['id']}/stream"
    )
    assert len(payload["chapters"]) == 1


def test_chapters_pagination(client, headers, books_data) -> None:
    book_id = books_data["book_ids"][0]
    response = client.get(
        f"/api/v1/books/{book_id}/chapters?page=1&page_size=1", headers=headers
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["title"] == "第一章"


def test_cover_placeholder_with_etag(client, headers, books_data) -> None:
    book_id = books_data["book_ids"][0]
    response = client.get(f"/api/v1/books/{book_id}/cover", headers=headers)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    etag = response.headers["etag"]
    assert etag
    assert "max-age=86400" in response.headers["cache-control"]

    cached = client.get(
        f"/api/v1/books/{book_id}/cover",
        headers={**headers, "If-None-Match": etag},
    )
    assert cached.status_code == 304


def test_patch_book_metadata_sets_manual_override(client, headers, books_data) -> None:
    book_id = books_data["book_ids"][0]
    response = client.patch(
        f"/api/v1/books/{book_id}",
        headers=headers,
        json={
            "title": "三体（修订版）",
            "author": "刘慈欣",
            "description": "手工简介",
        },
    )
    assert response.status_code == 200
    assert response.json()["title"] == "三体（修订版）"

    detail = client.get(f"/api/v1/books/{book_id}", headers=headers).json()
    assert detail["title"] == "三体（修订版）"
    assert detail["description"] == "手工简介"

    session = get_session_factory()()
    assert session.get(Book, book_id).manual_override is True
    session.close()


def test_patch_book_rejects_empty_payload(client, headers, books_data) -> None:
    response = client.patch(
        f"/api/v1/books/{books_data['book_ids'][0]}", headers=headers, json={}
    )
    assert response.status_code == 400


def test_patch_book_requires_admin(client, books_data) -> None:
    session = get_session_factory()()
    session.add(
        User(
            username="reader",
            password_hash=hash_password(PASSWORD),
            role="user",
            created_at=now_ts(),
        )
    )
    session.commit()
    session.close()

    login = client.post(
        "/api/v1/auth/login", json={"username": "reader", "password": PASSWORD}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.patch(
        f"/api/v1/books/{books_data['book_ids'][0]}",
        headers=headers,
        json={"title": "x"},
    )
    assert response.status_code == 403


def test_book_in_invisible_library_forbidden(client, headers, books_data) -> None:
    response = client.get("/api/v1/books?library_id=999999", headers=headers)
    assert response.status_code == 403


def test_patch_library_rename_and_disable(client, headers, books_data) -> None:
    library_id = books_data["library_id"]
    response = client.patch(
        f"/api/v1/libraries/{library_id}",
        headers=headers,
        json={"name": "改名后的库", "enabled": False},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "改名后的库"
    assert response.json()["enabled"] is False

    # 停用后书籍不再出现在列表
    assert client.get("/api/v1/books", headers=headers).json()["total"] == 0


def test_delete_library_cascades_index(client, headers, books_data) -> None:
    library_id = books_data["library_id"]
    response = client.delete(f"/api/v1/libraries/{library_id}", headers=headers)
    assert response.status_code == 204

    session = get_session_factory()()
    assert session.scalar(select(func.count(Book.id))) == 0
    assert session.scalar(select(func.count(Track.id))) == 0
    assert session.scalar(select(func.count(MediaFile.id))) == 0
    session.close()


def test_patch_library_requires_admin(client, books_data) -> None:
    session = get_session_factory()()
    session.add(
        User(
            username="reader",
            password_hash=hash_password(PASSWORD),
            role="user",
            created_at=now_ts(),
        )
    )
    session.commit()
    session.close()

    login = client.post(
        "/api/v1/auth/login", json={"username": "reader", "password": PASSWORD}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.patch(
        f"/api/v1/libraries/{books_data['library_id']}",
        headers=headers,
        json={"name": "x"},
    )
    assert response.status_code == 403


def test_search_finds_description_only_via_fts(client, headers, books_data) -> None:
    """4 字查询走 FTS：能命中简介里的词，LIKE 路径只查标题/作者/系列。"""
    session = get_session_factory()()
    try:
        book = session.scalar(select(Book).where(Book.title == "活着"))
        assert book is not None
        book.description = "讲述福贵一生的故事，余华代表作"
        session.commit()
    finally:
        session.close()

    assert client.get("/api/v1/books?q=福贵一生", headers=headers).json()["total"] == 1
    # 两字查询回退 LIKE，简介不参与，命中 0
    assert client.get("/api/v1/books?q=福贵", headers=headers).json()["total"] == 0


def test_search_multiple_terms_are_and(client, headers, books_data) -> None:
    payload = client.get("/api/v1/books?q=刘慈欣 球状闪", headers=headers).json()
    assert payload["total"] == 1
    assert payload["items"][0]["title"] == "球状闪电"


def test_search_index_follows_update_and_delete(client, headers, books_data) -> None:
    session = get_session_factory()()
    try:
        book = session.scalar(select(Book).where(Book.title == "活着"))
        assert book is not None
        book.title = "活着 新版增补"
        session.commit()

        assert (
            client.get("/api/v1/books?q=新版增补", headers=headers).json()["total"] == 1
        )
        assert (
            client.get("/api/v1/books?q=活着 新版", headers=headers).json()["total"]
            == 1
        )

        session.delete(book)
        session.commit()
    finally:
        session.close()

    assert client.get("/api/v1/books?q=新版增补", headers=headers).json()["total"] == 0


def test_search_mixes_short_and_long_terms(client, headers, books_data) -> None:
    """「刘慈欣 闪电」= 3 字作者走 FTS + 2 字书名走 LIKE，两者 AND。"""
    payload = client.get("/api/v1/books?q=刘慈欣 闪电", headers=headers).json()
    assert payload["total"] == 1
    assert payload["items"][0]["title"] == "球状闪电"


def test_authors_aggregate(client, headers, books_data) -> None:
    payload = client.get("/api/v1/authors", headers=headers).json()
    by_name = {item["name"]: item for item in payload["items"]}
    assert set(by_name) == {"刘慈欣", "余华"}
    assert by_name["刘慈欣"]["book_count"] == 2
    assert by_name["刘慈欣"]["total_duration_sec"] == 1500.0
    assert by_name["余华"]["book_count"] == 1
    # 样本库没有封面文件，不应给出会 404 的 URL
    assert by_name["余华"]["cover_url"] is None


def test_authors_requires_auth(client, books_data) -> None:
    assert client.get("/api/v1/authors").status_code == 401


def test_book_intro_outro_default_and_update(client, headers, books_data) -> None:
    book_id = books_data["book_ids"][0]
    detail = client.get(f"/api/v1/books/{book_id}", headers=headers).json()
    assert detail["intro_sec"] == 0
    assert detail["outro_sec"] == 0

    patched = client.patch(
        f"/api/v1/books/{book_id}",
        headers=headers,
        json={"intro_sec": 12.5, "outro_sec": 8},
    )
    assert patched.status_code == 200
    assert patched.json()["intro_sec"] == 12.5
    assert patched.json()["outro_sec"] == 8


def test_book_intro_outro_cannot_exceed_duration(client, headers, books_data) -> None:
    book_id = books_data["book_ids"][0]  # 总时长 1000 秒
    response = client.patch(
        f"/api/v1/books/{book_id}",
        headers=headers,
        json={"intro_sec": 600, "outro_sec": 500},
    )
    assert response.status_code == 400
