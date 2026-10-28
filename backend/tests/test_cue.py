"""M1-T05 验收：CUE 解析、GBK 编码、时间换算与全书章节累计。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.cue import (
    CueParseError,
    cue_to_chapters,
    decode_cue_bytes,
    msf_to_seconds,
    parse_cue,
    parse_cue_text,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_msf_to_seconds() -> None:
    assert msf_to_seconds("00:00:00") == 0.0
    assert msf_to_seconds("12:34:56") == pytest.approx(754 + 56 / 75, abs=1e-6)
    assert msf_to_seconds("100:00:00") == 6000.0
    assert msf_to_seconds("garbage") is None


def test_parse_utf8_cue() -> None:
    path = FIXTURES / "sample.cue"
    if not path.exists():
        pytest.skip("缺少样本 sample.cue，先运行 tests/fixtures/gen.sh")

    sheet = parse_cue(path)
    assert sheet.title == "三体"
    assert sheet.performer == "刘慈欣"
    assert sheet.files[0].name == "sample.flac"
    assert [track.title for track in sheet.tracks] == [
        "第一章 地球往事",
        "第二章 三体文明",
    ]
    assert sheet.tracks[1].offset_sec == pytest.approx(6.0)


def test_parse_gbk_cue_without_mojibake() -> None:
    path = FIXTURES / "sample_gbk.cue"
    if not path.exists():
        pytest.skip("缺少样本 sample_gbk.cue，先运行 tests/fixtures/gen.sh")

    sheet = parse_cue(path)
    assert sheet.tracks[0].title == "第一章 地球往事"
    assert sheet.title == "三体"


def test_decode_prefers_utf8_then_gb18030() -> None:
    assert decode_cue_bytes("标题".encode("utf-8")) == "标题"
    assert decode_cue_bytes("标题".encode("gb18030")) == "标题"


def test_cue_to_chapters_accumulates_offsets() -> None:
    sheet = parse_cue_text(
        'TITLE "合辑"\n'
        'FILE "a.flac" WAVE\n'
        "  TRACK 01 AUDIO\n"
        '    TITLE "A1"\n'
        "    INDEX 01 00:00:00\n"
        "  TRACK 02 AUDIO\n"
        '    TITLE "A2"\n'
        "    INDEX 01 00:05:00\n"
        'FILE "b.flac" WAVE\n'
        "  TRACK 03 AUDIO\n"
        '    TITLE "B1"\n'
        "    INDEX 01 00:00:00\n"
    )
    chapters = cue_to_chapters(sheet, {"a.flac": 10.0, "b.flac": 4.0})

    assert [chapter.title for chapter in chapters] == ["A1", "A2", "B1"]
    assert [chapter.start_sec for chapter in chapters] == [0.0, 5.0, 10.0]
    assert [chapter.end_sec for chapter in chapters] == [5.0, 10.0, 14.0]
    assert {chapter.source for chapter in chapters} == {"cue"}


def test_cue_without_tracks_is_invalid() -> None:
    with pytest.raises(CueParseError):
        parse_cue_text('TITLE "空"\n')
