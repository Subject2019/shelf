"""按章节切片下载接口（给客户端用，WebUI 不调用）。

场景：安卓端要缓存「第 35 集」，不必整卷下载 600MB。
首次请求时服务端用 ffmpeg 流复制切出该集并写入缓存，之后直接命中。
"""

from __future__ import annotations

import urllib.parse
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models import Book, Chapter, Library, MediaFile, Track, User
from app.schemas.book import ChapterAudioOut, ChapterCacheList
from app.services.chapter_audio import (
    ChapterAudioError,
    clear_book_cache,
    content_type_for,
    ensure_chapter_audio,
)
from app.services.permissions import get_current_user, require_visible_book
from app.services.streamer import resolve_media_path

router = APIRouter(tags=["chapters"])


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _load(
    db: Session, user: User, book_id: int, chapter_index: int
) -> tuple[Book, Chapter]:
    book = require_visible_book(db, user, book_id)
    chapter = db.scalar(
        select(Chapter).where(Chapter.book_id == book.id, Chapter.idx == chapter_index)
    )
    if chapter is None:
        raise _error(404, "chapter_not_found", "章节不存在")
    return book, chapter


def _track_offset(db: Session, book_id: int, track: Track) -> float:
    """该音轨在全书时间轴上的起点（单文件书恒为 0）。"""
    rows = db.scalars(
        select(Track)
        .where(Track.book_id == book_id)
        .order_by(Track.disc_no, Track.track_no)
    ).all()
    offset = 0.0
    for item in rows:
        if item.id == track.id:
            break
        offset += item.duration_sec or 0.0
    return offset


def _chapter_window(
    db: Session, book: Book, chapter: Chapter, track: Track
) -> tuple[float, float]:
    """换算成「物理文件内的起点」和时长（秒）。"""
    offset = _track_offset(db, book.id, track)
    start_in_file = (track.start_offset_sec or 0.0) + max(
        chapter.start_sec - offset, 0.0
    )

    if chapter.end_sec is not None and chapter.end_sec > chapter.start_sec:
        duration = chapter.end_sec - chapter.start_sec
    else:
        following = db.scalar(
            select(Chapter)
            .where(Chapter.book_id == book.id, Chapter.idx > chapter.idx)
            .order_by(Chapter.idx)
            .limit(1)
        )
        if following is not None:
            duration = following.start_sec - chapter.start_sec
        else:
            duration = (track.duration_sec or 0.0) - (chapter.start_sec - offset)

    if duration <= 0:
        raise _error(409, "chapter_empty", "章节时长为空，无法切片")
    return start_in_file, duration


def _ensure(settings: Settings) -> None:
    if not settings.enable_chapter_cache:
        raise _error(503, "chapter_cache_disabled", "按章节缓存未启用")


def _slice(
    db: Session, settings: Settings, book: Book, chapter: Chapter
) -> tuple[Path, str, bool, float, float]:
    track = db.get(Track, chapter.track_id)
    if track is None:
        raise _error(404, "chapter_not_found", "章节缺少音轨")

    media = db.get(MediaFile, track.media_file_id)
    if media is None or media.is_missing:
        raise _error(404, "media_missing", "音频文件不存在")

    library = db.get(Library, book.library_id)
    if library is None:
        raise _error(404, "library_missing", "书库不存在")

    source = resolve_media_path(library.root_path, media.rel_path)
    if source is None:
        raise _error(404, "media_missing", "音频文件不存在")

    start, duration = _chapter_window(db, book, chapter, track)
    try:
        result = ensure_chapter_audio(
            settings,
            book_id=book.id,
            index=chapter.idx,
            source=source,
            source_format=media.format,
            mtime=media.mtime or 0,
            size=media.size_bytes or 0,
            start_sec=start,
            duration_sec=duration,
        )
    except ChapterAudioError as exc:
        status = 503 if exc.code in {"ffmpeg_missing", "transcode_disabled"} else 502
        raise _error(status, exc.code, exc.message) from exc

    return result.path, result.content_type, result.created, start, duration


def _disposition(book: Book, chapter: Chapter, suffix: str) -> str:
    raw = f"{book.title}-{chapter.idx + 1:04d}-{chapter.title}.{suffix}"
    safe = "".join(char if char.isalnum() or char in " ._-" else "_" for char in raw)
    ascii_name = f"chapter-{chapter.idx + 1:04d}.{suffix}"
    return (
        f'attachment; filename="{ascii_name}"; '
        f"filename*=UTF-8''{urllib.parse.quote(safe)}"
    )


@router.get("/books/{book_id}/chapters/{chapter_index}/audio")
def get_chapter_audio(
    book_id: int,
    chapter_index: int,
    download: bool = Query(
        False, description="true 时带 Content-Disposition，供客户端保存"
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    """取「第 N 集」的独立音频（章节序号从 0 开始，与 `ChapterOut.idx` 一致）。"""
    _ensure(settings)
    book, chapter = _load(db, current_user, book_id, chapter_index)
    path, content_type, created, _, _ = _slice(db, settings, book, chapter)

    headers = {
        "X-Chapter-Cache": "miss" if created else "hit",
        "Cache-Control": "private, max-age=86400",
    }
    if download:
        headers["Content-Disposition"] = _disposition(
            book, chapter, path.suffix.lstrip(".")
        )
    return FileResponse(path, media_type=content_type, headers=headers)


@router.post("/books/{book_id}/chapters/{chapter_index}/cache")
def cache_chapter(
    book_id: int,
    chapter_index: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ChapterAudioOut:
    """预生成切片；客户端批量下载前可先调它，避免播放线程等待。"""
    _ensure(settings)
    book, chapter = _load(db, current_user, book_id, chapter_index)
    path, content_type, created, start, duration = _slice(db, settings, book, chapter)
    return ChapterAudioOut(
        book_id=book.id,
        index=chapter.idx,
        title=chapter.title,
        cache_key=path.name,
        bytes=path.stat().st_size,
        content_type=content_type,
        start_sec=round(start, 3),
        duration_sec=round(duration, 3),
        created=created,
    )


@router.get("/books/{book_id}/chapters/cache", response_model=ChapterCacheList)
def list_chapter_cache(
    book_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ChapterCacheList:
    """列出该书已切好的章节，客户端据此跳过重复下载。"""
    book = require_visible_book(db, current_user, book_id)
    folder = settings.chapter_cache_dir / str(book.id)
    if not folder.is_dir():
        return ChapterCacheList(items=[], total_bytes=0)

    titles = {
        chapter.idx: chapter.title
        for chapter in db.scalars(select(Chapter).where(Chapter.book_id == book.id))
    }

    items: list[ChapterAudioOut] = []
    total = 0
    for path in sorted(folder.iterdir()):
        if not path.is_file() or path.name.startswith("."):
            continue
        head = path.name.split("-", 1)[0]
        if not head.isdigit():
            continue
        index = int(head)
        size = path.stat().st_size
        total += size
        items.append(
            ChapterAudioOut(
                book_id=book.id,
                index=index,
                title=titles.get(index),
                cache_key=path.name,
                bytes=size,
                content_type=content_type_for(path.suffix),
            )
        )
    return ChapterCacheList(items=items, total_bytes=total)


@router.delete("/books/{book_id}/chapters/cache", status_code=204)
def clear_cache(
    book_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    """清空某本书的切片缓存。"""
    book = require_visible_book(db, current_user, book_id)
    clear_book_cache(settings, book.id)
    return Response(status_code=204)
