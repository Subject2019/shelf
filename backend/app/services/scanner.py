"""媒体扫描：遍历目录 → 聚合成书 → 幂等写入 books/tracks/chapters/media_files。

设计见 docs/ARCHITECTURE.md §3.1。幂等键 `(library_id, rel_path)` + `mtime` + `size`：
- 未变化文件复用库中已存的时长/章节，不再调用 ffprobe
- 消失的文件标 `is_missing`，不删记录，保留用户进度
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections import defaultdict
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import now_ts
from app.models import Book, Chapter, Library, MediaFile, Progress, Track
from app.services.covers import extract_from_media, save_cover
from app.services.cue import CueParseError, cue_to_chapters, parse_cue
from app.services.metadata import (
    EMBEDDED,
    TRACK_SPLIT,
    AudioMetadata,
    ChapterInfo,
    UnsupportedAudioError,
    build_virtual_chapters,
    read_audio_metadata,
)

logger = logging.getLogger(__name__)

AUDIO_EXTENSIONS = {
    ".mp3",
    ".mp3pro",
    ".m4a",
    ".m4b",
    ".aac",
    ".flac",
    ".ogg",
    ".oga",
    ".opus",
    ".wav",
    ".wma",
    ".ape",
    ".dsf",
    ".dff",
    ".aiff",
    ".aif",
    ".mka",
    ".webm",
}
IGNORED_DIR_NAMES = {
    "@eaDir",
    "#recycle",
    ".@__thumb",
    "$RECYCLE.BIN",
    "System Volume Information",
}
IGNORED_SUFFIXES = (".part", ".tmp", ".crdownload", ".!qb")
MIN_SIZE_BYTES = 100 * 1024
MAX_DEPTH = 12


class ScanError(Exception):
    """书库根目录不可用等致命错误。"""


@dataclass(slots=True)
class ScanStats:
    files_seen: int = 0
    files_added: int = 0
    files_updated: int = 0
    files_removed: int = 0
    books_created: int = 0
    books_updated: int = 0


@dataclass(slots=True)
class MediaData:
    path: Path
    rel_path: str
    mtime: int
    size_bytes: int
    inode: int
    meta: AudioMetadata
    record: MediaFile | None
    changed: bool


@dataclass(slots=True)
class TrackData:
    media_rel_path: str
    track_no: int
    title: str | None
    start_offset_sec: float
    duration_sec: float
    size_bytes: int | None


@dataclass(slots=True)
class ParsedBook:
    rel_dir: str
    title: str
    author: str | None
    narrator: str | None
    publisher: str | None
    publish_year: int | None
    language: str | None
    description: str | None
    series_name: str | None
    series_index: float | None
    media: list[MediaData]
    tracks: list[TrackData]
    chapters: list[ChapterInfo]
    # 非 cue 目录内只可能有一本书，按 rel_dir 匹配；cue 目录可能多本，按标题区分
    kind: str
    # 复用 media 记录时没有标签缓存，此时不能用回退标题覆盖已有书籍信息
    tags_authoritative: bool
    changed: bool

    @property
    def total_duration_sec(self) -> float:
        return sum(track.duration_sec for track in self.tracks)

    @property
    def size_bytes(self) -> int:
        return sum(media.size_bytes for media in self.media)

    @property
    def chapter_source(self) -> str | None:
        return self.chapters[0].source if self.chapters else None


def iter_audio_files(
    root: Path, *, min_size_bytes: int = MIN_SIZE_BYTES
) -> Iterator[Path]:
    root = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        depth = len(current.relative_to(root).parts)
        dirnames[:] = sorted(
            name
            for name in dirnames
            if not name.startswith(".") and name not in IGNORED_DIR_NAMES
        )
        if depth >= MAX_DEPTH:
            dirnames[:] = []
        for filename in sorted(filenames):
            lowered = filename.lower()
            if filename.startswith(".") or lowered.endswith(IGNORED_SUFFIXES):
                continue
            path = current / filename
            if path.suffix.lower() not in AUDIO_EXTENSIONS:
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            if not path.is_file() or stat.st_size < min_size_bytes:
                continue
            yield path


def scan_library(
    session: Session,
    library: Library,
    *,
    virtual_chapter_min: int = 15,
    min_size_bytes: int = MIN_SIZE_BYTES,
) -> ScanStats:
    root = Path(library.root_path)
    if not root.is_dir():
        raise ScanError(f"书库路径不存在或不可读: {root}")
    root = root.resolve()

    stats = ScanStats()
    cache = {
        record.rel_path: record
        for record in session.scalars(
            select(MediaFile).where(MediaFile.library_id == library.id)
        )
    }
    seen_media: set[str] = set()
    seen_books: set[tuple[str, str]] = set()
    claimed: set[int] = set()
    now = now_ts()

    by_dir: dict[str, list[Path]] = defaultdict(list)
    for path in iter_audio_files(root, min_size_bytes=min_size_bytes):
        by_dir[_rel_path(root, path.parent)].append(path)

    for rel_dir in sorted(by_dir):
        paths = sorted(by_dir[rel_dir], key=lambda item: _natural_key(item.name))
        cue_files = _cue_files(root / rel_dir if rel_dir else root)
        if cue_files:
            for cue_path in cue_files:
                parsed = _build_cue_book(
                    root, rel_dir, cue_path, cache, stats, seen_media
                )
                if parsed is not None:
                    book = _persist_book(session, library, parsed, stats, now, claimed)
                    claimed.add(book.id)
                    seen_books.add((book.rel_dir, book.title))
        else:
            media = _collect_media_book(root, rel_dir, paths, cache, stats, seen_media)
            # 同一目录可能放多本书（如 m4b 分卷），按文件类型拆开
            for group in _group_media(media):
                parsed = _build_media_book(rel_dir, group, virtual_chapter_min)
                if parsed is not None:
                    book = _persist_book(session, library, parsed, stats, now, claimed)
                    claimed.add(book.id)
                    seen_books.add((book.rel_dir, book.title))

    for rel_path, record in cache.items():
        if rel_path not in seen_media and not record.is_missing:
            record.is_missing = True
            stats.files_removed += 1

    for book in session.scalars(select(Book).where(Book.library_id == library.id)):
        if (book.rel_dir, book.title) not in seen_books and not book.is_missing:
            book.is_missing = True

    session.commit()
    logger.info(
        "扫描完成",
        extra={
            "extra_fields": {
                "library_id": library.id,
                "files_seen": stats.files_seen,
                "files_added": stats.files_added,
                "files_updated": stats.files_updated,
                "files_removed": stats.files_removed,
                "books_created": stats.books_created,
                "books_updated": stats.books_updated,
            }
        },
    )
    return stats


# ---------------- 书构建 ----------------


def _build_cue_book(
    root: Path,
    rel_dir: str,
    cue_path: Path,
    cache: dict[str, MediaFile],
    stats: ScanStats,
    seen_media: set[str],
) -> ParsedBook | None:
    try:
        sheet = parse_cue(cue_path)
    except (OSError, CueParseError) as exc:
        logger.warning(
            "CUE 解析失败，跳过",
            extra={"extra_fields": {"cue": str(cue_path), "error": str(exc)}},
        )
        return None

    directory = cue_path.parent
    media_by_name: dict[str, MediaData] = {}
    for cue_file in sheet.files:
        audio_path = (directory / cue_file.name).resolve()
        try:
            audio_path.relative_to(root)
        except ValueError:
            logger.warning("CUE 引用了书库外的文件，跳过该 FILE")
            continue
        if not audio_path.is_file():
            logger.warning(
                "CUE 引用的文件不存在，跳过该 FILE",
                extra={"extra_fields": {"file": str(audio_path)}},
            )
            continue
        media = _collect_media(
            cache, audio_path, _rel_path(root, audio_path), stats, seen_media
        )
        if media is not None:
            media_by_name[cue_file.name] = media

    if not media_by_name:
        return None

    durations = {
        name: (media.meta.duration_sec or 0.0) for name, media in media_by_name.items()
    }
    tracks: list[TrackData] = []
    track_no = 0
    for cue_file in sheet.files:
        media = media_by_name.get(cue_file.name)
        if media is None:
            continue
        file_duration = media.meta.duration_sec or 0.0
        for index, cue_track in enumerate(cue_file.tracks):
            offset = cue_track.offset_sec or 0.0
            if index + 1 < len(cue_file.tracks):
                next_offset = cue_file.tracks[index + 1].offset_sec
                end = next_offset if next_offset is not None else file_duration
            else:
                end = file_duration
            track_no += 1
            tracks.append(
                TrackData(
                    media_rel_path=media.rel_path,
                    track_no=track_no,
                    title=cue_track.title,
                    start_offset_sec=offset,
                    duration_sec=max(0.0, end - offset),
                    size_bytes=media.size_bytes,
                )
            )

    if not tracks:
        return None

    chapters = cue_to_chapters(sheet, durations)
    return ParsedBook(
        rel_dir=rel_dir,
        title=sheet.title or cue_path.stem,
        author=sheet.performer or _parent_author(rel_dir),
        narrator=None,
        publisher=None,
        publish_year=None,
        language=None,
        description=None,
        series_name=None,
        series_index=None,
        media=list(media_by_name.values()),
        tracks=tracks,
        chapters=chapters,
        kind="cue",
        tags_authoritative=True,
        changed=any(media.changed for media in media_by_name.values()),
    )


def _collect_media_book(
    root: Path,
    rel_dir: str,
    paths: list[Path],
    cache: dict[str, MediaFile],
    stats: ScanStats,
    seen_media: set[str],
) -> list[MediaData]:
    media: list[MediaData] = []
    for path in paths:
        item = _collect_media(cache, path, _rel_path(root, path), stats, seen_media)
        if item is not None:
            media.append(item)
    return media


# 单文件即一本有声书的容器；m4a/mp4 要带内嵌章节才算（否则可能是分章导出的一套）
STANDALONE_SUFFIXES = {".m4b"}
CHAPTERED_SUFFIXES = {".m4a", ".mp4"}


def _group_media(media: list[MediaData]) -> list[list[MediaData]]:
    """决定同一目录下哪些文件各自成书、哪些聚合为一本。

    - `m4b`：格式本身就代表「一整本有声书」，一个文件一本书
    - `m4a` / `mp4`：内嵌章节的各自成书，否则按「一章一文件」参与聚合
    - 其余（mp3 / flac / ogg / wav…）：同目录聚合为一本，文件即音轨
    """
    books: list[list[MediaData]] = []
    rest: list[MediaData] = []
    for item in media:
        suffix = item.path.suffix.lower()
        if suffix in STANDALONE_SUFFIXES or (
            suffix in CHAPTERED_SUFFIXES and item.meta.chapters
        ):
            books.append([item])
        else:
            rest.append(item)
    if rest:
        books.append(rest)
    return books


def _build_media_book(
    rel_dir: str,
    media: list[MediaData],
    virtual_chapter_min: int,
) -> ParsedBook | None:
    if not media:
        return None

    first = media[0]
    tracks: list[TrackData] = []
    for index, item in enumerate(media, start=1):
        tracks.append(
            TrackData(
                media_rel_path=item.rel_path,
                track_no=index,
                title=item.meta.title or _fallback_title(item.path, rel_dir),
                start_offset_sec=0.0,
                duration_sec=item.meta.duration_sec or 0.0,
                size_bytes=item.size_bytes,
            )
        )

    title = first.meta.title or _fallback_title(first.path, rel_dir)
    # 多文件书（一个文件夹 = 一本书）用文件夹名做书名：
    # 标签里的 title 往往是章节名，文件名还可能带序号（如 消失大陆的爱情1.mp3）
    if len(media) > 1:
        title = _folder_title(rel_dir) or title
    series_name, series_index = _resolve_series(
        first.meta.series,
        first.meta.series_index,
        title,
        rel_dir,
        is_collection=len(media) > 1,
    )

    return ParsedBook(
        rel_dir=rel_dir,
        title=title,
        author=(
            first.meta.author or first.meta.album_artist or _parent_author(rel_dir)
        ),
        narrator=first.meta.narrator,
        publisher=first.meta.publisher,
        publish_year=first.meta.year,
        language=first.meta.language,
        description=first.meta.description,
        series_name=series_name,
        series_index=series_index,
        media=media,
        tracks=tracks,
        chapters=_chapters_for_media(media, tracks, virtual_chapter_min),
        kind="media",
        # 多文件书的标题来自文件夹，即使没有标签也算权威（否则老库重扫不更新）
        tags_authoritative=bool(first.meta.title or first.meta.author)
        or len(media) > 1,
        changed=any(item.changed for item in media),
    )


def _chapters_for_media(
    media: list[MediaData], tracks: list[TrackData], virtual_chapter_min: int
) -> list[ChapterInfo]:
    if len(media) == 1:
        if media[0].meta.chapters:
            return list(media[0].meta.chapters)
        return build_virtual_chapters(media[0].meta.duration_sec, virtual_chapter_min)

    # 多文件：仅当每个文件都有内嵌章节时合并为 embedded，否则按「一文件一章」
    if all(item.meta.chapters for item in media):
        merged: list[ChapterInfo] = []
        cursor = 0.0
        for item in media:
            for chapter in item.meta.chapters:
                end = chapter.end_sec + cursor if chapter.end_sec is not None else None
                merged.append(
                    ChapterInfo(
                        title=chapter.title,
                        start_sec=chapter.start_sec + cursor,
                        end_sec=end,
                        source=EMBEDDED,
                    )
                )
            cursor += item.meta.duration_sec or 0.0
        return merged

    chapters: list[ChapterInfo] = []
    cursor = 0.0
    for track in tracks:
        chapters.append(
            ChapterInfo(
                title=track.title or f"第 {track.track_no} 章",
                start_sec=cursor,
                end_sec=cursor + track.duration_sec,
                source=TRACK_SPLIT,
            )
        )
        cursor += track.duration_sec
    return chapters


def _collect_media(
    cache: dict[str, MediaFile],
    path: Path,
    rel_path: str,
    stats: ScanStats,
    seen_media: set[str],
) -> MediaData | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    mtime = int(stat.st_mtime)
    size_bytes = stat.st_size
    existing = cache.get(rel_path)
    first_time_seen = rel_path not in seen_media
    if first_time_seen:
        stats.files_seen += 1
        seen_media.add(rel_path)

    if (
        existing is not None
        and not existing.is_missing
        and existing.mtime == mtime
        and existing.size_bytes == size_bytes
    ):
        return MediaData(
            path=path,
            rel_path=rel_path,
            mtime=mtime,
            size_bytes=size_bytes,
            inode=int(stat.st_ino),
            meta=_meta_from_record(existing),
            record=existing,
            changed=False,
        )

    try:
        meta = read_audio_metadata(path)
    except UnsupportedAudioError:
        logger.warning(
            "无法识别的音频文件，跳过", extra={"extra_fields": {"path": str(path)}}
        )
        return None

    if first_time_seen:
        if existing is None:
            stats.files_added += 1
        else:
            stats.files_updated += 1

    return MediaData(
        path=path,
        rel_path=rel_path,
        mtime=mtime,
        size_bytes=size_bytes,
        inode=int(stat.st_ino),
        meta=meta,
        record=existing,
        changed=True,
    )


def _meta_from_record(record: MediaFile) -> AudioMetadata:
    chapters: list[ChapterInfo] = []
    if record.embedded_chapters_json:
        try:
            for item in json.loads(record.embedded_chapters_json):
                end = item.get("end_sec")
                chapters.append(
                    ChapterInfo(
                        title=str(item.get("title") or ""),
                        start_sec=float(item["start_sec"]),
                        end_sec=float(end) if end is not None else None,
                        source=EMBEDDED,
                    )
                )
        except (KeyError, TypeError, ValueError):
            chapters = []
    return AudioMetadata(
        duration_sec=record.duration_sec,
        format=record.format,
        codec=record.codec,
        bitrate=record.bitrate,
        sample_rate=record.sample_rate,
        channels=record.channels,
        chapters=chapters,
        chapter_source=EMBEDDED if chapters else None,
    )


# ---------------- 写库 ----------------


def _persist_book(
    session: Session,
    library: Library,
    parsed: ParsedBook,
    stats: ScanStats,
    now: int,
    claimed: set[int],
) -> Book:
    media_records = {
        media.rel_path: _upsert_media(session, library.id, media, now)
        for media in parsed.media
    }
    session.flush()

    book = _find_existing_book(session, library, parsed, media_records, claimed)
    created = book is None
    media_changed = False
    if created:
        book = Book(
            library_id=library.id,
            rel_dir=parsed.rel_dir,
            title=parsed.title,
            added_at=now,
        )
        session.add(book)
        session.flush()
        stats.books_created += 1
    else:
        # 文件被删除时剩余文件都没变化，必须比较轨与媒体集合才知道要重建
        media_changed = parsed.changed or _track_media_changed(
            session, book, media_records
        )
        if media_changed:
            stats.books_updated += 1

    # 手工改过元数据的书，后续扫描不再覆盖书名/作者等字段
    if (created or parsed.tags_authoritative) and not book.manual_override:
        book.title = parsed.title or book.title
        book.author = parsed.author or book.author
        book.narrator = parsed.narrator or book.narrator
        book.publisher = parsed.publisher or book.publisher
        book.publish_year = parsed.publish_year or book.publish_year
        book.language = parsed.language or book.language
        book.description = parsed.description or book.description
        book.series_name = parsed.series_name or book.series_name
        book.series_index = (
            parsed.series_index
            if parsed.series_index is not None
            else book.series_index
        )

    # 文件名推断出的系列/卷号，即使标签缓存不可用也补上；已有值不覆盖
    if not book.manual_override and book.series_name is None and parsed.series_name:
        book.series_name = parsed.series_name
        book.series_index = parsed.series_index

    book.total_duration_sec = parsed.total_duration_sec
    book.track_count = len(parsed.tracks)
    book.size_bytes = parsed.size_bytes
    book.chapter_source = parsed.chapter_source
    book.is_missing = False
    book.updated_at = now

    # 拆卷 / 换文件后书会变短，旧进度可能越界（如整卷合并时记下的绝对位置），归零重来
    if book.total_duration_sec > 0:
        session.execute(
            update(Progress)
            .where(
                Progress.book_id == book.id,
                Progress.position_sec > book.total_duration_sec,
            )
            .values(position_sec=0.0, track_position_sec=None, is_finished=False)
        )

    if created or media_changed:
        _rebuild_tracks(session, book, parsed, media_records, now)

    # 没有封面时才抽取，手工上传过的不会被扫描覆盖
    if book.cover_path is None and parsed.tracks:
        _attach_cover(book, parsed, library)

    session.commit()
    return book


def _attach_cover(book: Book, parsed: ParsedBook, library: Library) -> None:
    """抽取内嵌/同目录封面；任何失败都只记日志，不影响扫描。"""
    try:
        media_path = Path(library.root_path) / parsed.tracks[0].media_rel_path
        data = extract_from_media(media_path)
        if not data:
            return
        book.cover_path = save_cover(book.id, data, get_settings().covers_dir)
    except Exception:  # noqa: BLE001
        logger.warning("封面抽取失败 book=%s", book.id, exc_info=True)


def _find_existing_book(
    session: Session,
    library: Library,
    parsed: ParsedBook,
    media_records: Mapping[str, MediaFile],
    claimed: set[int],
) -> Book | None:
    """同一目录可能有多本书，先按「这些媒体文件已经属于哪本书」判断。

    兜底再用 (rel_dir, title)：覆盖媒体文件被替换/改名、但书名没变的情况。
    `claimed` 记录本次扫描已经认领过的书，避免同目录多本同名文件被并到同一本。
    """
    # CUE 多本共用同一个物理文件，按归属判断会串，只用标题匹配
    if parsed.kind != "cue":
        media_ids = [
            media_records[track.media_rel_path].id
            for track in parsed.tracks
            if track.media_rel_path in media_records
        ]
        if media_ids:
            owner_id = session.scalar(
                select(Track.book_id).where(Track.media_file_id.in_(media_ids)).limit(1)
            )
            if owner_id is not None and owner_id not in claimed:
                return session.get(Book, owner_id)

    return session.scalar(
        select(Book).where(
            Book.library_id == library.id,
            Book.rel_dir == parsed.rel_dir,
            Book.title == parsed.title,
            Book.id.notin_(claimed) if claimed else True,
        )
    )


def _track_media_changed(
    session: Session, book: Book, media_records: Mapping[str, MediaFile]
) -> bool:
    current = set(
        session.scalars(select(Track.media_file_id).where(Track.book_id == book.id))
    )
    expected = {record.id for record in media_records.values()}
    return current != expected


def _upsert_media(
    session: Session, library_id: int, media: MediaData, now: int
) -> MediaFile:
    record = media.record
    if record is None:
        record = MediaFile(
            library_id=library_id,
            rel_path=media.rel_path,
            format=media.meta.format or "unknown",
            first_seen_at=now,
        )
        session.add(record)

    if media.changed:
        meta = media.meta
        record.format = meta.format or record.format or "unknown"
        record.codec = meta.codec
        record.bitrate = meta.bitrate
        record.sample_rate = meta.sample_rate
        record.channels = meta.channels
        record.duration_sec = meta.duration_sec
        record.has_embedded_chapters = bool(meta.chapters)
        record.embedded_chapters_json = (
            _chapters_to_json(meta.chapters) if meta.chapters else None
        )

    record.size_bytes = media.size_bytes
    record.mtime = media.mtime
    record.inode = media.inode
    record.is_missing = False
    record.last_seen_at = now
    return record


def _rebuild_tracks(
    session: Session,
    book: Book,
    parsed: ParsedBook,
    media_records: Mapping[str, MediaFile],
    now: int,
) -> None:
    session.execute(delete(Chapter).where(Chapter.book_id == book.id))
    session.execute(delete(Track).where(Track.book_id == book.id))
    session.flush()

    tracks: list[Track] = []
    for data in parsed.tracks:
        media = media_records[data.media_rel_path]
        track = Track(
            book_id=book.id,
            media_file_id=media.id,
            disc_no=1,
            track_no=data.track_no,
            title=data.title,
            start_offset_sec=data.start_offset_sec,
            duration_sec=data.duration_sec,
            size_bytes=data.size_bytes,
        )
        session.add(track)
        tracks.append(track)
    session.flush()

    for idx, chapter in enumerate(parsed.chapters):
        track = _track_at(tracks, chapter.start_sec)
        session.add(
            Chapter(
                book_id=book.id,
                track_id=track.id,
                idx=idx,
                title=chapter.title or f"第 {idx + 1} 章",
                start_sec=chapter.start_sec,
                end_sec=chapter.end_sec,
                source=chapter.source,
            )
        )
    session.flush()


def _track_at(tracks: list[Track], position_sec: float) -> Track:
    cursor = 0.0
    for index, track in enumerate(tracks):
        cursor += track.duration_sec
        if position_sec < cursor or index == len(tracks) - 1:
            return track
    return tracks[-1]


def _chapters_to_json(chapters: list[ChapterInfo]) -> str:
    return json.dumps(
        [
            {
                "title": chapter.title,
                "start_sec": chapter.start_sec,
                "end_sec": chapter.end_sec,
            }
            for chapter in chapters
        ],
        ensure_ascii=False,
    )


# ---------------- 路径与命名工具 ----------------


def _rel_path(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root).as_posix()


def _cue_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(
        item
        for item in directory.iterdir()
        if item.is_file() and item.suffix.lower() == ".cue"
    )


_CN_DIGITS = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
_CN_UNITS = {"十": 10, "百": 100, "千": 1000}

# 「间客 第二卷 上林的钟声」「三体·第 2 部 黑暗森林」
_SERIES_PATTERN = re.compile(
    r"(?P<name>.*?)"
    r"[\s·・\-—_]*"
    r"第\s*(?P<num>\d+|[零〇一二三四五六七八九十百千两]+)\s*"
    r"(?P<unit>[卷部册集季])"
)


def _parse_number(text: str) -> float | None:
    """把 `12`、`十二`、`二十一` 这类写法转成数字。"""
    text = text.strip()
    if not text:
        return None
    if text.isdigit():
        return float(text)

    total = 0
    current = 0
    for char in text:
        if char in _CN_DIGITS:
            current = _CN_DIGITS[char]
        elif char in _CN_UNITS:
            total += (current or 1) * _CN_UNITS[char]
            current = 0
        else:
            return None
    return float(total + current)


_ROMAN_INDEX = {
    "Ⅰ": 1,
    "Ⅱ": 2,
    "Ⅲ": 3,
    "Ⅳ": 4,
    "Ⅴ": 5,
    "Ⅵ": 6,
    "Ⅶ": 7,
    "Ⅷ": 8,
    "Ⅸ": 9,
    "Ⅹ": 10,
    "Ⅺ": 11,
    "Ⅻ": 12,
}
_LEADING_DIGITS = re.compile(r"^\s*(\d+)")


def _folder_index(name: str) -> float | None:
    """从卷目录名取卷号：第N卷 / Ⅰ / 01 前缀。"""
    match = _SERIES_PATTERN.search(name)
    if match:
        return _parse_number(match.group("num"))
    stripped = name.strip()
    if stripped[:1] in _ROMAN_INDEX:
        return float(_ROMAN_INDEX[stripped[:1]])
    digits = _LEADING_DIGITS.match(name)
    if digits:
        return float(int(digits.group(1)))
    return None


def _folder_series(rel_dir: str) -> tuple[str, float | None] | None:
    """多文件「按文件夹归组」的书：上一级目录名即系列名。

    例：`间客/Ⅰ第一卷 东林皆石/` → ("间客", 1)；顶层单本目录（`消失大陆的爱情/`）没有父目录，不建系列。
    """
    parts = [part for part in rel_dir.split("/") if part]
    if len(parts) < 2:
        return None
    return parts[-2], _folder_index(parts[-1])


def _resolve_series(
    tag_series: str | None,
    tag_index: float | None,
    title: str,
    rel_dir: str,
    *,
    is_collection: bool = False,
) -> tuple[str | None, float | None]:
    """系列名：标签 > 多文件文件夹 > 书名里的「第N卷」。

    用户约定：按文件夹归纳的多 MP3 书，系列名必须用**父文件夹名**，
    这样同一部书的不同卷会落在同一个系列里。
    """
    if tag_series:
        return tag_series, tag_index

    if is_collection:
        folder = _folder_series(rel_dir)
        if folder is not None:
            return folder

    match = _SERIES_PATTERN.search(title)
    if not match:
        return None, None

    index = _parse_number(match.group("num"))
    if index is None or not 0 < index < 1000:
        return None, None

    name = match.group("name").strip(" ·・-—_")
    if not name:
        # 书名只剩「第二卷 xxx」时退回目录名（作者/书名/ 里的书名）
        parts = [part for part in rel_dir.split("/") if part]
        name = parts[-1] if parts else ""
    if not name:
        return None, None

    return name, index


_DISC_DIR = re.compile(r"^(?:cd|disc|disk|dvd|vol(?:ume)?)[\s._-]*\d+$", re.IGNORECASE)


def _folder_title(rel_dir: str) -> str | None:
    """多文件书的书名：所在文件夹名。

    跳过 `CD1` / `Disc2` 这类分盘目录，取上一级（否则一本书会被叫成 CD1）。
    """
    parts = [part for part in rel_dir.split("/") if part]
    if not parts:
        return None
    leaf = parts[-1].strip()
    if len(parts) >= 2 and _DISC_DIR.match(leaf):
        return parts[-2]
    return leaf


def _parent_author(rel_dir: str) -> str | None:
    parts = [part for part in rel_dir.split("/") if part]
    return parts[-2] if len(parts) >= 2 else None


_NUMBER_PREFIX = re.compile(r"^[\s\[\(（【]*\d+[\s._\-、\]\)）】]*")


def _fallback_title(path: Path, rel_dir: str) -> str:
    cleaned = _NUMBER_PREFIX.sub("", path.stem).strip()
    if cleaned:
        return cleaned
    parts = [part for part in rel_dir.split("/") if part]
    return parts[-1] if parts else path.stem


def _natural_key(text: str) -> list[tuple[int, object]]:
    return [
        (0, int(part)) if part.isdigit() else (1, part.lower())
        for part in re.split(r"(\d+)", text)
        if part
    ]
