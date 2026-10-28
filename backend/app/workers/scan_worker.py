"""单写者扫描队列。

扫描永远串行（docs/ARCHITECTURE.md §3.1）：单线程消费队列，避免 SQLite 并发写锁冲突；
读请求走 WAL 不受影响。
"""

from __future__ import annotations

import logging
import queue
import threading

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import now_ts
from app.db.session import get_session_factory
from app.models import Library, ScanTask
from app.services.scanner import ScanError, scan_library

logger = logging.getLogger(__name__)

_STOP = object()


class ScanWorker:
    def __init__(self) -> None:
        self._queue: queue.Queue[object] = queue.Queue()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run, name="echoshelf-scan", daemon=True
        )
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        if self._thread is None:
            return
        self._queue.put(_STOP)
        self._thread.join(timeout=timeout)
        self._thread = None

    def submit(self, task_id: int) -> None:
        self._queue.put(task_id)

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            if item is _STOP:
                return
            try:
                self._process(int(item))  # type: ignore[arg-type]
            except Exception:  # noqa: BLE001 - 单任务异常不能终结工作线程
                logger.exception("扫描任务处理异常")
            finally:
                self._queue.task_done()

    def _process(self, task_id: int) -> None:
        settings = get_settings()
        session = get_session_factory()()
        try:
            task = session.get(ScanTask, task_id)
            if task is None:
                return
            library = session.get(Library, task.library_id)
            if library is None:
                self._finish_failed(session, task_id, "书库不存在")
                return

            task.status = "running"
            task.started_at = now_ts()
            session.commit()

            try:
                stats = scan_library(
                    session,
                    library,
                    virtual_chapter_min=settings.scan_virtual_chapter_min,
                    min_size_bytes=settings.scan_min_size_bytes,
                )
            except ScanError as exc:
                session.rollback()
                self._finish_failed(session, task_id, str(exc))
                return
            except Exception as exc:  # noqa: BLE001
                session.rollback()
                logger.exception(
                    "扫描失败", extra={"extra_fields": {"task_id": task_id}}
                )
                self._finish_failed(session, task_id, f"扫描失败: {exc}")
                return

            task = session.get(ScanTask, task_id)
            if task is None:
                return
            task.status = "success"
            task.finished_at = now_ts()
            task.files_seen = stats.files_seen
            task.files_added = stats.files_added
            task.files_updated = stats.files_updated
            task.files_removed = stats.files_removed
            task.books_created = stats.books_created
            task.books_updated = stats.books_updated
            library.last_scan_at = now_ts()
            session.commit()
        finally:
            session.close()

    @staticmethod
    def _finish_failed(session: Session, task_id: int, message: str) -> None:
        task = session.get(ScanTask, task_id)
        if task is None:
            return
        task.status = "failed"
        task.error = message[:2000]
        task.finished_at = now_ts()
        session.commit()
