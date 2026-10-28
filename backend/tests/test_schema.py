"""迁移与关键约束测试。

覆盖 M1-T02 验收点：alembic upgrade 建出全部表；幂等判重键 (library_id, rel_path) 唯一。
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.db.session import get_engine, get_session_factory
from app.models import Library, MediaFile

EXPECTED_TABLES = {
    "bookmarks",
    "books",
    "chapters",
    "collection_books",
    "collections",
    "devices",
    "libraries",
    "library_users",
    "media_files",
    "progress",
    "refresh_tokens",
    "scan_tasks",
    "settings",
    "tracks",
    "users",
}


def test_migration_creates_all_tables(database) -> None:
    inspector = inspect(get_engine())
    assert EXPECTED_TABLES <= set(inspector.get_table_names())
    assert "idx_progress_updated" in {
        index["name"] for index in inspector.get_indexes("progress")
    }


def test_media_rel_path_unique_within_library(database) -> None:
    session = get_session_factory()()
    try:
        lib_a = Library(name="书库A", root_path="/audiobooks/a")
        lib_b = Library(name="书库B", root_path="/audiobooks/b")
        session.add_all([lib_a, lib_b])
        session.flush()

        session.add(
            MediaFile(library_id=lib_a.id, rel_path="book/01.mp3", format="mp3")
        )
        session.commit()

        # 不同书库允许相同相对路径
        session.add(
            MediaFile(library_id=lib_b.id, rel_path="book/01.mp3", format="mp3")
        )
        session.commit()

        # 同一书库重复 rel_path 必须被唯一约束挡住（扫描幂等的基础）
        session.add(
            MediaFile(library_id=lib_a.id, rel_path="book/01.mp3", format="mp3")
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    finally:
        session.close()
