"""HTTP Range 解析与分块读取（RFC 7233）。

偏移全程用 Python int（64 位），>2GB 的 m4b 不会溢出；
分块读取避免一次性把整个文件读进内存（AGENTS.md 架构红线 2）。
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

CHUNK_SIZE = 64 * 1024

CONTENT_TYPES = {
    "mp3": "audio/mpeg",
    "mp3pro": "audio/mpeg",
    "m4a": "audio/mp4",
    "m4b": "audio/mp4",
    "aac": "audio/aac",
    "flac": "audio/flac",
    "ogg": "audio/ogg",
    "oga": "audio/ogg",
    "opus": "audio/ogg",
    "wav": "audio/wav",
    "wma": "audio/x-ms-wma",
    "ape": "audio/x-ape",
    "dsf": "audio/x-dsf",
    "dff": "audio/x-dff",
    "aiff": "audio/aiff",
    "aif": "audio/aiff",
    "mka": "audio/x-matroska",
    "webm": "audio/webm",
}


class RangeNotSatisfiable(Exception):
    """请求头语法非法或范围越界，应返回 416。"""

    def __init__(self, file_size: int) -> None:
        super().__init__(f"range not satisfiable for size {file_size}")
        self.file_size = file_size


@dataclass(frozen=True, slots=True)
class ByteRange:
    start: int
    end: int  # 含尾

    @property
    def length(self) -> int:
        return self.end - self.start + 1


def parse_range(header: str | None, file_size: int) -> ByteRange | None:
    """返回 None 表示无 Range（整文件 200）。多段请求只取第一段。"""
    if header is None or not header.strip():
        return None
    if file_size <= 0:
        raise RangeNotSatisfiable(file_size)

    value = header.strip()
    if not value.lower().startswith("bytes="):
        raise RangeNotSatisfiable(file_size)

    spec = value.split("=", 1)[1].split(",")[0].strip()
    start_text, separator, end_text = spec.partition("-")
    if not separator:
        raise RangeNotSatisfiable(file_size)
    start_text = start_text.strip()
    end_text = end_text.strip()

    if not start_text:
        # bytes=-N：最后 N 字节
        if not end_text.isdigit():
            raise RangeNotSatisfiable(file_size)
        suffix = int(end_text)
        if suffix <= 0:
            raise RangeNotSatisfiable(file_size)
        return ByteRange(max(0, file_size - suffix), file_size - 1)

    if not start_text.isdigit():
        raise RangeNotSatisfiable(file_size)
    start = int(start_text)
    if start >= file_size:
        raise RangeNotSatisfiable(file_size)

    if end_text:
        if not end_text.isdigit():
            raise RangeNotSatisfiable(file_size)
        end = min(int(end_text), file_size - 1)
        if end < start:
            raise RangeNotSatisfiable(file_size)
        return ByteRange(start, end)

    return ByteRange(start, file_size - 1)


def iter_file_chunks(
    path: Path, start: int, length: int, chunk_size: int = CHUNK_SIZE
) -> Iterator[bytes]:
    remaining = length
    with path.open("rb") as handle:
        handle.seek(start)
        while remaining > 0:
            chunk = handle.read(min(chunk_size, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def content_type_for(audio_format: str | None) -> str:
    return CONTENT_TYPES.get((audio_format or "").lower(), "application/octet-stream")


def resolve_media_path(library_root: str | Path, rel_path: str) -> Path | None:
    """解析并校验仍在书库根目录内（防目录穿越）。"""
    root = Path(library_root).resolve()
    try:
        target = (root / rel_path).resolve()
    except OSError:
        return None
    if not target.is_relative_to(root):
        return None
    if not target.is_file():
        return None
    return target
