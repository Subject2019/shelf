"""按章节切片并缓存。

用途：让客户端（安卓 / 第三方）能按「第 N 集」单独下载，不必整卷拉走。
WebUI 不使用（播放走整文件 Range 直出，见 `services/streamer.py`）。

实现要点：
- 用 ffmpeg **流复制**（`-c:a copy`）切割：不重编码、CPU 开销极小、无质量损失；
  代价是切点按音频帧对齐（AAC 一帧 ≈ 21ms），实际偏差通常在 50ms 内。
- 缓存键包含源文件的 `mtime` 与 `size`：源文件被替换后旧缓存自然失效，
  不需要额外的失效逻辑。
- 同一章节的并发请求用进程内锁串行化，避免重复切片；写入先落临时文件再
  `os.replace`，客户端读不到半成品。
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings

logger = logging.getLogger(__name__)

# 源格式 → (输出后缀, ffmpeg 尾部参数)。这些容器可以直接承载原音频流
_COPY_PLANS: dict[str, tuple[str, list[str]]] = {
    "m4b": ("m4a", ["-c:a", "copy", "-movflags", "+faststart"]),
    "m4a": ("m4a", ["-c:a", "copy", "-movflags", "+faststart"]),
    "mp4": ("m4a", ["-c:a", "copy", "-movflags", "+faststart"]),
    "aac": ("m4a", ["-c:a", "copy", "-movflags", "+faststart"]),
    "mp3": ("mp3", ["-c:a", "copy", "-f", "mp3"]),
    "flac": ("flac", ["-c:a", "copy", "-f", "flac"]),
    "ogg": ("ogg", ["-c:a", "copy", "-f", "ogg"]),
    "oga": ("ogg", ["-c:a", "copy", "-f", "ogg"]),
    "opus": ("ogg", ["-c:a", "copy", "-f", "ogg"]),
}

# wma / ape / dsf / dff / wav 等不能直接装进 mp4，统一转 64k AAC
_TRANSCODE_PLAN = ("m4a", ["-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart"])

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


class ChapterAudioError(RuntimeError):
    """切片失败：`code` 会原样出现在错误响应里。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class ChapterAudio:
    path: Path
    cache_key: str
    content_type: str
    created: bool


def plan_output(source_format: str | None) -> tuple[str, list[str], bool]:
    """返回 (输出后缀, ffmpeg 参数, 是否需要转码)。"""
    fmt = (source_format or "").lower()
    plan = _COPY_PLANS.get(fmt)
    if plan is not None:
        return plan[0], plan[1], False
    return _TRANSCODE_PLAN[0], _TRANSCODE_PLAN[1], True


def cache_dir(settings: Settings, book_id: int) -> Path:
    return settings.chapter_cache_dir / str(book_id)


def cache_key(index: int, mtime: int, size: int, suffix: str) -> str:
    return f"{index:04d}-{mtime}-{size}.{suffix}"


def cached_path(
    settings: Settings,
    book_id: int,
    index: int,
    mtime: int,
    size: int,
    source_format: str | None,
) -> tuple[Path, str]:
    suffix, _, _ = plan_output(source_format)
    key = cache_key(index, mtime, size, suffix)
    return cache_dir(settings, book_id) / key, key


def _lock_for(key: str) -> threading.Lock:
    with _locks_guard:
        lock = _locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _locks[key] = lock
        return lock


