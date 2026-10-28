"""M1-T04 验收：扫描聚合、幂等重扫、missing 标记与 CUE 分轨。"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

import pytest
from sqlalchemy import func, select, text

from app.db.base import now_ts
from app.db.session import get_session_factory
from app.models import Book, Chapter, Library, MediaFile, Track
from app.services.scanner import (
    _folder_series,
    _folder_title,
    _resolve_series,
    scan_library,
)

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_MP3 = FIXTURES / "sample.mp3"
SAMPLE_M4B = FIXTURES / "sample.m4b"
SAMPLE_FLAC = FIXTURES / "sample.flac"

requires_fixtures = pytest.mark.skipif(
    not all(path.exists() for path in (SAMPLE_MP3, SAMPLE_M4B, SAMPLE_FLAC)),
    reason="缺少样本，先运行 tests/fixtures/gen.sh",
)

CLEAN_TABLES = (
    "chapters",
    "tracks",
    "collection_books",
    "bookmarks",
    "progress",
    "media_files",
    "books",
    "scan_tasks",
    "library_users",
    "libraries",
)


@pytest.fixture(autouse=True)
def clean_tables(database):
    session = get_session_factory()()
    for table in CLEAN_TABLES:
        session.execute(text(f"DELETE FROM {table}"))
    session.commit()
    session.close()
    yield


@pytest.fixture()
def session(database):
    instance = get_session_factory()()
    yield instance
    instance.close()


def _count(session, model: type) -> int:
    return int(session.scalar(select(func.count()).select_from(model)) or 0)


def _make_library(session, root: Path) -> Library:
    library = Library(name="测试库", root_path=str(root), created_at=now_ts())
    session.add(library)
    session.commit()
    return library


def _build_tree(root: Path) -> None:
    long_dir = root / "作者甲" / "长篇"
    long_dir.mkdir(parents=True)
    for index in range(1, 13):
        shutil.copyfile(SAMPLE_MP3, long_dir / f"{index:03d}.mp3")

    short_dir = root / "作者乙" / "短篇集"
    short_dir.mkdir(parents=True)
    for index in range(1, 8):
        shutil.copyfile(SAMPLE_MP3, short_dir / f"{index:03d}.mp3")

    single_dir = root / "作者丙" / "单文件"
    single_dir.mkdir(parents=True)
    shutil.copyfile(SAMPLE_M4B, single_dir / "book.m4b")


@requires_fixtures
def test_each_m4b_in_one_dir_is_its_own_book(session, tmp_path: Path) -> None:
    """m4b 是「一整本」，同目录多卷不能被合并成多音轨。"""
    root = tmp_path / "library"
    series = root / "作者丁" / "间客"
    series.mkdir(parents=True)
    for name in ("间客 第一卷.m4b", "间客 第二卷.m4b", "间客 第三卷.m4b"):
        shutil.copyfile(SAMPLE_M4B, series / name)

    library = _make_library(session, root)
    stats = scan_library(session, library, min_size_bytes=0)

    assert stats.books_created == 3
    assert _count(session, Book) == 3
    assert _count(session, Track) == 3

    books = session.scalars(select(Book)).all()
    for book in books:
        assert book.rel_dir == "作者丁/间客"
        assert book.track_count == 1
        # 每个文件的内嵌章节各自保留，不跨文件拼接
        assert _count_chapters(session, book.id) == 2

    # 再扫一次仍然是 3 本，不会重复创建
    again = scan_library(session, library, min_size_bytes=0)
    assert again.books_created == 0
    assert _count(session, Book) == 3
    assert _count(session, Track) == 3


@requires_fixtures
def test_progress_beyond_duration_is_reset_on_rescan(session, tmp_path: Path) -> None:
    """拆卷后书变短，原本跨卷记录的绝对位置必须归零，否则进度条会越界。"""
    from app.models import Progress, User

    root = tmp_path / "library"
    folder = root / "作者戊" / "书"
    folder.mkdir(parents=True)
    shutil.copyfile(SAMPLE_M4B, folder / "a.m4b")
    shutil.copyfile(SAMPLE_M4B, folder / "b.m4b")
    library = _make_library(session, root)
    scan_library(session, library, min_size_bytes=0)

    book = session.scalar(select(Book).order_by(Book.id))
    assert book is not None
    user = User(
        username="proguser", password_hash="x", role="viewer", created_at=now_ts()
    )
    session.add(user)
    session.commit()
    session.add(
        Progress(
            user_id=user.id,
            book_id=book.id,
            position_sec=(book.total_duration_sec or 0) + 3600,
            updated_at=now_ts(),
        )
    )
    session.commit()

    scan_library(session, library, min_size_bytes=0)
    session.expire_all()
    progress = session.get(Progress, (user.id, book.id))
    assert progress is not None
    assert progress.position_sec == 0.0
    assert progress.is_finished is False


@requires_fixtures
def test_scan_aggregates_books_and_is_idempotent(session, tmp_path: Path) -> None:
    root = tmp_path / "library"
    _build_tree(root)
    library = _make_library(session, root)

    stats = scan_library(session, library, min_size_bytes=0)
    assert stats.books_created == 3
    assert stats.files_seen == 20

    assert _count(session, Book) == 3
    assert _count(session, Track) == 20
    assert _count(session, MediaFile) == 20

    long_book = session.scalar(select(Book).where(Book.rel_dir == "作者甲/长篇"))
    assert long_book is not None
    assert long_book.track_count == 12
    assert long_book.author == "刘慈欣"
    assert long_book.chapter_source == "track_split"
    assert _count_chapters(session, long_book.id) == 12

    single_book = session.scalar(select(Book).where(Book.rel_dir == "作者丙/单文件"))
    assert single_book is not None
    assert single_book.chapter_source == "embedded"
    assert single_book.track_count == 1
    assert _count_chapters(session, single_book.id) == 2

    again = scan_library(session, library, min_size_bytes=0)
    assert again.books_created == 0
    assert again.files_added == 0
    assert again.files_updated == 0
    assert _count(session, Book) == 3
    assert _count(session, Track) == 20
    assert _count(session, MediaFile) == 20


@requires_fixtures
def test_scan_marks_missing_without_deleting(session, tmp_path: Path) -> None:
    root = tmp_path / "library"
    _build_tree(root)
    library = _make_library(session, root)

    scan_library(session, library, min_size_bytes=0)
    (root / "作者甲" / "长篇" / "001.mp3").unlink()

    stats = scan_library(session, library, min_size_bytes=0)
    assert stats.files_removed == 1
    missing = session.scalar(
        select(func.count(MediaFile.id)).where(MediaFile.is_missing.is_(True))
    )
    assert missing == 1
    assert _count(session, Track) == 19


@requires_fixtures
def test_cue_book_becomes_one_book_two_tracks(session, tmp_path: Path) -> None:
    root = tmp_path / "cue-library"
    book_dir = root / "刘慈欣" / "三体"
    book_dir.mkdir(parents=True)
    shutil.copyfile(SAMPLE_FLAC, book_dir / "整轨.flac")
    cue_text = (
        'PERFORMER "刘慈欣"\n'
        'TITLE "三体"\n'
        'FILE "整轨.flac" WAVE\n'
        "  TRACK 01 AUDIO\n"
        '    TITLE "第一章"\n'
        "    INDEX 01 00:00:00\n"
        "  TRACK 02 AUDIO\n"
        '    TITLE "第二章"\n'
        "    INDEX 01 00:06:00\n"
    )
    (book_dir / "整轨.cue").write_bytes(cue_text.encode("gb18030"))
    library = _make_library(session, root)

    stats = scan_library(session, library, min_size_bytes=0)
    assert stats.books_created == 1

    book = session.scalar(select(Book))
    assert book is not None
    assert book.title == "三体"
    assert book.author == "刘慈欣"
    assert book.chapter_source == "cue"
    assert book.track_count == 2
    assert _count(session, MediaFile) == 1  # 一个物理文件只入库一次

    tracks = list(session.scalars(select(Track).order_by(Track.track_no)))
    assert [track.start_offset_sec for track in tracks] == [0.0, 6.0]
    chapters = list(session.scalars(select(Chapter).order_by(Chapter.idx)))
    assert [chapter.title for chapter in chapters] == ["第一章", "第二章"]
    assert chapters[1].start_sec == pytest.approx(6.0, abs=0.01)
    assert chapters[1].track_id == tracks[1].id


@requires_fixtures
def test_manual_override_survives_rescan(session, tmp_path: Path) -> None:
    root = tmp_path / "library"
    book_dir = root / "刘慈欣" / "三体"
    book_dir.mkdir(parents=True)
    audio = book_dir / "001.mp3"
    shutil.copyfile(SAMPLE_MP3, audio)
    library = _make_library(session, root)

    scan_library(session, library, min_size_bytes=0)
    book = session.scalar(select(Book))
    assert book is not None
    assert book.title == "三体"

    book.title = "手工书名"
    book.manual_override = True
    session.commit()

    # 改 mtime 触发重新解析，模拟文件变化后的重扫
    future = time.time() + 5
    os.utime(audio, (future, future))
    scan_library(session, library, min_size_bytes=0)

    session.refresh(book)
    assert book.title == "手工书名"


def _count_chapters(session, book_id: int) -> int:
    return int(
        session.scalar(select(func.count(Chapter.id)).where(Chapter.book_id == book_id))
        or 0
    )


# ---------------------------------------------------------------- 系列命名


def test_series_name_uses_parent_folder() -> None:
    """多文件书按父文件夹归组：`间客/Ⅰ第一卷 东林皆石/` → 系列「间客」第 1 卷。"""
    assert _resolve_series(
        None, None, "钟楼街的游行", "间客/Ⅰ第一卷 东林皆石", is_collection=True
    ) == ("间客", 1.0)
    assert _resolve_series(
        None, None, "湖畔一匹夫", "间客/Ⅱ第二卷 上林的钟声", is_collection=True
    ) == ("间客", 2.0)
    assert _resolve_series(
        None, None, "作训基地", "间客/Ⅲ第三卷 西林的征途", is_collection=True
    ) == ("间客", 3.0)
    assert _resolve_series(
        None, None, "几千万吨海水", "间客/Ⅳ第四卷 星光流年", is_collection=True
    ) == ("间客", 4.0)


def test_series_ignores_top_level_and_single_file() -> None:
    # 顶层单本目录没有父目录，不建只有一本的「系列」
    assert _resolve_series(
        None, None, "消失大陆的爱情1", "消失大陆的爱情", is_collection=True
    ) == (None, None)
    # 单文件书不按目录硬套，避免把「作者/书名」的作者目录变成系列
    assert _resolve_series(None, None, "三体", "刘慈欣/三体", is_collection=False) == (
        None,
        None,
    )
    # 标签里的系列优先
    assert _resolve_series("间客", 3, "随便", "间客/Ⅳ第四卷", is_collection=True) == (
        "间客",
        3,
    )
    assert _folder_series("间客") is None


def test_collection_title_uses_folder_name() -> None:
    """多文件书的书名取文件夹名：去掉文件序号，也跳过 CD1 这类分盘目录。"""
    assert _folder_title("消失大陆的爱情") == "消失大陆的爱情"
    assert _folder_title("间客/Ⅰ第一卷 东林皆石") == "Ⅰ第一卷 东林皆石"
    assert _folder_title("某书/CD1") == "某书"
    assert _folder_title("某书/Disc 2") == "某书"
    assert _folder_title("") is None
