"""按章节切片缓存：生成 / 命中 / Range / 下载 / 权限 / 开关 / 清理。"""

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
from app.models import Book, Chapter, Library, LibraryUser, MediaFile, Track, User

PASSWORD = "chapterpass123"

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


def _make_m4b(path: Path, seconds: int = 6) -> bool:
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
            "aac",
            "-b:a",
            "64k",
            "-f",
            "mp4",
            "-y",
            str(path),
        ],
        check=True,
        timeout=60,
    )
    return True


@pytest.fixture()
def chapter_env(tmp_path: Path):
    """一本 6 秒的 m4b、两集（0-3s / 3-6s），外加一个无权限的普通用户。"""
    settings = get_settings()
    clear_cache_dir(settings.chapter_cache_dir)

    auth_module._failures.clear()
    session = get_session_factory()()
    for table in CLEAN_TABLES:
        session.execute(text(f"DELETE FROM {table}"))
    session.commit()

    media_dir = tmp_path / "library"
    media_dir.mkdir()
    source = media_dir / "vol1.m4b"
    if not _make_m4b(source):
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
    library = Library(name="测试库", root_path=str(media_dir), created_at=now)
    session.add_all([admin, outsider, library])
    session.flush()

    # 有授权行 = 私有书库，只有清单里的用户可见（没有授权行会被当作公开）
    session.add(LibraryUser(library_id=library.id, user_id=admin.id))

    media = MediaFile(
        library_id=library.id,
        rel_path="vol1.m4b",
        format="m4b",
        size_bytes=source.stat().st_size,
        mtime=int(source.stat().st_mtime),
        first_seen_at=now,
        last_seen_at=now,
    )
    session.add(media)
    session.flush()

    book = Book(
        library_id=library.id,
        rel_dir="vol1",
        title="第一卷",
        author="测试作者",
        total_duration_sec=6.0,
        track_count=1,
        size_bytes=source.stat().st_size,
        chapter_source="embedded",
        added_at=now,
        updated_at=now,
    )
    session.add(book)
    session.flush()

    track = Track(
        book_id=book.id,
        media_file_id=media.id,
        track_no=1,
        duration_sec=6.0,
        start_offset_sec=0.0,
    )
    session.add(track)
    session.flush()

    session.add_all(
        [
            Chapter(
                book_id=book.id,
                track_id=track.id,
                idx=0,
                title="第一集",
                start_sec=0.0,
                end_sec=3.0,
                source="embedded",
            ),
            Chapter(
                book_id=book.id,
                track_id=track.id,
                idx=1,
                title="第二集",
                start_sec=3.0,
                end_sec=6.0,
                source="embedded",
            ),
        ]
    )
    session.commit()

    yield {"book_id": book.id, "source": source, "media_id": media.id}
    session.close()


def clear_cache_dir(root: Path) -> None:
    if not root.is_dir():
        return
    for path in root.rglob("*"):
        if path.is_file():
            path.unlink()
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_dir():
            path.rmdir()


def _login(client, username: str = "admin") -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login", json={"username": username, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_slice_creates_file_then_hits_cache(client, chapter_env):
    headers = _login(client)
    book_id = chapter_env["book_id"]
    settings = get_settings()

    first = client.post(f"/api/v1/books/{book_id}/chapters/1/cache", headers=headers)
    assert first.status_code == 200, first.text
    payload = first.json()
    assert payload["created"] is True
    assert payload["bytes"] > 1_000
    assert payload["duration_sec"] == pytest.approx(3.0, abs=0.01)
    assert payload["content_type"] == "audio/mp4"

    folder = settings.chapter_cache_dir / str(book_id)
    files = [item for item in folder.iterdir() if item.is_file()]
    assert len(files) == 1
    assert files[0].stat().st_size == payload["bytes"]

    second = client.post(f"/api/v1/books/{book_id}/chapters/1/cache", headers=headers)
    assert second.status_code == 200
    assert second.json()["created"] is False


def test_audio_range_and_download_headers(client, chapter_env):
    headers = _login(client)
    book_id = chapter_env["book_id"]
    url = f"/api/v1/books/{book_id}/chapters/1/audio"

    ranged = client.get(url, headers={**headers, "Range": "bytes=0-99"})
    assert ranged.status_code == 206
    assert len(ranged.content) == 100
    assert ranged.headers["content-type"].startswith("audio/")
    assert ranged.headers["x-chapter-cache"] == "miss"

    again = client.get(url, headers={**headers, "Range": "bytes=0-99"})
    assert again.headers["x-chapter-cache"] == "hit"

    download = client.get(f"{url}?download=1", headers=headers)
    disposition = download.headers["content-disposition"]
    assert disposition.startswith("attachment;")
    assert "chapter-0002.m4a" in disposition


def test_chapter_not_found(client, chapter_env):
    headers = _login(client)
    book_id = chapter_env["book_id"]
    response = client.post(
        f"/api/v1/books/{book_id}/chapters/99/cache", headers=headers
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "chapter_not_found"


def test_outsider_cannot_slice(client, chapter_env):
    headers = _login(client, "outsider")
    book_id = chapter_env["book_id"]
    response = client.post(f"/api/v1/books/{book_id}/chapters/0/cache", headers=headers)
    assert response.status_code == 403


def test_switch_off_returns_503(client, chapter_env, monkeypatch):
    headers = _login(client)
    book_id = chapter_env["book_id"]
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_chapter_cache", False)

    response = client.post(f"/api/v1/books/{book_id}/chapters/0/cache", headers=headers)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "chapter_cache_disabled"


def test_missing_ffmpeg_returns_503(client, chapter_env, monkeypatch):
    headers = _login(client)
    book_id = chapter_env["book_id"]
    monkeypatch.setattr(shutil, "which", lambda _name: None)

    response = client.post(f"/api/v1/books/{book_id}/chapters/0/cache", headers=headers)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ffmpeg_missing"


def test_cache_list_and_clear(client, chapter_env):
    headers = _login(client)
    book_id = chapter_env["book_id"]

    client.post(f"/api/v1/books/{book_id}/chapters/0/cache", headers=headers)
    client.post(f"/api/v1/books/{book_id}/chapters/1/cache", headers=headers)

    listing = client.get(f"/api/v1/books/{book_id}/chapters/cache", headers=headers)
    assert listing.status_code == 200
    payload = listing.json()
    assert [item["index"] for item in payload["items"]] == [0, 1]
    assert payload["items"][1]["title"] == "第二集"
    assert payload["total_bytes"] > 0

    removed = client.delete(f"/api/v1/books/{book_id}/chapters/cache", headers=headers)
    assert removed.status_code == 204
    empty = client.get(f"/api/v1/books/{book_id}/chapters/cache", headers=headers)
    assert empty.json() == {"items": [], "total_bytes": 0}
