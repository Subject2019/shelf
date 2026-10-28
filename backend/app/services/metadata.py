"""音频元数据与内嵌章节解析。

分工（docs/AUDIO_FORMATS.md §3.2）：mutagen 负责标签/时长/编码信息，ffprobe 负责章节，
因为 ffmpeg 对 chpl、ID3 CHAP 的解析覆盖面最广。纯函数，不碰数据库，便于单测。
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import mutagen
from mutagen.flac import FLAC
from mutagen.id3 import ID3, CHAP
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4, MP4FreeForm
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis

EMBEDDED = "embedded"
CUE = "cue"
TRACK_SPLIT = "track_split"
VIRTUAL = "virtual"
MANUAL = "manual"


class UnsupportedAudioError(Exception):
    """mutagen 无法识别的容器。调用方应记 warn 并跳过该文件。"""


@dataclass(slots=True)
class ChapterInfo:
    title: str
    start_sec: float
    end_sec: float | None
    source: str = EMBEDDED


@dataclass(slots=True)
class AudioMetadata:
    title: str | None = None
    author: str | None = None
    album_artist: str | None = None
    narrator: str | None = None
    publisher: str | None = None
    year: int | None = None
    language: str | None = None
    description: str | None = None
    series: str | None = None
    series_index: float | None = None
    duration_sec: float | None = None
    format: str | None = None
    codec: str | None = None
    bitrate: int | None = None
    sample_rate: int | None = None
    channels: int | None = None
    has_cover: bool = False
    chapters: list[ChapterInfo] = field(default_factory=list)
    chapter_source: str | None = None


def read_audio_metadata(path: Path) -> AudioMetadata:
    """读取单个音频文件。未知容器抛 UnsupportedAudioError。"""
    try:
        audio = mutagen.File(path)
    except (mutagen.MutagenError, OSError) as exc:
        raise UnsupportedAudioError(str(path)) from exc
    if audio is None:
        raise UnsupportedAudioError(str(path))

    info = getattr(audio, "info", None)
    tags = getattr(audio, "tags", None)
    meta = AudioMetadata(
        format=path.suffix.lstrip(".").lower() or None,
        codec=_guess_codec(audio),
        duration_sec=float(info.length) if info is not None else None,
        bitrate=int(info.bitrate // 1000) if getattr(info, "bitrate", None) else None,
        sample_rate=getattr(info, "sample_rate", None),
        channels=getattr(info, "channels", None),
    )

    if isinstance(audio, MP3):
        _apply_id3(meta, tags)
        meta.has_cover = bool(isinstance(tags, ID3) and tags.getall("APIC"))
    elif isinstance(audio, MP4):
        _apply_mp4(meta, tags)
    elif isinstance(audio, FLAC):
        _apply_vorbis(meta, tags)
        meta.has_cover = bool(getattr(audio, "pictures", None))
    elif isinstance(audio, (OggVorbis, OggOpus)):
        _apply_vorbis(meta, tags)
        meta.has_cover = bool(tags and tags.get("metadata_block_picture"))

    probe = _ffprobe(path)
    if meta.duration_sec is None and probe:
        meta.duration_sec = _to_float(probe.get("format", {}).get("duration"))

    chapters = _chapters_from_probe(probe)
    if not chapters and isinstance(audio, MP3) and isinstance(tags, ID3):
        # ffprobe 缺失或版本过旧时退到 ID3 CHAP
        chapters = _chapters_from_id3(tags)
    meta.chapters = _sanitize_chapters(chapters, meta.duration_sec)
    if meta.chapters:
        meta.chapter_source = EMBEDDED
    return meta


def build_virtual_chapters(
    duration_sec: float | None, segment_min: int = 15
) -> list[ChapterInfo]:
    """无内嵌章节、无 CUE 时按固定长度切分（docs/AUDIO_FORMATS.md §3.1 兜底）。"""
    if not duration_sec or duration_sec <= 0:
        return []
    segment = max(1, segment_min) * 60
    chapters: list[ChapterInfo] = []
    start = 0.0
    index = 0
    while start < duration_sec:
        end = min(start + segment, duration_sec)
        chapters.append(
            ChapterInfo(
                title=f"第 {index + 1} 段",
                start_sec=start,
                end_sec=end,
                source=VIRTUAL,
            )
        )
        start = end
        index += 1
    return chapters


def _guess_codec(audio: Any) -> str | None:
    if isinstance(audio, MP3):
        return "mp3"
    if isinstance(audio, MP4):
        codec = str(getattr(audio.info, "codec", "")).lower()
        return "alac" if "alac" in codec else "aac"
    if isinstance(audio, FLAC):
        return "flac"
    if isinstance(audio, OggOpus):
        return "opus"
    if isinstance(audio, OggVorbis):
        return "vorbis"
    return None


# ---------------- 标签映射：统一到 AudioMetadata ----------------


def _apply_id3(meta: AudioMetadata, tags: Any) -> None:
    if not isinstance(tags, ID3):
        return
    meta.title = _id3_text(tags, "TIT2")
    meta.author = _id3_text(tags, "TPE1")
    meta.album_artist = _id3_text(tags, "TPE2")
    meta.narrator = _id3_txxx(tags, "NARRATOR")
    meta.series = _id3_txxx(tags, "SERIES")
    meta.series_index = _to_float(_id3_txxx(tags, "SERIES-PART"))
    meta.publisher = _id3_text(tags, "TPUB")
    meta.year = _to_year(_id3_text(tags, "TDRC"))
    meta.language = _id3_text(tags, "TLAN")
    meta.description = _id3_comm(tags)


def _apply_mp4(meta: AudioMetadata, tags: Any) -> None:
    if not tags:
        return

    def plain(key: str) -> str | None:
        return _to_text(tags.get(key))

    def freeform(key: str) -> str | None:
        value = tags.get(f"----:com.apple.iTunes:{key}")
        if isinstance(value, list) and value:
            raw = value[0]
            if isinstance(raw, MP4FreeForm):
                return bytes(raw).decode("utf-8", errors="replace")
            if isinstance(raw, bytes):
                return raw.decode("utf-8", errors="replace")
        return None

    meta.title = plain("©nam")
    meta.author = plain("©ART")
    meta.album_artist = plain("aART")
    meta.narrator = plain("©nrt") or freeform("NARRATOR")
    meta.series = freeform("SERIES")
    meta.series_index = _to_float(freeform("SERIES-PART"))
    meta.publisher = plain("©pub")
    meta.year = _to_year(plain("©day"))
    meta.language = plain("©lan") or freeform("LANGUAGE")
    meta.description = plain("desc") or plain("©cmt")


def _apply_vorbis(meta: AudioMetadata, tags: Any) -> None:
    if not tags:
        return
    meta.title = _to_text(tags.get("title"))
    meta.author = _to_text(tags.get("artist"))
    meta.album_artist = _to_text(tags.get("albumartist"))
    meta.narrator = _to_text(tags.get("narrator"))
    meta.series = _to_text(tags.get("series"))
    meta.series_index = _to_float(_to_text(tags.get("series-part")))
    meta.publisher = _to_text(tags.get("publisher"))
    meta.year = _to_year(_to_text(tags.get("date")))
    meta.language = _to_text(tags.get("language"))
    meta.description = _to_text(tags.get("description"))


def _id3_text(tags: ID3, key: str) -> str | None:
    frame = tags.get(key)
    text = getattr(frame, "text", None)
    if not text:
        return None
    return None if not str(text[0]).strip() else str(text[0]).strip()


def _id3_txxx(tags: ID3, desc: str) -> str | None:
    for frame in tags.getall("TXXX"):
        if getattr(frame, "desc", "").upper() == desc.upper():
            return _to_text(getattr(frame, "text", None))
    return None


def _id3_comm(tags: ID3) -> str | None:
    frames = tags.getall("COMM")
    for frame in frames:
        text = getattr(frame, "text", None)
        if text:
            return str(text[0])
    return None


def _to_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        if not value:
            return None
        value = value[0]
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    text = str(value).strip()
    return text or None


def _to_float(value: Any) -> float | None:
    text = _to_text(value) if not isinstance(value, (int, float)) else value
    if text is None:
        return None
    try:
        return float(str(text).replace(",", "."))
    except ValueError:
        return None


def _to_year(value: Any) -> int | None:
    text = _to_text(value)
    if not text:
        return None
    digits = "".join(ch for ch in text[:4] if ch.isdigit())
    return int(digits) if len(digits) == 4 else None


# ---------------- 内嵌章节 ----------------


def _ffprobe(path: Path) -> dict[str, Any] | None:
    executable = shutil.which("ffprobe")
    if executable is None:
        return None
    command = [
        executable,
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_chapters",
        "-show_format",
        str(path),
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=30, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _chapters_from_probe(probe: dict[str, Any] | None) -> list[ChapterInfo]:
    if not probe:
        return []
    chapters: list[ChapterInfo] = []
    for item in probe.get("chapters") or []:
        start = _to_float(item.get("start_time"))
        if start is None:
            continue
        title = _to_text((item.get("tags") or {}).get("title")) or ""
        chapters.append(
            ChapterInfo(
                title=title,
                start_sec=start,
                end_sec=_to_float(item.get("end_time")),
                source=EMBEDDED,
            )
        )
    chapters.sort(key=lambda chapter: chapter.start_sec)
    return chapters


def _chapters_from_id3(tags: ID3) -> list[ChapterInfo]:
    chapters: list[ChapterInfo] = []
    for frame in tags.getall("CHAP"):
        if not isinstance(frame, CHAP):
            continue
        title = ""
        for key, sub_frame in (frame.sub_frames or {}).items():
            if key.startswith("TIT2"):
                title = _to_text(getattr(sub_frame, "text", None)) or ""
                break
        # ID3 CHAP 的时间单位是毫秒
        chapters.append(
            ChapterInfo(
                title=title,
                start_sec=frame.start_time / 1000.0,
                end_sec=(frame.end_time / 1000.0) if frame.end_time else None,
                source=EMBEDDED,
            )
        )
    chapters.sort(key=lambda chapter: chapter.start_sec)
    return chapters


def _sanitize_chapters(
    chapters: list[ChapterInfo], duration: float | None
) -> list[ChapterInfo]:
    """裁剪越界、丢弃零长、抹平重叠（docs/AUDIO_FORMATS.md 边界 11）。"""
    cleaned: list[ChapterInfo] = []
    for chapter in sorted(chapters, key=lambda item: item.start_sec):
        start = max(0.0, chapter.start_sec)
        end = chapter.end_sec
        if duration is not None:
            if start >= duration:
                continue
            if end is not None:
                end = min(end, duration)
        if end is not None and end - start < 0.5:
            continue
        cleaned.append(replace(chapter, start_sec=start, end_sec=end))

    for index in range(len(cleaned) - 1):
        current, following = cleaned[index], cleaned[index + 1]
        if current.end_sec is None or current.end_sec > following.start_sec:
            cleaned[index] = replace(current, end_sec=following.start_sec)
    return cleaned
