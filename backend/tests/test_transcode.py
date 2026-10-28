"""整轨转码：wma → opus、缓存命中、Range、参数校验、开关。"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from sqlalchemy import text

from app.api.v1 import auth as auth_module
from app.core.config import get_settings
from app.core.security import hash_password
from app.db.base import now_ts
from app.db.session import get_session_factory
from app.models import Book, Library, LibraryUser, MediaFile, Track, User

PASSWORD = "transcodepass123"

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


def _make_wma(path: Path, seconds: int = 4) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return False
    subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:duration={seconds}",
            "-c:a",
            "wmav2",
            "-b:a",
            "64k",
            "-f",
            "asf",
            "-y",
            str(path),
        ],
        check=True,
        timeout=60,
    )
    return True


def _clear_cache() -> None:
    root = get_settings().transcode_cache_dir
    if root.is_dir():
        shutil.rmtree(root, ignore_errors=True)


@pytest.fixture()
def transcode_env(tmp_path: Path):
    """一本 wma 单轨书（浏览器不支持 wma，正是转码场景）。"""
    _clear_cache()

    auth_module._failures.clear()
    session = get_session_factory()()
    for table in CLEAN_TABLES:
        session.execute(text(f"DELETE FROM {table}"))
    session.commit()

    media_dir = tmp_path / "library"
    media_dir.mkdir()
    source = media_dir / "only.wma"
    if not _make_wma(source):
        session.close()
        pytest.skip("需要 ffmpeg")

    now = now_ts()
    admin = User(
        username="admin",
        password_hash=hash_password(PASSWORD),
        role="admin",
        created_at=now,
    )
    outsider = User(
        username="outsider",
        password_hash=hash_password(PASSWORD),
        role="user",
        created_at=now,
    )
    library = Library(name="转码库", root_path=str(media_dir), created_at=now)
    session.add_all([admin, outsider, library])
    session.flush()
    session.add(LibraryUser(library_id=library.id, user_id=admin.id))

    media = MediaFile(
        library_id=library.id,
        rel_path="only.wma",
        format="wma",
        size_bytes=source.stat().st_size,
        mtime=int(source.stat().st_mtime),
        first_seen_at=now,
        last_seen_at=now,
    )
    session.add(media)
    session.flush()

    book = Book(
        library_id=library.id,
        rel_dir="only",
        title="转码测试书",
        author="测试",
        total_duration_sec=4.0,
        track_count=1,
        size_bytes=source.stat().st_size,
        chapter_source="track_split",
        added_at=now,
        updated_at=now,
    )
    session.add(book)
    session.flush()

    track = Track(
        book_id=book.id,
        media_file_id=media.id,
        track_no=1,
        duration_sec=4.0,
        start_offset_sec=0.0,
    )
    session.add(track)
    session.commit()

    ids = {"book_id": book.id, "track_id": track.id}
    session.close()

    yield ids

    _clear_cache()


def _headers(client) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_transcode_stream_and_cache_hit(client, transcode_env):
    headers = _headers(client)
    book_id = transcode_env["book_id"]
    track_id = transcode_env["track_id"]

    first = client.get(
        f"/api/v1/books/{book_id}/tracks/{track_id}/stream?transcode=opus&bitrate=64",
        headers={**headers, "Range": "bytes=0-1023"},
    )
    assert first.status_code == 206, first.text
    assert first.headers["content-type"].startswith("audio/webm")
    assert first.headers["x-transcode-cache"] == "miss"
    assert first.headers["x-transcode"] == "opus/64"
    assert len(first.content) == 1024

    cache_files = list((get_settings().transcode_cache_dir / str(book_id)).iterdir())
    assert len(cache_files) == 1

    second = client.get(
        f"/api/v1/books/{book_id}/tracks/{track_id}/stream?transcode=opus&bitrate=64",
        headers={**headers, "Range": "bytes=0-1023"},
    )
    assert second.status_code == 206
    assert second.headers["x-transcode-cache"] == "hit"

    # 不带 transcode 仍是原文件（wma，浏览器可能播不了，但服务端如实返回）
    raw = client.head(
        f"/api/v1/books/{book_id}/tracks/{track_id}/stream", headers=headers
    )
    assert raw.status_code == 200
    assert raw.headers["x-transcode-cache"] == "off"


def test_prepare_transcode_endpoint(client, transcode_env):
    headers = _headers(client)
    book_id = transcode_env["book_id"]
    track_id = transcode_env["track_id"]

    first = client.post(
        f"/api/v1/books/{book_id}/tracks/{track_id}/transcode?codec=opus&bitrate=48",
        headers=headers,
    )
    assert first.status_code == 200, first.text
    payload = first.json()
    assert payload["created"] is True
    assert payload["codec"] == "opus"
    assert payload["bitrate"] == 48
    assert payload["bytes"] > 0
    assert payload["content_type"] == "audio/webm"
    assert payload["duration_sec"] == 4.0

    again = client.post(
        f"/api/v1/books/{book_id}/tracks/{track_id}/transcode?codec=opus&bitrate=48",
        headers=headers,
    )
    assert again.status_code == 200
    assert again.json()["created"] is False


def test_transcode_rejects_unknown_codec_and_bitrate(client, transcode_env):
    headers = _headers(client)
    book_id = transcode_env["book_id"]
    track_id = transcode_env["track_id"]

    bad_codec = client.get(
        f"/api/v1/books/{book_id}/tracks/{track_id}/stream?transcode=aac",
        headers=headers,
    )
    assert bad_codec.status_code == 400
    assert bad_codec.json()["error"]["code"] == "transcode_unsupported"

    bad_rate = client.get(
        f"/api/v1/books/{book_id}/tracks/{track_id}/stream?transcode=opus&bitrate=9",
        headers=headers,
    )
    assert bad_rate.status_code == 400


def test_transcode_disabled_returns_503(client, transcode_env, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_transcode", False)

    headers = _headers(client)
    book_id = transcode_env["book_id"]
    track_id = transcode_env["track_id"]

    response = client.get(
        f"/api/v1/books/{book_id}/tracks/{track_id}/stream?transcode=opus",
        headers=headers,
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "transcode_disabled"


def test_transcode_rejects_too_long_track(client, transcode_env, monkeypatch):
    """整轨超过时长上限时快速失败，避免请求挂几十分钟。"""
    settings = get_settings()
    monkeypatch.setattr(settings, "transcode_max_duration_sec", 1)

    headers = _headers(client)
    book_id = transcode_env["book_id"]
    track_id = transcode_env["track_id"]

    response = client.get(
        f"/api/v1/books/{book_id}/tracks/{track_id}/stream?transcode=opus",
        headers=headers,
    )
    assert response.status_code == 413
    payload = response.json()["error"]
    assert payload["code"] == "transcode_too_long"
    assert "chapters" in payload["message"]


def test_transcode_requires_permission(client, transcode_env):
    book_id = transcode_env["book_id"]
    track_id = transcode_env["track_id"]

    anonymous = client.get(
        f"/api/v1/books/{book_id}/tracks/{track_id}/stream?transcode=opus"
    )
    assert anonymous.status_code == 401

    login = client.post(
        "/api/v1/auth/login", json={"username": "outsider", "password": PASSWORD}
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    forbidden = client.get(
        f"/api/v1/books/{book_id}/tracks/{track_id}/stream?transcode=opus",
        headers=headers,
    )
    assert forbidden.status_code == 403


def test_health_reports_transcode_stats(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    stats = response.json()["transcode"]
    assert stats["enabled"] is True
    assert stats["active"] == 0
    assert stats["completed"] >= 0
