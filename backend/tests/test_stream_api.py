"""M1-T06 验收：206/416/HEAD、鉴权与目录穿越防护。"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text

from app.api.v1 import auth as auth_module
from app.core.security import hash_password
from app.db.base import now_ts
from app.db.session import get_session_factory
from app.models import Book, Library, LibraryUser, MediaFile, Track, User

PASSWORD = "streampass123"

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
def stream_data(database, tmp_path: Path):
    # 限流计数是进程级状态，其他用例可能已把同名用户锁住
    auth_module._failures.clear()
    session = get_session_factory()()
    for table in CLEAN_TABLES:
        session.execute(text(f"DELETE FROM {table}"))
    session.commit()

    media_dir = tmp_path / "library"
    media_dir.mkdir()
    payload = bytes(range(256)) * 20  # 5120 字节，方便断言切片
    (media_dir / "track.mp3").write_bytes(payload)

    now = now_ts()
    alice = User(
        username="alice",
        password_hash=hash_password(PASSWORD),
        role="admin",
        created_at=now,
    )
    library = Library(name="测试库", root_path=str(media_dir), created_at=now)
    session.add_all([alice, library])
    session.flush()

    book = Book(
        library_id=library.id, rel_dir="", title="测试书", added_at=now, updated_at=now
    )
    session.add(book)
    session.flush()

    media = MediaFile(
        library_id=library.id,
        rel_path="track.mp3",
        format="mp3",
        size_bytes=len(payload),
        mtime=now,
        first_seen_at=now,
        last_seen_at=now,
    )
    session.add(media)
    session.flush()

    track = Track(
        book_id=book.id,
        media_file_id=media.id,
        track_no=1,
        duration_sec=12.0,
        start_offset_sec=0.0,
    )
    session.add(track)
    session.commit()

    data = {
        "library_id": library.id,
        "book_id": book.id,
        "track_id": track.id,
        "media_id": media.id,
        "alice_id": alice.id,
    }
    session.close()
    return data, payload, media_dir


@pytest.fixture()
def headers(client, stream_data) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login", json={"username": "alice", "password": PASSWORD}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _url(data: dict) -> str:
    return f"/api/v1/books/{data['book_id']}/tracks/{data['track_id']}/stream"


def test_full_stream(client, headers, stream_data) -> None:
    data, payload, _ = stream_data
    response = client.get(_url(data), headers=headers)

    assert response.status_code == 200
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-length"] == str(len(payload))
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.content == payload


def test_closed_range(client, headers, stream_data) -> None:
    data, payload, _ = stream_data
    size = len(payload)
    response = client.get(_url(data), headers={**headers, "Range": "bytes=100-199"})

    assert response.status_code == 206
    assert response.headers["content-range"] == f"bytes 100-199/{size}"
    assert response.headers["content-length"] == "100"
    assert response.content == payload[100:200]


def test_open_ended_range(client, headers, stream_data) -> None:
    data, payload, _ = stream_data
    size = len(payload)
    response = client.get(_url(data), headers={**headers, "Range": "bytes=5000-"})

    assert response.status_code == 206
    assert response.headers["content-range"] == f"bytes 5000-{size - 1}/{size}"
    assert response.content == payload[5000:]


def test_suffix_range(client, headers, stream_data) -> None:
    data, payload, _ = stream_data
    size = len(payload)
    response = client.get(_url(data), headers={**headers, "Range": "bytes=-120"})

    assert response.status_code == 206
    assert response.headers["content-range"] == f"bytes {size - 120}-{size - 1}/{size}"
    assert response.content == payload[-120:]


def test_multipart_returns_first_segment(client, headers, stream_data) -> None:
    data, payload, _ = stream_data
    response = client.get(_url(data), headers={**headers, "Range": "bytes=0-9,20-29"})

    assert response.status_code == 206
    assert response.content == payload[0:10]


def test_range_out_of_bounds_returns_416(client, headers, stream_data) -> None:
    data, payload, _ = stream_data
    size = len(payload)
    response = client.get(
        _url(data), headers={**headers, "Range": f"bytes={size + 100}-"}
    )

    assert response.status_code == 416
    assert response.headers["content-range"] == f"bytes */{size}"


def test_invalid_range_returns_416(client, headers, stream_data) -> None:
    data, _, _ = stream_data
    response = client.get(_url(data), headers={**headers, "Range": "bytes=abc-"})
    assert response.status_code == 416


def test_head_returns_headers_without_body(client, headers, stream_data) -> None:
    data, payload, _ = stream_data
    response = client.head(_url(data), headers=headers)

    assert response.status_code == 200
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-length"] == str(len(payload))
    assert response.content == b""


def test_head_with_range(client, headers, stream_data) -> None:
    data, payload, _ = stream_data
    size = len(payload)
    response = client.head(_url(data), headers={**headers, "Range": "bytes=10-19"})

    assert response.status_code == 206
    assert response.headers["content-range"] == f"bytes 10-19/{size}"
    assert response.headers["content-length"] == "10"
    assert response.content == b""


def test_stream_requires_auth(client, stream_data) -> None:
    data, _, _ = stream_data
    assert client.get(_url(data)).status_code == 401


def test_transcode_rejects_unknown_codec(client, headers, stream_data) -> None:
    """M6 起支持转码；非法编码在这里就 400，不进入 ffmpeg。"""
    data, _, _ = stream_data
    response = client.get(f"{_url(data)}?transcode=aac", headers=headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "transcode_unsupported"


def test_track_not_found(client, headers, stream_data) -> None:
    data, _, _ = stream_data
    response = client.get(
        f"/api/v1/books/{data['book_id']}/tracks/999999/stream", headers=headers
    )
    assert response.status_code == 404


def test_other_user_without_grant_forbidden(client, stream_data) -> None:
    data, _, _ = stream_data
    session = get_session_factory()()
    # 书库只授权给 alice，bob 属于普通用户且未被授权
    session.add(LibraryUser(library_id=data["library_id"], user_id=data["alice_id"]))
    bob = User(
        username="bob",
        password_hash=hash_password(PASSWORD),
        role="user",
        created_at=now_ts(),
    )
    session.add(bob)
    session.commit()
    session.close()

    login = client.post(
        "/api/v1/auth/login", json={"username": "bob", "password": PASSWORD}
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.get(_url(data), headers=headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_path_traversal_is_blocked(
    client, headers, stream_data, tmp_path: Path
) -> None:
    data, _, _ = stream_data
    (tmp_path / "secret.mp3").write_bytes(b"secret")

    session = get_session_factory()()
    media = session.get(MediaFile, data["media_id"])
    assert media is not None
    media.rel_path = "../secret.mp3"
    session.commit()
    session.close()

    response = client.get(_url(data), headers=headers)
    assert response.status_code == 404


def test_play_token_grants_stream_without_header(client, headers, stream_data) -> None:
    data, payload, _ = stream_data
    token_response = client.post(
        f"/api/v1/books/{data['book_id']}/play-token", headers=headers
    )
    assert token_response.status_code == 200
    body = token_response.json()
    assert body["expires_in"] > 0
    assert body["expires_at"] > 0

    response = client.get(
        f"{_url(data)}?token={body['token']}", headers={"Range": "bytes=0-9"}
    )
    assert response.status_code == 206
    assert response.content == payload[:10]

    head = client.head(f"{_url(data)}?token={body['token']}")
    assert head.status_code == 200
    assert head.headers["content-length"] == str(len(payload))


def test_play_token_is_book_scoped(client, headers, stream_data) -> None:
    data, _, _ = stream_data
    token = client.post(
        f"/api/v1/books/{data['book_id']}/play-token", headers=headers
    ).json()["token"]

    other_book = data["book_id"] + 1000
    response = client.head(
        f"/api/v1/books/{other_book}/tracks/{data['track_id']}/stream?token={token}"
    )
    assert response.status_code == 401


def test_play_token_rejects_access_token(client, headers, stream_data) -> None:
    data, _, _ = stream_data
    access_token = headers["Authorization"].removeprefix("Bearer ")
    response = client.head(f"{_url(data)}?token={access_token}")
    assert response.status_code == 401


def test_play_token_requires_login(client, stream_data) -> None:
    data, _, _ = stream_data
    assert client.post(f"/api/v1/books/{data['book_id']}/play-token").status_code == 401
