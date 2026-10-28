"""M1-T06 验收：Range 解析边界与大偏移。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.streamer import (
    ByteRange,
    RangeNotSatisfiable,
    content_type_for,
    parse_range,
    resolve_media_path,
)


def test_no_range_returns_full_file() -> None:
    assert parse_range(None, 1024) is None
    assert parse_range("   ", 1024) is None


def test_closed_range() -> None:
    assert parse_range("bytes=0-9", 1024) == ByteRange(0, 9)


def test_open_ended_range() -> None:
    assert parse_range("bytes=1000-", 1024) == ByteRange(1000, 1023)


def test_suffix_range() -> None:
    assert parse_range("bytes=-24", 1024) == ByteRange(1000, 1023)


def test_suffix_larger_than_file_covers_all() -> None:
    assert parse_range("bytes=-4096", 1024) == ByteRange(0, 1023)


def test_end_beyond_file_is_clamped() -> None:
    assert parse_range("bytes=1000-9999", 1024) == ByteRange(1000, 1023)


def test_multipart_uses_first_segment() -> None:
    assert parse_range("bytes=0-9, 20-29", 1024) == ByteRange(0, 9)


@pytest.mark.parametrize(
    "header",
    [
        "bytes=1024-",
        "bytes=2000-3000",
        "bytes=abc-def",
        "items=0-10",
        "bytes=-0",
        "bytes=10-5",
        "bytes=",
    ],
)
def test_unsatisfiable_ranges(header: str) -> None:
    with pytest.raises(RangeNotSatisfiable):
        parse_range(header, 1024)


def test_range_on_empty_file() -> None:
    with pytest.raises(RangeNotSatisfiable):
        parse_range("bytes=0-1", 0)


def test_handles_offsets_beyond_32bit() -> None:
    size = 5_000_000_000
    parsed = parse_range("bytes=3000000000-", size)
    assert parsed == ByteRange(3_000_000_000, size - 1)
    assert parsed is not None
    assert parsed.length == size - 3_000_000_000


def test_content_type_mapping() -> None:
    assert content_type_for("m4b") == "audio/mp4"
    assert content_type_for("MP3") == "audio/mpeg"
    assert content_type_for(None) == "application/octet-stream"


def test_resolve_media_path_blocks_traversal(tmp_path: Path) -> None:
    root = tmp_path / "library"
    root.mkdir()
    inside = root / "book.mp3"
    inside.write_bytes(b"x")
    outside = tmp_path / "secret.mp3"
    outside.write_bytes(b"x")

    assert resolve_media_path(root, "book.mp3") == inside.resolve()
    assert resolve_media_path(root, "../secret.mp3") is None
    assert resolve_media_path(root, "missing.mp3") is None