def ensure_chapter_audio(
    settings: Settings,
    *,
    book_id: int,
    index: int,
    source: Path,
    source_format: str | None,
    mtime: int,
    size: int,
    start_sec: float,
    duration_sec: float,
) -> ChapterAudio:
    """命中缓存直接返回；否则切一段写入缓存再返回。"""
    if not settings.enable_chapter_cache:
        raise ChapterAudioError("chapter_cache_disabled", "按章节缓存未启用")

    suffix, ffmpeg_tail, needs_transcode = plan_output(source_format)
    dest, key = cached_path(settings, book_id, index, mtime, size, source_format)

    if dest.is_file() and dest.stat().st_size > 0:
        return ChapterAudio(dest, key, content_type_for(suffix), False)

    if needs_transcode and not settings.enable_transcode:
        raise ChapterAudioError(
            "transcode_disabled",
            f"{source_format or '该格式'} 需要转码才能切片，但转码已关闭",
        )

    with _lock_for(str(dest)):
        # 等锁期间可能已被别的请求生成
        if dest.is_file() and dest.stat().st_size > 0:
            return ChapterAudio(dest, key, content_type_for(suffix), False)

        dest.parent.mkdir(parents=True, exist_ok=True)
        _slice(settings, source, dest, start_sec, duration_sec, ffmpeg_tail)
        _drop_stale_versions(dest.parent, index, keep=dest)
        _prune_total(settings)

    logger.info(
        "章节切片完成",
        extra={
            "extra_fields": {
                "book_id": book_id,
                "index": index,
                "bytes": dest.stat().st_size,
                "path": str(dest),
            }
        },
    )
    return ChapterAudio(dest, key, content_type_for(suffix), True)


def _slice(
    settings: Settings,
    source: Path,
    dest: Path,
    start_sec: float,
    duration_sec: float,
    ffmpeg_tail: list[str],
) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise ChapterAudioError("ffmpeg_missing", "服务端未安装 ffmpeg，无法切片")

    temp = dest.with_name(f".{dest.stem}.{uuid.uuid4().hex[:8]}.tmp{dest.suffix}")
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        # -ss 放在 -i 前是输入侧快速定位，配合 copy 无需解码
        "-ss",
        f"{max(start_sec, 0):.3f}",
        "-t",
        f"{max(duration_sec, 0.5):.3f}",
        "-i",
        str(source),
        "-map",
        "0:a:0",
        "-vn",
        "-sn",
        "-dn",
        # m4b 的章节常以「text」数据轨存在，不带这个参数会跟进切片文件里
        "-map_chapters",
        "-1",
        *ffmpeg_tail,
        "-y",
        str(temp),
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=settings.chapter_slice_timeout,
        )
    except subprocess.TimeoutExpired as exc:
        temp.unlink(missing_ok=True)
        raise ChapterAudioError("slice_timeout", "切片超时") from exc

    if completed.returncode != 0 or not temp.is_file() or temp.stat().st_size == 0:
        temp.unlink(missing_ok=True)
        detail = (completed.stderr or "").strip().splitlines()
        raise ChapterAudioError(
            "slice_failed", detail[-1] if detail else "ffmpeg 切片失败"
        )

    os.replace(temp, dest)


def _drop_stale_versions(folder: Path, index: int, keep: Path) -> None:
    """同一章节只保留当前源文件版本，换文件后旧切片自动回收。"""
    for old in folder.glob(f"{index:04d}-*"):
        if old != keep and old.is_file():
            old.unlink(missing_ok=True)


def _prune_total(settings: Settings) -> None:
    """缓存总量超过上限时按最后修改时间删最旧的切片。"""
    limit = settings.chapter_cache_max_bytes
    if limit <= 0:
        return

    root = settings.chapter_cache_dir
    if not root.is_dir():
        return

    files: list[tuple[float, int, Path]] = []
    total = 0
    for path in root.rglob("*"):
        if not path.is_file() or path.name.startswith("."):
            continue
        stat = path.stat()
        total += stat.st_size
        files.append((stat.st_mtime, stat.st_size, path))

    if total <= limit:
        return

    files.sort()
    for _, size, path in files:
        if total <= limit:
            break
        path.unlink(missing_ok=True)
        total -= size
        logger.info("清理过期章节缓存：%s", path)


def clear_book_cache(settings: Settings, book_id: int) -> int:
    """删除某本书的全部切片，返回删除的文件数。"""
    folder = cache_dir(settings, book_id)
    if not folder.is_dir():
        return 0

    removed = 0
    for path in folder.iterdir():
        if path.is_file():
            path.unlink(missing_ok=True)
            removed += 1
    try:
        folder.rmdir()
    except OSError:
        pass
    return removed


def content_type_for(suffix: str) -> str:
    """切片容器 → MIME。suffix 可带前导点。"""
    return {
        "m4a": "audio/mp4",
        "mp3": "audio/mpeg",
        "flac": "audio/flac",
        "ogg": "audio/ogg",
    }.get(suffix.lstrip(".").lower(), "application/octet-stream")
