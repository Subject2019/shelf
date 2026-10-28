"""ORM 模型汇总。导入本模块即完成全部表的 metadata 注册（Alembic 依赖此行为）。"""

from __future__ import annotations

from app.models.book import Book, Chapter, Track
from app.models.collection import Collection, CollectionBook
from app.models.library import Library, LibraryUser
from app.models.media import MediaFile
from app.models.progress import Bookmark, Progress, ProgressHistory
from app.models.scan import ScanTask
from app.models.setting import Setting
from app.models.stats import ListeningDaily
from app.models.user import Device, RefreshToken, User

__all__ = [
    "Book",
    "Bookmark",
    "Chapter",
    "Collection",
    "CollectionBook",
    "Device",
    "Library",
    "LibraryUser",
    "ListeningDaily",
    "MediaFile",
    "Progress",
    "ProgressHistory",
    "RefreshToken",
    "ScanTask",
    "Setting",
    "Track",
    "User",
]
