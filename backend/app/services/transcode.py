"""整轨转码（opus / mp3）。

浏览器对 wma / ape 这类格式支持很差，播放时带 `?transcode=opus` 即可拿到可播版本。

策略：整轨只转一次，按「源文件 mtime + size + 目标编码 + 码率」做缓存键，
之后所有 Range 请求直接读缓存文件。同一轨并发请求串行化，临时文件 + `os.replace`
原子落盘，客户端不会读到半成品。超过 `TRANSCODE_MAX_BYTES` 按最旧优先清理。
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings

logger = logging.getLogger(__name__)

DEFAULT_BITRATE = 64
MIN_BITRATE = 16
MAX_BITRATE = 320

# codec -> (后缀, Content-Type, ffmpeg 输出参数)
_CODECS: dict[str, tuple[str, str, list[str]]] = {
    "opus": ("webm", "audio/webm", ["-c:a", "libopus", "-f", "webm"]),
    "mp3": ("mp3", "audio/mpeg", ["-c:a", "libmp3lame", "-f", "mp3"]),
}

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()

_stats_guard = threading.Lock()
_active = 0
_completed = 0


class TranscodeError(RuntimeError):
    """转码失败：`code` 原样出现在错误响应里。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class TranscodedAudio:
    path: Path
    cache_key: str
    content_type: str
    codec: str
    bitrate: int
    created: bool


def normalize(codec: str | None, bitrate: int | None) -> tuple[str, int]:
    name = (codec or "").strip().lower()
    if name not in _CODECS:
        raise TranscodeError(
            "transcode_unsupported",
            f"不支持的转码格式：{codec or '空'}（可选 opus / mp3）",
        )
    rate = DEFAULT_BITRATE if bitrate is None else bitrate
    if not MIN_BITRATE <= rate <= MAX_BITRATE:
        raise TranscodeError(
            "transcode_unsupported",
            f"码率需在 {MIN_BITRATE}-{MAX_BITRATE} kbps 之间",
        )
    return name, rate


def stats() -> dict[str, int | bool]:
    with _stats_guard:
        return {"active": _active, "completed": _completed}


def cache_dir(settings: Settings, book_id: int) -> Path:
    return settings.transcode_cache_dir / str(book_id)


def cache_key(
    track_id: int, mtime: int, size: int, codec: str, bitrate: int, suffix: str
) -> str:
    return f"{track_id:06d}-{mtime}-{size}-{codec}-{bitrate}.{suffix}"


def ensure_transcoded(
    settings: Settings,
    *,
    book_id: int,
    track_id: int,
    source: Path,
    mtime: int,
    size: int,
    codec: str,
    bitrate: int,
    duration_sec: float | None = None,
) -> TranscodedAudio:
    if not settings.enable_transcode:
        raise TranscodeError(
            "transcode_disabled", "转码已关闭（ECHOSHELF_ENABLE_TRANSCODE）"
        )

    suffix, content_type, _ = _CODECS[codec]
    dest = cache_dir(settings, book_id) / cache_key(
        track_id, mtime, size, codec, bitrate, suffix
    )
    key = dest.name

    if dest.is_file() and dest.stat().st_size > 0:
        return TranscodedAudio(dest, key, content_type, codec, bitrate, False)

    with _lock_for(str(dest)):
        # 等锁期间可能已被别的请求生成
        if dest.is_file() and dest.stat().st_size > 0:
            return TranscodedAudio(dest, key, content_type, codec, bitrate, False)

        limit = settings.transcode_max_duration_sec
        if limit > 0 and duration_sec and duration_sec > limit:
            raise TranscodeError(
                "transcode_too_long",
                f"单轨 {duration_sec / 3600:.1f} 小时，超过整轨转码上限 {limit / 3600:.1f} 小时；"
                "请改用按章节切片接口 /books/{id}/chapters/{idx}/cache",
            )

        dest.parent.mkdir(parents=True, exist_ok=True)
        _run_ffmpeg(settings, source, dest, codec, bitrate)
        _drop_stale_versions(dest.parent, track_id, keep=dest)
        _prune_total(settings, keep=dest)

    logger.info(
        "整轨转码完成",
        extra={
            "extra_fields": {
                "book_id": book_id,
                "track_id": track_id,
                "codec": codec,
                "bitrate": bitrate,
                "bytes": dest.stat().st_size,
                "seconds": round(_last_duration_sec(), 1),
            }
        },
    )
    return TranscodedAudio(dest, key, content_type, codec, bitrate, True)


# 最近一次转码耗时，仅用于日志
_last_seconds = 0.0


def _last_duration_sec() -> float:
    return _last_seconds


def _lock_for(key: str) -> threading.Lock:
    with _locks_guard:
        lock = _locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _locks[key] = lock
        return lock


def _run_ffmpeg(
    settings: Settings,
    source: Path,
    dest: Path,
    codec: str,
    bitrate: int,
) -> None:
    global _active, _completed, _last_seconds

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise TranscodeError("ffmpeg_missing", "服务端未安装 ffmpeg，无法转码")

    _, _, tail = _CODECS[codec]
    temp = dest.with_name(f".{dest.stem}.{uuid.uuid4().hex[:8]}.tmp{dest.suffix}")
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-i",
        str(source),
        "-vn",
        "-sn",
        "-dn",
        "-map",
        "0:a:0",
        # 转码产物不需要章节/封面等附加流
        "-map_chapters",
        "-1",
        *tail,
        "-b:a",
        f"{bitrate}k",
        "-y",
        str(temp),
    ]

    started = time.monotonic()
    with _stats_guard:
        _active += 1
    try:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            timeout=settings.transcode_timeout,
        )
    except subprocess.TimeoutExpired as exc:
        temp.unlink(missing_ok=True)
        raise TranscodeError(
            "transcode_timeout",
            f"转码超过 {settings.transcode_timeout} 秒仍未完成",
        ) from exc
    except subprocess.CalledProcessError as exc:
        temp.unlink(missing_ok=True)
        stderr = (exc.stderr or b"").decode("utf-8", "ignore").strip()[-300:]
        raise TranscodeError("transcode_failed", stderr or "ffmpeg 转码失败") from exc
    finally:
        with _stats_guard:
            _active -= 1

    if not temp.is_file() or temp.stat().st_size == 0:
        temp.unlink(missing_ok=True)
        raise TranscodeError("transcode_failed", "转码产物为空")

    os.replace(temp, dest)
    _last_seconds = time.monotonic() - started
    with _stats_guard:
        _completed += 1


def _drop_stale_versions(folder: Path, track_id: int, keep: Path) -> None:
    """同一轨只保留当前源文件版本（换文件后旧产物自动回收）。"""
    for old in folder.glob(f"{track_id:06d}-*"):
        if old != keep and old.is_file():
            old.unlink(missing_ok=True)


def _prune_total(settings: Settings, keep: Path) -> None:
    root = settings.transcode_cache_dir
    if not root.is_dir():
        return

    files = [path for path in root.rglob("*") if path.is_file() and path != keep]
    total = sum(path.stat().st_size for path in files) + keep.stat().st_size
    if total <= settings.transcode_max_bytes:
        return

    files.sort(key=lambda path: path.stat().st_mtime)
    for path in files:
        if total <= settings.transcode_max_bytes:
            break
        try:
            total -= path.stat().st_size
            path.unlink()
        except OSError:
            continue
    logger.info("转码缓存已清理", extra={"extra_fields": {"total": total}})
