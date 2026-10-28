"""CUE sheet 解析（docs/AUDIO_FORMATS.md §3.3）。

只做解析与时间换算，不访问数据库；一个 cue = 一本书，物理文件由调用方解析一次。
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from app.services.metadata import CUE, ChapterInfo

_FRAMES_PER_SECOND = 75  # CUE 的 MM:SS:FF，FF 为 1/75 秒
_MSF_RE = re.compile(r"(\d+):(\d{1,2}):(\d{1,2})")


@dataclass(slots=True)
class CueTrack:
    number: int
    title: str | None = None
    performer: str | None = None
    offset_sec: float | None = None  # 在所属文件内的起点


@dataclass(slots=True)
class CueFile:
    name: str
    tracks: list[CueTrack] = field(default_factory=list)


@dataclass(slots=True)
class CueSheet:
    title: str | None = None
    performer: str | None = None
    files: list[CueFile] = field(default_factory=list)

    @property
    def tracks(self) -> list[CueTrack]:
        return [track for cue_file in self.files for track in cue_file.tracks]


class CueParseError(Exception):
    """cue 内容不可用（无 TRACK、无 FILE 等）。扫描器应记 warn 并跳过。"""


def decode_cue_bytes(raw: bytes) -> str:
    """先 UTF-8，失败退 GB18030 —— 中文 cue 大量是 GBK。"""
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def parse_cue(path: Path) -> CueSheet:
    return parse_cue_text(decode_cue_bytes(path.read_bytes()))


def parse_cue_text(text: str) -> CueSheet:
    sheet = CueSheet()
    current_file: CueFile | None = None
    current_track: CueTrack | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.upper().startswith("REM"):
            continue
        keyword, _, rest = line.partition(" ")
        keyword = keyword.upper()
        rest = rest.strip()

        if keyword == "FILE":
            name = _first_token(rest)
            if not name:
                continue
            current_file = CueFile(name=name)
            sheet.files.append(current_file)
            current_track = None
        elif keyword == "TRACK":
            if current_file is None:
                # TRACK 前没有 FILE 的 cue 不合规范，忽略但不算致命
                continue
            number = _parse_int(_first_token(rest))
            current_track = CueTrack(number=number)
            current_file.tracks.append(current_track)
        elif keyword == "TITLE":
            value = _unquote(rest)
            if current_track is not None:
                current_track.title = value
            else:
                sheet.title = value
        elif keyword == "PERFORMER":
            value = _unquote(rest)
            if current_track is not None:
                current_track.performer = value
            else:
                sheet.performer = value
        elif keyword == "INDEX":
            if current_track is None:
                continue
            parts = rest.split()
            if len(parts) < 2:
                continue
            index_no, timestamp = parts[0], parts[1]
            if index_no != "01":
                continue
            seconds = msf_to_seconds(timestamp)
            if seconds is not None:
                current_track.offset_sec = seconds

    if not sheet.files or not sheet.tracks:
        raise CueParseError("cue 中没有有效的 FILE/TRACK")
    return sheet


def msf_to_seconds(value: str) -> float | None:
    """MM:SS:FF → 秒（1 帧 = 1/75 秒）。兼容超过 99 分钟。"""
    match = _MSF_RE.search(value.strip())
    if not match:
        return None
    minutes, seconds, frames = (int(part) for part in match.groups())
    return minutes * 60 + seconds + frames / _FRAMES_PER_SECOND


def cue_to_chapters(
    sheet: CueSheet, file_durations: Mapping[str, float | None]
) -> list[ChapterInfo]:
    """把 cue 分轨转成全书绝对秒数的章节。

    file_durations 以 FILE 中的文件名为键；缺失时末轨 end_sec 为 None（到结尾）。
    """
    starts: list[tuple[CueTrack, float]] = []
    cursor = 0.0
    duration_unknown = False
    for cue_file in sheet.files:
        for track in cue_file.tracks:
            starts.append((track, cursor + (track.offset_sec or 0.0)))
        duration = file_durations.get(cue_file.name)
        if duration is None:
            # 缺时长时用本文件最后一轨的起点兜底累计，避免后续文件起点重叠
            duration_unknown = True
            offsets = [
                track.offset_sec
                for track in cue_file.tracks
                if track.offset_sec is not None
            ]
            duration = max(offsets) if offsets else 0.0
        cursor += float(duration)

    chapters: list[ChapterInfo] = []
    for index, (track, start) in enumerate(starts):
        if index + 1 < len(starts):
            end: float | None = starts[index + 1][1]
        else:
            end = cursor if (cursor > start and not duration_unknown) else None
        chapters.append(
            ChapterInfo(
                title=track.title or f"Track {track.number:02d}",
                start_sec=start,
                end_sec=end,
                source=CUE,
            )
        )
    return chapters


def _first_token(value: str) -> str | None:
    value = value.strip()
    if not value:
        return None
    if value[0] in "\"'":
        quote = value[0]
        closing = value.find(quote, 1)
        return value[1:closing] if closing > 0 else value[1:]
    return value.split()[0]


def _unquote(value: str) -> str | None:
    value = value.strip()
    if not value:
        return None
    if value[0] in "\"'":
        quote = value[0]
        closing = value.find(quote, 1)
        return value[1:closing] if closing > 0 else value[1:]
    return value


def _parse_int(value: str | None) -> int:
    if not value:
        return 0
    digits = "".join(ch for ch in value if ch.isdigit())
    return int(digits) if digits else 0
