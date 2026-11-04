"""M1-T07 验收：ADR-0002 合并规则与进度接口。"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select, text

from app.api.v1 import auth as auth_module
from app.core.security import hash_password
from app.db.base import now_ts
from app.db.session import get_session_factory
from app.models import (
    Book,
    Library,
    ListeningDaily,
    MediaFile,
    Progress,
    ProgressHistory,
    Track,
    User,
)
from app.services.progress_history import HISTORY_LIMIT, record_checkpoint
from app.services.stats import collect_stats
from app.services.progress import (
    ProgressState,
    locate_track,
    merge_progress,
    sane_timestamp,
    track_position,
    track_start_offsets,
)

PASSWORD = "progresspass123"

CLEAN_TABLES = (
    "chapters",
    "tracks",
    "collection_books",
    "bookmarks",
    "listening_daily",
    "progress_history",
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


# ---------------- 纯函数 ----------------


def test_first_report_is_accepted() -> None:
    decision = merge_progress(
        None,
        ProgressState(100.0, 1, 1000),
        server_now=1000,
        explicit_seek=False,
    )
    assert decision.accepted is True
    assert decision.position_sec == 100.0


def test_same_or_older_timestamp_rejected() -> None:
    old = ProgressState(100.0, 1, 1000)
    same = merge_progress(
        old, ProgressState(200.0, 1, 1000), server_now=1000, explicit_seek=True
    )
    assert same.accepted is False
    assert same.position_sec == 100.0

    older = merge_progress(
        old, ProgressState(200.0, 1, 900), server_now=1000, explicit_seek=False
    )
    assert older.accepted is False


def test_clock_skew_falls_back_to_server_time() -> None:
    assert sane_timestamp(1000, 1000) == 1000
    # 客户端时钟快 1 小时：改用服务器时间
    assert sane_timestamp(4600, 1000) == 1000
    # 客户端时钟慢 1 小时：同样改用服务器时间
    assert sane_timestamp(-2600, 1000) == 1000
    assert sane_timestamp(1299, 1000) == 1299


def test_same_track_small_rewind_is_accepted() -> None:
    old = ProgressState(100.0, 1, 1000)
    decision = merge_progress(
        old, ProgressState(80.0, 1, 1010), server_now=1010, explicit_seek=False
    )
    assert decision.accepted is True
    assert decision.position_sec == 80.0


def test_same_track_large_rewind_rejected() -> None:
    old = ProgressState(100.0, 1, 1000)
    decision = merge_progress(
        old, ProgressState(60.0, 1, 1010), server_now=1010, explicit_seek=False
    )
    assert decision.accepted is False
    assert decision.position_sec == 100.0


def test_explicit_seek_overrides_rewind() -> None:
    old = ProgressState(100.0, 1, 1000)
    decision = merge_progress(
        old, ProgressState(5.0, 1, 1010), server_now=1010, explicit_seek=True
    )
    assert decision.accepted is True
    assert decision.position_sec == 5.0


def test_cross_track_rewind_rejected_without_seek() -> None:
    # 绝对位置从 250 退回 20，即使换了轨也不能当成「前进」
    old = ProgressState(250.0, 3, 1000)
    decision = merge_progress(
        old, ProgressState(20.0, 1, 1010), server_now=1010, explicit_seek=False
    )
    assert decision.accepted is False
    assert decision.position_sec == 250.0


def test_cross_track_rewind_accepted_with_seek() -> None:
    old = ProgressState(250.0, 3, 1000)
    decision = merge_progress(
        old, ProgressState(20.0, 1, 1010), server_now=1010, explicit_seek=True
    )
    assert decision.accepted is True
    assert decision.position_sec == 20.0


def test_track_offsets_and_lookup() -> None:
    class FakeTrack:
        def __init__(self, track_id: int, duration: float) -> None:
            self.id = track_id
            self.duration_sec = duration

    tracks = [FakeTrack(1, 100.0), FakeTrack(2, 50.0), FakeTrack(3, 30.0)]
    offsets = track_start_offsets(tracks)  # type: ignore[arg-type]
    assert offsets == {1: 0.0, 2: 100.0, 3: 150.0}
    assert locate_track(offsets, tracks, 0.0) == 1  # type: ignore[arg-type]
    assert locate_track(offsets, tracks, 99.9) == 1  # type: ignore[arg-type]
    assert locate_track(offsets, tracks, 100.0) == 2  # type: ignore[arg-type]
    assert locate_track(offsets, tracks, 999.0) == 3  # type: ignore[arg-type]
    assert track_position(120.0, 100.0) == 20.0
    assert track_position(10.0, 100.0) == 0.0


# ---------------- 接口 ----------------


@pytest.fixture()
def progress_data(database, tmp_path: Path):
    auth_module._failures.clear()
    session = get_session_factory()()
    for table in CLEAN_TABLES:
        session.execute(text(f"DELETE FROM {table}"))
    session.commit()

    now = now_ts()
    media_dir = tmp_path / "library"
    media_dir.mkdir()
    (media_dir / "book.mp3").write_bytes(b"x" * 32)

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
        size_bytes=32,
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
        author="刘慈欣",
        total_duration_sec=300.0,
        track_count=3,
        size_bytes=32,
        chapter_source="track_split",
        added_at=now,
        updated_at=now,
    )
    session.add(book)
    session.flush()

    track_ids: list[int] = []
    for index in range(1, 4):
        track = Track(
            book_id=book.id,
            media_file_id=media.id,
            track_no=index,
            title=f"第 {index} 章",
            start_offset_sec=0.0,
            duration_sec=100.0,
            size_bytes=32,
        )
        session.add(track)
        session.flush()
        track_ids.append(track.id)
    session.commit()

    data = {"book_id": book.id, "track_ids": track_ids}
    session.close()
    return data


@pytest.fixture()
def headers(client, progress_data) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": PASSWORD}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _put(client, headers, book_id: int, **overrides) -> dict:
    payload = {
        "track_id": None,
        "position_sec": 50.0,
        "playback_rate": 1.0,
        "device_id": "web-test",
        "client_updated_at": now_ts(),
        "explicit_seek": False,
        "finished": False,
    }
    payload.update(overrides)
    return client.put(
        f"/api/v1/progress/{book_id}", headers=headers, json=payload
    ).json()


def test_get_progress_without_record_returns_zeros(
    client, headers, progress_data
) -> None:
    book_id = progress_data["book_id"]
    response = client.get(f"/api/v1/progress/{book_id}", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["position_sec"] == 0.0
    assert payload["is_finished"] is False
    assert payload["updated_at"] == 0


def test_put_progress_then_get(client, headers, progress_data) -> None:
    book_id = progress_data["book_id"]
    tracks = progress_data["track_ids"]

    first = _put(client, headers, book_id, track_id=tracks[1], position_sec=150.0)
    assert first["accepted"] is True
    assert first["position_sec"] == 150.0
    assert first["track_id"] == tracks[1]

    detail = client.get(f"/api/v1/progress/{book_id}", headers=headers).json()
    assert detail["track_position_sec"] == 50.0
    assert detail["device_id"] == "web-test"


def test_put_progress_rejects_large_rewind(client, headers, progress_data) -> None:
    book_id = progress_data["book_id"]
    track = progress_data["track_ids"][1]

    _put(client, headers, book_id, track_id=track, position_sec=150.0)
    rejected = _put(
        client,
        headers,
        book_id,
        track_id=track,
        position_sec=50.0,
        client_updated_at=now_ts() + 10,
    )
    assert rejected["accepted"] is False
    assert rejected["position_sec"] == 150.0


def test_explicit_seek_allows_rewind(client, headers, progress_data) -> None:
    book_id = progress_data["book_id"]
    track = progress_data["track_ids"][1]

    _put(client, headers, book_id, track_id=track, position_sec=150.0)
    seeked = _put(
        client,
        headers,
        book_id,
        track_id=track,
        position_sec=10.0,
        client_updated_at=now_ts() + 10,
        explicit_seek=True,
    )
    assert seeked["accepted"] is True
    assert seeked["position_sec"] == 10.0


def test_finished_auto_detected_and_excluded_from_recent(
    client, headers, progress_data
) -> None:
    book_id = progress_data["book_id"]
    _put(client, headers, book_id, position_sec=290.0)

    detail = client.get(f"/api/v1/progress/{book_id}", headers=headers).json()
    assert detail["is_finished"] is True

    recent = client.get("/api/v1/progress/recent", headers=headers).json()
    assert recent["items"] == []


def test_recent_progress_lists_unfinished(client, headers, progress_data) -> None:
    book_id = progress_data["book_id"]
    _put(client, headers, book_id, position_sec=60.0)

    recent = client.get("/api/v1/progress/recent", headers=headers).json()
    assert len(recent["items"]) == 1
    item = recent["items"][0]
    assert item["book_id"] == book_id
    assert item["title"] == "三体"
    assert item["percent"] == 20.0
    assert item["cover_url"] is None
    # 客户端靠 device_id 判断「这条是不是我自己写的」
    assert item["device_id"] == "web-test"


def test_position_beyond_duration_rejected(client, headers, progress_data) -> None:
    book_id = progress_data["book_id"]
    response = client.put(
        f"/api/v1/progress/{book_id}",
        headers=headers,
        json={
            "position_sec": 400.0,
            "client_updated_at": now_ts(),
            "playback_rate": 1.0,
        },
    )
    assert response.status_code == 400


def test_unknown_track_id_is_resolved_by_position(
    client, headers, progress_data
) -> None:
    book_id = progress_data["book_id"]
    result = _put(client, headers, book_id, track_id=999999, position_sec=120.0)
    assert result["accepted"] is True
    assert result["track_id"] == progress_data["track_ids"][1]


def test_delete_progress_resets(client, headers, progress_data) -> None:
    book_id = progress_data["book_id"]
    _put(client, headers, book_id, position_sec=60.0)
    assert (
        client.delete(f"/api/v1/progress/{book_id}", headers=headers).status_code == 204
    )

    detail = client.get(f"/api/v1/progress/{book_id}", headers=headers).json()
    assert detail["position_sec"] == 0.0
    session = get_session_factory()()
    assert session.scalar(select(func.count()).select_from(Progress)) == 0
    session.close()


def test_progress_requires_visibility(client, headers, progress_data) -> None:
    response = client.get("/api/v1/progress/999999", headers=headers)
    assert response.status_code == 404


# ---------------- M4-T02：四组并发同步场景 ----------------


def test_sync_same_track_rewind_keeps_forward_position(
    client, headers, progress_data
) -> None:
    """两台设备同轨：后上报但位置更靠前的小幅回退，保留较后位置。"""
    book_id = progress_data["book_id"]
    track = progress_data["track_ids"][0]
    base = now_ts()

    forward = _put(
        client,
        headers,
        book_id,
        track_id=track,
        position_sec=90.0,
        client_updated_at=base,
    )
    assert forward["accepted"] is True

    back = _put(
        client,
        headers,
        book_id,
        track_id=track,
        position_sec=40.0,
        client_updated_at=base + 5,
    )
    assert back["accepted"] is False
    assert back["position_sec"] == 90.0


def test_sync_cross_track_rewind_rejected_then_seek_wins(
    client, headers, progress_data
) -> None:
    """跨轨回退不再被当成「前进」，显式跳转才放行。"""
    book_id = progress_data["book_id"]
    tracks = progress_data["track_ids"]
    base = now_ts()

    first = _put(
        client,
        headers,
        book_id,
        track_id=tracks[2],
        position_sec=250.0,
        client_updated_at=base,
    )
    assert first["accepted"] is True

    rewind = _put(
        client,
        headers,
        book_id,
        track_id=tracks[0],
        position_sec=20.0,
        client_updated_at=base + 5,
    )
    assert rewind["accepted"] is False
    assert rewind["position_sec"] == 250.0

    seek = _put(
        client,
        headers,
        book_id,
        track_id=tracks[0],
        position_sec=20.0,
        client_updated_at=base + 10,
        explicit_seek=True,
    )
    assert seek["accepted"] is True
    assert seek["position_sec"] == 20.0
    assert seek["track_id"] == tracks[0]


def test_sync_offline_replay_returns_authoritative_value(
    client, headers, progress_data
) -> None:
    """离线设备补传旧时间戳：拒绝并回传服务端权威值。"""
    book_id = progress_data["book_id"]
    base = now_ts()

    _put(client, headers, book_id, position_sec=250.0, client_updated_at=base)

    late = _put(
        client,
        headers,
        book_id,
        position_sec=260.0,
        client_updated_at=base - 600,
    )
    assert late["accepted"] is False
    assert late["position_sec"] == 250.0

    server = client.get(f"/api/v1/progress/{book_id}", headers=headers).json()
    assert server["position_sec"] == 250.0
    assert server["updated_at"] > 0


def test_sync_clock_skew_does_not_lock_other_devices(
    client, headers, progress_data
) -> None:
    """时钟快 1 小时的设备写入后，正常设备仍能继续更新。"""
    book_id = progress_data["book_id"]
    base = now_ts()

    skewed = _put(
        client, headers, book_id, position_sec=120.0, client_updated_at=base + 3600
    )
    assert skewed["accepted"] is True

    normal = _put(
        client, headers, book_id, position_sec=130.0, client_updated_at=base + 2
    )
    assert normal["accepted"] is True
    assert normal["position_sec"] == 130.0


# ---------------- 进度检查点（每本书最近 7 个） ----------------


def test_history_refreshes_in_place_within_delta(
    client, headers, progress_data
) -> None:
    """阈值内只刷新同一条，不产生垃圾快照（本书 300 秒 → 阈值 5 分钟）。"""
    book_id = progress_data["book_id"]
    base = now_ts()
    _put(
        client,
        headers,
        book_id,
        position_sec=50.0,
        explicit_seek=True,
        client_updated_at=base,
    )
    _put(
        client,
        headers,
        book_id,
        position_sec=60.0,
        explicit_seek=True,
        client_updated_at=base + 2,
    )

    items = client.get(f"/api/v1/progress/{book_id}/history", headers=headers).json()[
        "items"
    ]
    assert len(items) == 1
    assert items[0]["position_sec"] == 60.0
    assert items[0]["device_id"] == "web-test"


def test_history_requires_auth(client, progress_data) -> None:
    book_id = progress_data["book_id"]
    assert client.get(f"/api/v1/progress/{book_id}/history").status_code == 401


def test_delete_progress_clears_history(client, headers, progress_data) -> None:
    book_id = progress_data["book_id"]
    _put(client, headers, book_id, position_sec=10.0, explicit_seek=True)
    assert (
        client.delete(f"/api/v1/progress/{book_id}", headers=headers).status_code == 204
    )
    items = client.get(f"/api/v1/progress/{book_id}/history", headers=headers).json()[
        "items"
    ]
    assert items == []


def test_history_keeps_latest_seven(progress_data) -> None:
    """长篇（10 小时）阈值 18 分钟：间隔 2000 秒每次新增，超过 7 条淘汰最旧。"""
    session = get_session_factory()()
    try:
        user = session.scalar(select(User).where(User.username == "admin"))
        assert user is not None
        book_id = progress_data["book_id"]
        base = 1_700_000_000

        for index, position in enumerate([0, 2000, 4000, 6000, 8000, 10000, 12000]):
            record_checkpoint(
                session,
                user_id=user.id,
                book_id=book_id,
                position_sec=float(position),
                track_id=None,
                device_id="web-test",
                total_duration_sec=36000.0,
                now=base + index,
            )
        session.commit()

        query = (
            select(ProgressHistory)
            .where(
                ProgressHistory.user_id == user.id,
                ProgressHistory.book_id == book_id,
            )
            .order_by(ProgressHistory.created_at.desc(), ProgressHistory.id.desc())
        )
        rows = session.scalars(query).all()
        assert len(rows) == HISTORY_LIMIT == 7
        assert [int(row.position_sec) for row in rows] == [
            12000,
            10000,
            8000,
            6000,
            4000,
            2000,
            0,
        ]

        # 300 秒 < 阈值 1080 秒：刷新最新一条，不新增
        record_checkpoint(
            session,
            user_id=user.id,
            book_id=book_id,
            position_sec=12300.0,
            track_id=None,
            device_id="web-test",
            total_duration_sec=36000.0,
            now=base + 100,
        )
        session.commit()

        rows = session.scalars(query).all()
        assert len(rows) == 7
        assert rows[0].position_sec == 12300.0
        assert rows[0].created_at == base + 100
    finally:
        session.close()


def test_history_dedupes_when_jumping_back(progress_data) -> None:
    """误拖出去再撤销回来：刷新原快照，不在列表里留两条几乎相同的位置。"""
    session = get_session_factory()()
    try:
        user = session.scalar(select(User).where(User.username == "admin"))
        assert user is not None
        book_id = progress_data["book_id"]
        base = 1_700_000_000

        def record(position: float, offset: int) -> None:
            record_checkpoint(
                session,
                user_id=user.id,
                book_id=book_id,
                position_sec=position,
                track_id=None,
                device_id="web-test",
                total_duration_sec=36000.0,
                now=base + offset,
            )
            session.commit()

        record(5000.0, 0)
        record(30000.0, 10)  # 误拖
        record(5010.0, 20)  # 撤销回来

        query = (
            select(ProgressHistory)
            .where(
                ProgressHistory.user_id == user.id,
                ProgressHistory.book_id == book_id,
            )
            .order_by(ProgressHistory.created_at.desc(), ProgressHistory.id.desc())
        )
        rows = session.scalars(query).all()
        assert [int(row.position_sec) for row in rows] == [5010, 30000]
    finally:
        session.close()


# ---------------- 收听统计 ----------------


def test_listening_stats_accumulate(client, headers, progress_data) -> None:
    book_id = progress_data["book_id"]
    base = now_ts()
    _put(client, headers, book_id, position_sec=10.0, client_updated_at=base)
    _put(client, headers, book_id, position_sec=40.0, client_updated_at=base + 15)

    stats = client.get("/api/v1/stats", headers=headers).json()
    assert stats["today_sec"] == 30
    assert stats["total_sec"] == 30
    assert stats["streak_days"] == 1
    assert len(stats["days"]) == 7
    assert stats["days"][-1]["seconds"] == 30


def test_listening_stats_ignore_seek_and_rewind(client, headers, progress_data) -> None:
    book_id = progress_data["book_id"]
    base = now_ts()
    _put(client, headers, book_id, position_sec=10.0, client_updated_at=base)
    # 拖动进度条不算收听
    _put(
        client,
        headers,
        book_id,
        position_sec=200.0,
        client_updated_at=base + 10,
        explicit_seek=True,
    )
    # 往回拖也不算
    _put(
        client,
        headers,
        book_id,
        position_sec=50.0,
        client_updated_at=base + 20,
        explicit_seek=True,
    )

    stats = client.get("/api/v1/stats", headers=headers).json()
    assert stats["today_sec"] == 0


def test_listening_stats_divide_by_playback_rate(
    client, headers, progress_data
) -> None:
    """2 倍速下 60 秒进度约等于 30 秒真实收听。"""
    book_id = progress_data["book_id"]
    base = now_ts()
    _put(client, headers, book_id, position_sec=10.0, client_updated_at=base)
    _put(
        client,
        headers,
        book_id,
        position_sec=70.0,
        client_updated_at=base + 15,
        playback_rate=2.0,
    )

    stats = client.get("/api/v1/stats", headers=headers).json()
    assert stats["today_sec"] == 30


def test_stats_requires_auth(client, progress_data) -> None:
    assert client.get("/api/v1/stats").status_code == 401


def test_stats_streak_counts_consecutive_days(progress_data) -> None:
    session = get_session_factory()()
    try:
        user = session.scalar(select(User).where(User.username == "admin"))
        assert user is not None
        today = date.today()
        # 今天、昨天、前天有记录，大前天断了
        for offset in (0, 1, 2, 4):
            session.add(
                ListeningDaily(
                    user_id=user.id,
                    day=(today - timedelta(days=offset)).isoformat(),
                    seconds=60,
                    updated_at=now_ts(),
                )
            )
        session.commit()

        data = collect_stats(session, user_id=user.id, days=7)
        assert data["streak_days"] == 3
        assert data["total_sec"] == 240
        assert data["today_sec"] == 60
    finally:
        session.close()
