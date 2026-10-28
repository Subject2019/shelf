"""书签接口：按书查询、新建、改备注、删除。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.base import now_ts
from app.db.session import get_db
from app.models import Bookmark, User
from app.schemas.bookmark import BookmarkCreate, BookmarkOut, BookmarkUpdate
from app.services.permissions import require_visible_book

router = APIRouter(tags=["bookmarks"])

POSITION_SLACK_SEC = 5.0


def _bookmark_out(bookmark: Bookmark) -> BookmarkOut:
    return BookmarkOut(
        id=bookmark.id,
        book_id=bookmark.book_id,
        position_sec=bookmark.position_sec,
        track_id=bookmark.track_id,
        note=bookmark.note,
        created_at=bookmark.created_at,
    )


def _own_bookmark(db: Session, user: User, bookmark_id: int) -> Bookmark:
    bookmark = db.get(Bookmark, bookmark_id)
    if bookmark is None or bookmark.user_id != user.id:
        raise HTTPException(status_code=404, detail="书签不存在")
    return bookmark


@router.get("/books/{book_id}/bookmarks", response_model=list[BookmarkOut])
def list_bookmarks(
    book_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[BookmarkOut]:
    book = require_visible_book(db, current_user, book_id)
    rows = db.scalars(
        select(Bookmark)
        .where(Bookmark.user_id == current_user.id, Bookmark.book_id == book.id)
        .order_by(Bookmark.position_sec, Bookmark.id)
    )
    return [_bookmark_out(bookmark) for bookmark in rows]


@router.post("/books/{book_id}/bookmarks", response_model=BookmarkOut, status_code=201)
def create_bookmark(
    book_id: int,
    payload: BookmarkCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BookmarkOut:
    book = require_visible_book(db, current_user, book_id)
    if (
        book.total_duration_sec > 0
        and payload.position_sec > book.total_duration_sec + POSITION_SLACK_SEC
    ):
        raise HTTPException(status_code=400, detail="书签位置超过书籍总时长")

    bookmark = Bookmark(
        user_id=current_user.id,
        book_id=book.id,
        position_sec=payload.position_sec,
        track_id=payload.track_id,
        note=payload.note,
        created_at=now_ts(),
    )
    db.add(bookmark)
    db.commit()
    db.refresh(bookmark)
    return _bookmark_out(bookmark)


@router.patch("/bookmarks/{bookmark_id}", response_model=BookmarkOut)
def update_bookmark(
    bookmark_id: int,
    payload: BookmarkUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BookmarkOut:
    bookmark = _own_bookmark(db, current_user, bookmark_id)
    bookmark.note = payload.note
    db.commit()
    db.refresh(bookmark)
    return _bookmark_out(bookmark)


@router.delete("/bookmarks/{bookmark_id}", status_code=204)
def delete_bookmark(
    bookmark_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    bookmark = _own_bookmark(db, current_user, bookmark_id)
    db.delete(bookmark)
    db.commit()
    return Response(status_code=204)
