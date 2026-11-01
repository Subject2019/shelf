"""书籍查询接口：列表（搜索/筛选/排序/分页）、详情、章节分页、封面。"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Literal

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from sqlalchemy import and_, false, func, or_, select, text as sql_text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_stream_token, get_current_user
from app.db.base import now_ts
from app.db.session import get_db
from app.models import Book, Chapter, MediaFile, Progress, Track, User
from app.services.book_dto import book_out
from app.services.search import search_plan
from app.services.covers import (
    MAX_UPLOAD_BYTES,
    CoverError,
    remove_cover,
    save_cover,
)
from app.schemas.book import (
    AuthorList,
    AuthorOut,
    BookDetail,
    BookList,
    BookOut,
    BookUpdate,
    ChapterList,
    ChapterOut,
    PlayTokenOut,
    SeriesList,
    SeriesOut,
    TrackOut,
)
from app.services.permissions import (
    is_admin,
    can_delete_cover,
    require_editor,
    require_visible_book,
    visible_library_ids,
)

router = APIRouter(tags=["books"])

EMBED_CHAPTER_LIMIT = 500
CACHE_CONTROL = "public, max-age=86400"

_PLACEHOLDER_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400" '
    b'viewBox="0 0 400 400"><rect width="400" height="400" fill="#1f2937"/>'
    b'<rect x="110" y="140" width="180" height="150" rx="14" fill="#374151"/>'
    b'<path d="M134 176h132M134 210h132M134 244h96" stroke="#9ca3af" '
    b'stroke-width="10" stroke-linecap="round"/>'
    b'<text x="200" y="340" font-family="sans-serif" font-size="24" '
    b'fill="#6b7280" text-anchor="middle">EchoShelf</text></svg>'
)
_PLACEHOLDER_ETAG = '"echoshelf-placeholder-v1"'

_IMAGE_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def _progress_join(user_id: int):
    return and_(Progress.book_id == Book.id, Progress.user_id == user_id)


def _order_by(sort: str):
    if sort == "title_asc":
        return (Book.title.asc(), Book.id.asc())
    if sort == "author_asc":
        return (Book.author.is_(None), Book.author.asc(), Book.title.asc())
    if sort == "duration_desc":
        return (Book.total_duration_sec.desc(), Book.id.asc())
    if sort == "series_asc":
        # 系列视图：卷号小的在前，没有卷号的排最后
        return (Book.series_index.is_(None), Book.series_index.asc(), Book.title.asc())
    if sort == "progress_desc":
        return (
            Progress.updated_at.is_(None),
            Progress.updated_at.desc(),
            Book.added_at.desc(),
        )
    return (Book.added_at.desc(), Book.id.desc())


@router.get("/series", response_model=SeriesList)
def list_series(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SeriesList:
    """按 `series_name` 汇总，供书架的「系列」视图使用。"""
    visible = visible_library_ids(db, current_user)
    if not visible:
        return SeriesList(items=[])

    base = (
        Book.is_missing.is_(False),
        Book.hidden.is_(False),
        Book.library_id.in_(visible),
        Book.series_name.is_not(None),
        Book.series_name != "",
    )
    rows = db.execute(
        select(
            Book.series_name,
            func.count(Book.id),
            func.sum(Book.total_duration_sec),
            func.max(Book.added_at),
        )
        .where(*base)
        .group_by(Book.series_name)
        .order_by(func.max(Book.added_at).desc())
    ).all()

    # 卷号最小的一本当封面（series_index 为空的排最后）
    covers: dict[str, int] = {}
    for name, book_id in db.execute(
        select(Book.series_name, Book.id)
        .where(*base)
        .order_by(Book.series_index.is_(None), Book.series_index, Book.id)
    ):
        covers.setdefault(name, book_id)

    # 只有真存在封面文件时才给地址，否则前端会拿到占位图（灰块）
    has_cover = {
        book_id: bool(cover_path)
        for book_id, cover_path in db.execute(
            select(Book.id, Book.cover_path).where(Book.id.in_(covers.values()))
        )
    }

    return SeriesList(
        items=[
            SeriesOut(
                name=name,
                book_count=int(count),
                total_duration_sec=float(duration or 0),
                cover_book_id=covers.get(name),
                cover_url=(
                    f"/api/v1/books/{covers[name]}/cover?size=thumb"
                    if name in covers and has_cover.get(covers[name])
                    else None
                ),
                latest_added_at=int(latest or 0),
            )
            for name, count, duration, latest in rows
        ]
    )


@router.get("/authors", response_model=AuthorList)
def list_authors(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AuthorList:
    """按 `author` 汇总，供书架的「作者」视图使用。"""
    visible = visible_library_ids(db, current_user)
    if not visible:
        return AuthorList(items=[])

    base = (
        Book.is_missing.is_(False),
        Book.hidden.is_(False),
        Book.library_id.in_(visible),
        Book.author.is_not(None),
        Book.author != "",
    )
    rows = db.execute(
        select(
            Book.author,
            func.count(Book.id),
            func.sum(Book.total_duration_sec),
            func.max(Book.added_at),
        )
        .where(*base)
        .group_by(Book.author)
        .order_by(func.max(Book.added_at).desc())
    ).all()

    # 封面：优先挑有封面文件的一本，其次任意一本（都没有则不给 URL）
    covers: dict[str, tuple[int, bool]] = {}
    for name, book_id, cover_path in db.execute(
        select(Book.author, Book.id, Book.cover_path)
        .where(*base)
        .order_by(Book.added_at.desc(), Book.id)
    ):
        if cover_path and name not in covers:
            covers[name] = (book_id, True)
    for name, book_id, _cover_path in db.execute(
        select(Book.author, Book.id, Book.cover_path).where(*base).order_by(Book.id)
    ):
        covers.setdefault(name, (book_id, False))

    return AuthorList(
        items=[
            AuthorOut(
                name=name,
                book_count=int(count),
                total_duration_sec=float(duration or 0),
                cover_book_id=covers[name][0] if name in covers else None,
                cover_url=(
                    f"/api/v1/books/{covers[name][0]}/cover?size=thumb"
                    if covers.get(name, (0, False))[1]
                    else None
                ),
                latest_added_at=int(latest or 0),
            )
            for name, count, duration, latest in rows
        ]
    )


@router.get("/books", response_model=BookList)
def list_books(
    library_id: int | None = None,
    q: str | None = Query(default=None, max_length=256),
    author: str | None = Query(default=None, max_length=256),
    series: str | None = Query(default=None, max_length=256),
    sort: Literal[
        "added_desc",
        "title_asc",
        "author_asc",
        "duration_desc",
        "progress_desc",
        "series_asc",
    ] = "added_desc",
    filter_value: Literal[
        "all", "in_progress", "finished", "unplayed", "downloaded"
    ] = Query("all", alias="filter"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    include_hidden: bool = Query(False, description="仅管理员：包含已隐藏的书"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BookList:
    visible = visible_library_ids(db, current_user)
    if library_id is not None:
        if library_id not in visible:
            raise HTTPException(status_code=403, detail="无权访问该书库")
        visible = [library_id]
    if not visible:
        return BookList(items=[], total=0, page=page, page_size=page_size)

    if include_hidden and not is_admin(current_user):
        raise HTTPException(status_code=403, detail="只有管理员可以查看已隐藏的书籍")

    conditions = [Book.is_missing.is_(False), Book.library_id.in_(visible)]
    if not include_hidden:
        conditions.append(Book.hidden.is_(False))
    if q and q.strip():
        fts, short_terms = search_plan(q)
        if fts:
            # 3 字以上的词走 FTS5（trigram），中文可子串匹配
            conditions.append(
                sql_text(
                    "books.id IN (SELECT rowid FROM books_fts WHERE books_fts MATCH :fts_q)"
                ).bindparams(fts_q=fts)
            )
        # 1–2 字的词产生不了 trigram，退回 LIKE（与 FTS 条件是 AND）
        for term in short_terms:
            like = f"%{term}%"
            conditions.append(
                or_(
                    Book.title.like(like),
                    Book.author.like(like),
                    Book.series_name.like(like),
                )
            )
    if author:
        conditions.append(Book.author == author)
    if series:
        conditions.append(Book.series_name == series)
    if filter_value == "in_progress":
        conditions.extend(
            [
                Progress.user_id.is_not(None),
                Progress.is_finished.is_(False),
                Progress.position_sec > 0,
            ]
        )
    elif filter_value == "finished":
        conditions.append(Progress.is_finished.is_(True))
    elif filter_value == "unplayed":
        conditions.append(Progress.user_id.is_(None))
    elif filter_value == "downloaded":
        # 下载状态只存在于客户端，服务端不掌握
        conditions.append(false())

    join = _progress_join(current_user.id)
    total = int(
        db.scalar(
            select(func.count())
            .select_from(Book)
            .outerjoin(Progress, join)
            .where(*conditions)
        )
        or 0
    )
    rows = db.execute(
        select(Book, Progress)
        .outerjoin(Progress, join)
        .where(*conditions)
        .order_by(*_order_by(sort))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return BookList(
        items=[book_out(book, progress) for book, progress in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/books/{book_id}", response_model=BookDetail)
def get_book(
    book_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BookDetail:
    book = require_visible_book(db, current_user, book_id)

    track_rows = db.execute(
        select(Track, MediaFile)
        .join(MediaFile, MediaFile.id == Track.media_file_id)
        .where(Track.book_id == book.id)
        .order_by(Track.disc_no, Track.track_no)
    ).all()
    tracks = [
        TrackOut(
            id=track.id,
            track_no=track.track_no,
            disc_no=track.disc_no,
            title=track.title,
            duration_sec=track.duration_sec,
            format=media.format,
            bitrate=media.bitrate,
            stream_url=f"/api/v1/books/{book.id}/tracks/{track.id}/stream",
        )
        for track, media in track_rows
    ]

    chapter_total = int(
        db.scalar(select(func.count(Chapter.id)).where(Chapter.book_id == book.id)) or 0
    )
    chapters: list[ChapterOut] | None = None
    if chapter_total <= EMBED_CHAPTER_LIMIT:
        chapters = [
            ChapterOut(
                id=chapter.id,
                idx=chapter.idx,
                title=chapter.title,
                start_sec=chapter.start_sec,
                end_sec=chapter.end_sec,
                track_id=chapter.track_id,
            )
            for chapter in db.scalars(
                select(Chapter).where(Chapter.book_id == book.id).order_by(Chapter.idx)
            )
        ]

    progress = db.scalar(
        select(Progress).where(
            Progress.user_id == current_user.id, Progress.book_id == book.id
        )
    )
    base = book_out(book, progress)
    return BookDetail(
        **base.model_dump(),
        subtitle=book.subtitle,
        publisher=book.publisher,
        publish_year=book.publish_year,
        description=book.description,
        rel_dir=book.rel_dir,
        is_missing=book.is_missing,
        updated_at=book.updated_at,
        tracks=tracks,
        chapters=chapters,
    )


@router.post("/books/{book_id}/play-token", response_model=PlayTokenOut)
def create_play_token(
    book_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlayTokenOut:
    """给 <audio> 用的短时令牌：绑定本书、6 小时有效，避免把 access token 塞进 URL。"""
    require_visible_book(db, current_user, book_id)
    token, ttl = create_stream_token(current_user.id, book_id)
    return PlayTokenOut(token=token, expires_in=ttl, expires_at=int(time.time()) + ttl)


@router.patch("/books/{book_id}", response_model=BookOut)
def update_book(
    book_id: int,
    payload: BookUpdate,
    editor: User = Depends(require_editor),
    db: Session = Depends(get_db),
) -> BookOut:
    book = require_visible_book(db, editor, book_id)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="没有需要更新的字段")
    if updates.get("hidden") is not None and not is_admin(editor):
        raise HTTPException(status_code=403, detail="只有管理员可以隐藏书籍")

    for field, value in updates.items():
        if field == "title":
            cleaned = (value or "").strip()
            if not cleaned:
                raise HTTPException(status_code=400, detail="书名不能为空")
            book.title = cleaned
        elif isinstance(value, str):
            # 空字符串视为清空该字段
            setattr(book, field, value.strip() or None)
        else:
            setattr(book, field, value)

    total = book.total_duration_sec or 0
    if total > 0 and (book.intro_sec or 0) + (book.outro_sec or 0) >= total:
        raise HTTPException(status_code=400, detail="片头加片尾不能超过总时长")

    # 只切隐藏状态不算「手工改元数据」，否则扫描不再更新资料
    if set(updates) - {"hidden"}:
        book.manual_override = True
    book.updated_at = now_ts()
    db.commit()
    db.refresh(book)

    progress = db.scalar(
        select(Progress).where(
            Progress.user_id == editor.id, Progress.book_id == book.id
        )
    )
    return book_out(book, progress)


@router.post("/books/{book_id}/metadata/reset", response_model=BookOut)
def reset_metadata(
    book_id: int,
    editor: User = Depends(require_editor),
    db: Session = Depends(get_db),
) -> BookOut:
    """清除「手工修改」标记，下次扫描重新用音频标签覆盖元数据。"""
    book = require_visible_book(db, editor, book_id)
    book.manual_override = False
    book.updated_at = now_ts()
    db.commit()
    db.refresh(book)

    progress = db.scalar(
        select(Progress).where(
            Progress.user_id == editor.id, Progress.book_id == book.id
        )
    )
    return book_out(book, progress)


@router.put("/books/{book_id}/cover", response_model=BookOut)
async def upload_cover(
    book_id: int,
    file: UploadFile = File(...),
    editor: User = Depends(require_editor),
    db: Session = Depends(get_db),
) -> BookOut:
    """上传/替换封面（管理员或上传者）：统一转 JPEG，并生成 400px 缩略图。"""
    book = require_visible_book(db, editor, book_id)
    payload = await file.read(MAX_UPLOAD_BYTES + 1)
    if not payload:
        raise HTTPException(status_code=400, detail="文件为空")
    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="封面不能超过 5 MB")

    try:
        book.cover_path = save_cover(book.id, payload, get_settings().covers_dir)
    except CoverError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # 记录上传者：上传者之后只能删自己传的这张
    book.cover_uploaded_by = editor.id
    book.updated_at = now_ts()
    db.commit()
    db.refresh(book)

    progress = db.scalar(
        select(Progress).where(
            Progress.user_id == editor.id, Progress.book_id == book.id
        )
    )
    return book_out(book, progress)


@router.delete("/books/{book_id}/cover", response_model=BookOut)
def delete_cover(
    book_id: int,
    editor: User = Depends(require_editor),
    db: Session = Depends(get_db),
) -> BookOut:
    """删除手工封面：管理员可删任意；上传者仅限自己上传的。"""
    book = require_visible_book(db, editor, book_id)
    if not can_delete_cover(editor, book):
        raise HTTPException(status_code=403, detail="只能删除自己上传的封面")
    remove_cover(book.id, get_settings().covers_dir)
    book.cover_path = None
    book.cover_uploaded_by = None
    book.updated_at = now_ts()
    db.commit()
    db.refresh(book)

    progress = db.scalar(
        select(Progress).where(
            Progress.user_id == editor.id, Progress.book_id == book.id
        )
    )
    return book_out(book, progress)


@router.get("/books/{book_id}/chapters", response_model=ChapterList)
def list_chapters(
    book_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChapterList:
    book = require_visible_book(db, current_user, book_id)
    total = int(
        db.scalar(select(func.count(Chapter.id)).where(Chapter.book_id == book.id)) or 0
    )
    rows = db.scalars(
        select(Chapter)
        .where(Chapter.book_id == book.id)
        .order_by(Chapter.idx)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return ChapterList(
        items=[
            ChapterOut(
                id=chapter.id,
                idx=chapter.idx,
                title=chapter.title,
                start_sec=chapter.start_sec,
                end_sec=chapter.end_sec,
                track_id=chapter.track_id,
            )
            for chapter in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


def _cover_payload(book: Book, size: str, covers_dir: Path) -> tuple[str, bytes, str]:
    if book.cover_path:
        base = (covers_dir / book.cover_path).resolve()
        candidates = []
        if size == "thumb":
            candidates.append(base.with_name(f"{base.stem}_thumb{base.suffix}"))
        candidates.append(base)
        for path in candidates:
            if path.is_file():
                stat = path.stat()
                etag = f'"{book.id}-{int(stat.st_mtime)}-{stat.st_size}"'
                media_type = _IMAGE_TYPES.get(path.suffix.lower(), "image/jpeg")
                return etag, path.read_bytes(), media_type
    return _PLACEHOLDER_ETAG, _PLACEHOLDER_SVG, "image/svg+xml"


@router.get("/books/{book_id}/cover")
def get_cover(
    book_id: int,
    request: Request,
    size: Literal["thumb", "full"] = "thumb",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    book = require_visible_book(db, current_user, book_id)
    settings = get_settings()
    etag, payload, media_type = _cover_payload(book, size, settings.covers_dir)
    headers = {"ETag": etag, "Cache-Control": CACHE_CONTROL}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(content=payload, media_type=media_type, headers=headers)
