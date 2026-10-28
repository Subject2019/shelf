"""M1-T05 验收：5 种格式解析出 title/author/duration/chapters。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.metadata import (
    UnsupportedAudioError,
    build_virtual_chapters,
    read_audio_metadata,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    ("filename", "expected_format", "expected_title"),
    [
        ("sample.mp3", "mp3", "三体"),
        ("sample.m4a", "m4a", "球状闪电"),
        ("sample.m4b", "m4b", "三体·章节版"),
        ("sample.flac", "flac", "三体"),
        ("sample.ogg", "ogg", "黑暗森林"),
    ],
)
def test_reads_basic_metadata(
    filename: str, expected_format: str, expected_title: str
) -> None:
    path = FIXTURES / filename
    if not path.exists():
        pytest.skip(f"缺少样本 {filename}，先运行 tests/fixtures/gen.sh")

    meta = read_audio_metadata(path)
    assert meta.title == expected_title
    assert meta.author == "刘慈欣"
    assert meta.format == expected_format
    assert meta.duration_sec == pytest.approx(12, abs=1.0)
    assert meta.has_cover is False


def test_m4b_embedded_chapters() -> None:
    path = FIXTURES / "sample.m4b"
    if not path.exists():
        pytest.skip("缺少样本 sample.m4b，先运行 tests/fixtures/gen.sh")

    meta = read_audio_metadata(path)
    assert meta.chapter_source == "embedded"
    assert len(meta.chapters) == 2
    assert [chapter.title for chapter in meta.chapters] == [
        "第一章 科学边界",
        "第二章 台球",
    ]
    assert meta.chapters[0].start_sec == pytest.approx(0.0, abs=0.2)
    assert meta.chapters[1].start_sec == pytest.approx(6.0, abs=0.2)
    assert meta.chapters[1].end_sec == pytest.approx(12.0, abs=0.3)


def test_flac_series_tags() -> None:
    path = FIXTURES / "sample.flac"
    if not path.exists():
        pytest.skip("缺少样本 sample.flac，先运行 tests/fixtures/gen.sh")

    meta = read_audio_metadata(path)
    assert meta.series == "地球往事"
    assert meta.series_index == 1.0


def test_unsupported_file_raises(tmp_path: Path) -> None:
    broken = tmp_path / "broken.mp3"
    broken.write_bytes(b"this is not an audio file")
    with pytest.raises(UnsupportedAudioError):
        read_audio_metadata(broken)


def test_virtual_chapters_split_by_segment() -> None:
    chapters = build_virtual_chapters(3600, segment_min=15)
    assert len(chapters) == 4
    assert chapters[0].start_sec == 0.0
    assert chapters[-1].end_sec == 3600.0
    assert {chapter.source for chapter in chapters} == {"virtual"}

    short = build_virtual_chapters(600, segment_min=15)
    assert len(short) == 1
    assert short[0].end_sec == 600.0

    assert build_virtual_chapters(None) == []
    assert build_virtual_chapters(0) == []
