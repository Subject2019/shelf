"""个人书单接口：书单 CRUD 与书籍成员管理。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import and_, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.base import now_ts
from app.db.session import get_db
from app.models import Book, Collection, CollectionBook, Progress, User
from app.schemas.collection import (
    CollectionBookCreate,
    CollectionCreate,
    CollectionDetail,
    CollectionList,
    CollectionOut,
    CollectionUpdate,
)
from app.services.book_dto import book_out
from app.services.permissions import (
    is_admin,
    require_visible_book,
    visible_library_ids,
)

router = APIRouter(tags=["collections"])


def _owned_collection(db: Session, user: User, collection_id: int) -> Collection:
    collection = db.get(Collection, collection_id)
    if collection is None or collection.user_id != user.id:
        # 不区分「不存在」和「别人的」，避免泄露书单 id
        raise HTTPException(status_code=404, detail="书单不存在")
    return collection


def _visible_conditions(db: Session, user: User) -> list:
    """书单里只统计当前用户仍然有权限看到的书。"""
    conditions = [
        Book.is_missing.is_(False),
        Book.library_id.in_(visible_library_ids(db, user)),
    ]
    if not is_admin(user):
        conditions.append(Book.hidden.is_(False))
    return conditions


def _summary(
    db: Session,
    user: User,
    collection: Collection,
    *,
    contains_book: bool = False,
) -> CollectionOut:
    conditions = [
        CollectionBook.collection_id == collection.id,
        *_visible_conditions(db, user),
    ]
    count = int(
        db.scalar(
            select(func.count())
            .select_from(CollectionBook)
            .join(Book, Book.id == CollectionBook.book_id)
            .where(*conditions)
        )
        or 0
    )
    cover_book_id = db.scalar(
        select(Book.id)
        .join(CollectionBook, CollectionBook.book_id == Book.id)
        .where(*conditions, Book.cover_path.is_not(None))
        .order_by(CollectionBook.added_at.desc(), Book.id.desc())
        .limit(1)
    )
    return CollectionOut(
        id=collection.id,
        name=collection.name,
        book_count=count,
        created_at=collection.created_at,
        cover_url=(
            f"/api/v1/books/{cover_book_id}/cover?size=thumb"
            if cover_book_id is not None
            else None
        ),
        contains_book=contains_book,
    )


def _ensure_unique_name(
    db: Session,
    user_id: int,
    name: str,
    *,
    exclude_id: int | None = None,
) -> None:
    stmt = select(Collection.id).where(
        Collection.user_id == user_id,
        Collection.name == name,
    )
    if exclude_id is not None:
        stmt = stmt.where(Collection.id != exclude_id)
    if db.scalar(stmt) is not None:
        raise HTTPException(status_code=409, detail="书单名称已存在")


def _commit_or_conflict(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="书单名称已存在") from None


@router.get("/collections", response_model=CollectionList)
def list_collections(
    book_id: int | None = Query(
        default=None,
        ge=1,
        description="可选：返回每个书单是否包含这本书，用于详情页勾选",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CollectionList:
    if book_id is not None:
        # 不可见的书不允许用来探测书单成员关系
        require_visible_book(db, current_user, book_id)

    collections = list(
        db.scalars(
            select(Collection)
            .where(Collection.user_id == current_user.id)
            .order_by(Collection.created_at.desc(), Collection.id.desc())
        )
    )
    contains_ids: set[int] = set()
    if book_id is not None and collections:
        contains_ids = set(
            db.scalars(
                select(CollectionBook.collection_id).where(
                    CollectionBook.book_id == book_id,
                    CollectionBook.collection_id.in_(
                        [collection.id for collection in collections]
                    ),
                )
            )
        )

    return CollectionList(
        items=[
            _summary(
                db,
                current_user,
                collection,
                contains_book=collection.id in contains_ids,
            )
            for collection in collections
        ]
    )


@router.post("/collections", response_model=CollectionOut, status_code=201)
def create_collection(
    payload: CollectionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CollectionOut:
    _ensure_unique_name(db, current_user.id, payload.name)
    collection = Collection(
        user_id=current_user.id,
        name=payload.name,
        created_at=now_ts(),
    )
    db.add(collection)
    _commit_or_conflict(db)
    db.refresh(collection)
    return _summary(db, current_user, collection)


@router.get("/collections/{collection_id}", response_model=CollectionDetail)
def get_collection(
    collection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CollectionDetail:
    collection = _owned_collection(db, current_user, collection_id)
    rows = db.execute(
        select(Book, Progress)
        .join(CollectionBook, CollectionBook.book_id == Book.id)
        .outerjoin(
            Progress,
            and_(
                Progress.book_id == Book.id,
                Progress.user_id == current_user.id,
            ),
        )
        .where(
            CollectionBook.collection_id == collection.id,
            *_visible_conditions(db, current_user),
        )
        .order_by(CollectionBook.added_at.desc(), Book.id.desc())
    ).all()
    summary = _summary(db, current_user, collection, contains_book=True)
    return CollectionDetail(
        **summary.model_dump(),
        books=[book_out(book, progress) for book, progress in rows],
    )


@router.patch("/collections/{collection_id}", response_model=CollectionOut)
def update_collection(
    collection_id: int,
    payload: CollectionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CollectionOut:
    collection = _owned_collection(db, current_user, collection_id)
    _ensure_unique_name(
        db,
        current_user.id,
        payload.name,
        exclude_id=collection.id,
    )
    collection.name = payload.name
    _commit_or_conflict(db)
    return _summary(db, current_user, collection)


@router.delete("/collections/{collection_id}", status_code=204)
def delete_collection(
    collection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    collection = _owned_collection(db, current_user, collection_id)
    # SQLite 默认不保证开启外键级联，显式清理关联行
    db.execute(
        delete(CollectionBook).where(CollectionBook.collection_id == collection.id)
    )
    db.delete(collection)
    db.commit()
    return Response(status_code=204)


@router.post("/collections/{collection_id}/books", response_model=CollectionOut)
def add_book(
    collection_id: int,
    payload: CollectionBookCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CollectionOut:
    collection = _owned_collection(db, current_user, collection_id)
    book = require_visible_book(db, current_user, payload.book_id)
    existing = db.get(CollectionBook, (collection.id, book.id))
    if existing is None:
        db.add(
            CollectionBook(
                collection_id=collection.id,
                book_id=book.id,
                added_at=now_ts(),
            )
        )
        db.commit()
    return _summary(db, current_user, collection, contains_book=True)


@router.delete("/collections/{collection_id}/books/{book_id}", status_code=204)
def remove_book(
    collection_id: int,
    book_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    collection = _owned_collection(db, current_user, collection_id)
    row = db.get(CollectionBook, (collection.id, book_id))
    if row is not None:
        db.delete(row)
        db.commit()
    return Response(status_code=204)
