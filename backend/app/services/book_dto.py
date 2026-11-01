"""书籍 DTO 组装：书架、书单等接口共用，避免重复拼字段。"""

from __future__ import annotations

from app.models import Book, Progress
from app.schemas.book import BookOut, ProgressBrief


def progress_brief(book: Book, progress: Progress | None) -> ProgressBrief | None:
    if progress is None:
        return None
    percent = (
        0.0
        if book.total_duration_sec <= 0
        else min(100.0, progress.position_sec / book.total_duration_sec * 100)
    )
    return ProgressBrief(
        position_sec=progress.position_sec,
        percent=round(percent, 2),
        is_finished=progress.is_finished,
    )


def book_out(book: Book, progress: Progress | None) -> BookOut:
    return BookOut(
        id=book.id,
        library_id=book.library_id,
        title=book.title,
        author=book.author,
        narrator=book.narrator,
        series_name=book.series_name,
        series_index=book.series_index,
        language=book.language,
        cover_url=(
            f"/api/v1/books/{book.id}/cover?size=thumb" if book.cover_path else None
        ),
        manual_override=book.manual_override,
        cover_uploaded_by=book.cover_uploaded_by,
        hidden=book.hidden,
        total_duration_sec=book.total_duration_sec,
        intro_sec=book.intro_sec or 0.0,
        outro_sec=book.outro_sec or 0.0,
        track_count=book.track_count,
        size_bytes=book.size_bytes,
        chapter_source=book.chapter_source,
        added_at=book.added_at,
        progress=progress_brief(book, progress),
    )
