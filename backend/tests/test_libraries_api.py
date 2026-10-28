"""M1-T04 验收：书库登记、触发扫描、扫描状态与并发 409。"""

from __future__ import annotations

import shutil
import time
from pathlib import Path

import pytest
from sqlalchemy import text

from app.core.security import hash_password
from app.db.base import now_ts
from app.db.session import get_session_factory
from app.models import ScanTask, User

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_M4B = FIXTURES / "sample.m4b"
PASSWORD = "adminpass123"

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


@pytest.fixture(autouse=True)
def clean_tables(database):
    session = get_session_factory()()
    for table in CLEAN_TABLES:
        session.execute(text(f"DELETE FROM {table}"))
    session.commit()
    session.close()
    yield


def _create_user(username: str = "admin", role: str = "admin") -> None:
    session = get_session_factory()()
    session.add(
        User(
            username=username,
            password_hash=hash_password(PASSWORD),
            display_name=username,
            role=role,
            created_at=now_ts(),
        )
    )
    session.commit()
    session.close()


def _auth_headers(client, username: str = "admin") -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login", json={"username": username, "password": PASSWORD}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_library(client, headers: dict[str, str], root: Path) -> int:
    response = client.post(
        "/api/v1/libraries",
        headers=headers,
        json={"name": "本地测试", "root_path": str(root)},
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def _wait_scan(
    client, headers: dict[str, str], library_id: int, timeout: float = 15.0
) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = client.get(
            f"/api/v1/libraries/{library_id}/scan/status", headers=headers
        )
        if response.status_code == 200:
            payload = response.json()
            if payload["status"] in ("success", "failed"):
                return payload
        time.sleep(0.1)
    raise AssertionError("扫描超时未完成")


@pytest.mark.skipif(not SAMPLE_M4B.exists(), reason="缺少样本 sample.m4b")
def test_create_library_and_scan(client, tmp_path: Path) -> None:
    _create_user()
    headers = _auth_headers(client)

    media = tmp_path / "media"
    media.mkdir()
    shutil.copyfile(SAMPLE_M4B, media / "book.m4b")
    library_id = _create_library(client, headers, media)

    triggered = client.post(f"/api/v1/libraries/{library_id}/scan", headers=headers)
    assert triggered.status_code == 202
    assert triggered.json()["status"] == "queued"

    status = _wait_scan(client, headers, library_id)
    assert status["status"] == "success", status
    assert status["books_created"] == 1
    assert status["files_added"] == 1

    listing = client.get("/api/v1/libraries", headers=headers)
    assert listing.status_code == 200
    item = listing.json()["items"][0]
    assert item["book_count"] == 1
    assert item["scan"]["status"] == "success"
    assert item["total_duration_sec"] > 0


@pytest.mark.skipif(not SAMPLE_M4B.exists(), reason="缺少样本 sample.m4b")
def test_duplicate_scan_returns_conflict(client, tmp_path: Path) -> None:
    _create_user()
    headers = _auth_headers(client)

    media = tmp_path / "media"
    media.mkdir()
    shutil.copyfile(SAMPLE_M4B, media / "book.m4b")
    library_id = _create_library(client, headers, media)

    session = get_session_factory()()
    session.add(ScanTask(library_id=library_id, status="queued", created_at=now_ts()))
    session.commit()
    session.close()

    response = client.post(f"/api/v1/libraries/{library_id}/scan", headers=headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_create_library_requires_admin(client) -> None:
    _create_user(username="reader", role="user")
    headers = _auth_headers(client, username="reader")

    response = client.post(
        "/api/v1/libraries",
        headers=headers,
        json={"name": "x", "root_path": "/tmp"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_create_library_rejects_missing_path(client, tmp_path: Path) -> None:
    _create_user()
    headers = _auth_headers(client)

    response = client.post(
        "/api/v1/libraries",
        headers=headers,
        json={"name": "x", "root_path": str(tmp_path / "not-exists")},
    )
    assert response.status_code == 400
