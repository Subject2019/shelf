"""系列归组：GET /series 汇总与封面挑选。"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text

from app.api.v1 import auth as auth_module
from app.core.security import hash_password
from app.db.base import now_ts
from app.db.session import get_session_factory
from app.models import Book, Library, User
from app.services.scanner import _parse_number, _resolve_series

PASSWORD = "seriespass123"

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


def test_resolve_series_from_title() -> None:
    assert _resolve_series(None, None, "间客·第一卷 东林皆石", "猫腻/间客") == (
        "间客",
        1.0,
    )
    assert _resolve_series(None, None, "间客 第二卷 上林的钟声", "猫腻/间客") == (
        "间客",
        2.0,
    )
    assert _resolve_series(None, None, "三体 第三部 死神永生", "刘慈欣/三体") == (
        "三体",
        3.0,
    )
    # 书名没有系列名时退回目录
    assert _resolve_series(None, None, "第一卷 东林皆石", "猫腻/间客") == ("间客", 1.0)
    # 标签优先
    assert _resolve_series("已标注系列", 7, "随便什么书名", "") == ("已标注系列", 7)
    # 没有卷号就不猜
    assert _resolve_series(None, None, "没有卷号的书名", "猫腻/间客") == (None, None)


def test_parse_number_handles_chinese() -> None:
    assert _parse_number("12") == 12.0
    assert _parse_number("二") == 2.0
    assert _parse_number("十") == 10.0
    assert _parse_number("十二") == 12.0
    assert _parse_number("二十一") == 21.0
    assert _parse_number("一百零三") == 103.0
    assert _parse_number("abc") is None


@pytest.fixture()
def series_data(database, tmp_path: Path):
    auth_module._failures.clear()
    session = get_session_factory()()
    for table in CLEAN_TABLES:
        session.execute(text(f"DELETE FROM {table}"))
    session.commit()

    now = now_ts()
    admin = User(
        username="seriesadmin",
        password_hash=hash_password(PASSWORD),
        role="admin",
        created_at=now,
    )
    library = Library(name="系列库", root_path=str(tmp_path), created_at=now)
    session.add_all([admin, library])
    session.flush()

    books = [
        Book(
            library_id=library.id,
            rel_dir="猫腻/间客",
            title="间客 第一卷",
            series_name="间客",
            series_index=1,
            total_duration_sec=3600,
            added_at=now - 300,
            updated_at=now,
        ),
        Book(
            library_id=library.id,
            rel_dir="猫腻/间客",
            title="间客 第二卷",
            series_name="间客",
            series_index=2,
            total_duration_sec=7200,
            added_at=now - 200,
            updated_at=now,
        ),
        Book(
            library_id=library.id,
            rel_dir="猫腻/间客",
            title="间客 第三卷",
            series_name="间客",
            series_index=3,
            total_duration_sec=1800,
            added_at=now - 100,
            updated_at=now,
        ),
        Book(
            library_id=library.id,
            rel_dir="猫腻/其他",
            title="没有系列的书",
            series_name=None,
            total_duration_sec=600,
            added_at=now,
            updated_at=now,
        ),
    ]
    session.add_all(books)
    session.commit()
    first_volume_id = books[0].id
    session.close()
    return {"first_volume_id": first_volume_id}


@pytest.fixture()
def headers(client, series_data):
    response = client.post(
        "/api/v1/auth/login", json={"username": "seriesadmin", "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_series_endpoint_groups_volumes(client, headers, series_data) -> None:
    response = client.get("/api/v1/series", headers=headers)
    assert response.status_code == 200, response.text
    items = response.json()["items"]

    assert len(items) == 1, "没有系列名的书不应出现在系列列表"
    series = items[0]
    assert series["name"] == "间客"
    assert series["book_count"] == 3
    assert series["total_duration_sec"] == 3600 + 7200 + 1800
    # 封面取卷号最小的一本
    assert series["cover_book_id"] == series_data["first_volume_id"]


def test_series_filter_narrows_books(client, headers, series_data) -> None:
    response = client.get("/api/v1/books?series=间客", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert {item["series_index"] for item in body["items"]} == {1, 2, 3}
