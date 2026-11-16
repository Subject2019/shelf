"""书库可见性与管理员校验。

约定（docs/DATA_MODEL.md 2.3）：某书库在 library_users 中无任何行 = 全员可见。
"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import (
    bearer_scheme,
    decode_download_token,
    get_current_user,
)
from app.db.session import get_db
from app.models import Book, Library, LibraryUser, User


def visible_library_ids(db: Session, user: User) -> list[int]:
    all_ids = list(
        db.scalars(
            select(Library.id).where(Library.enabled.is_(True)).order_by(Library.id)
        )
    )
    if user.role == "admin":
        return all_ids

    # 判定依据是「书库有没有授权行」：整库没有任何行 = 公开，有行则只对清单内用户可见
    granted: dict[int, set[int]] = {}
    for library_id, user_id in db.execute(
        select(LibraryUser.library_id, LibraryUser.user_id)
    ):
        granted.setdefault(library_id, set()).add(user_id)

    return [
        library_id
        for library_id in all_ids
        if not granted.get(library_id) or user.id in granted[library_id]
    ]


def can_view_library(db: Session, user: User, library_id: int) -> bool:
    return library_id in visible_library_ids(db, user)


def require_visible_book(db: Session, user: User, book_id: int) -> Book:
    book = db.get(Book, book_id)
    if book is None or book.is_missing:
        raise HTTPException(status_code=404, detail="书籍不存在")
    if not can_view_library(db, user, book.library_id):
        raise HTTPException(status_code=403, detail="无权访问该书库")
    # 被管理员隐藏的书对普通用户等同于不存在
    if book.hidden and not is_admin(user):
        raise HTTPException(status_code=404, detail="书籍不存在")
    return book


ROLE_ADMIN = "admin"
ROLE_EDITOR = "editor"
ROLE_LISTENER = "listener"


def is_admin(user: User) -> bool:
    return user.role == ROLE_ADMIN


def can_edit(user: User) -> bool:
    """能否改书籍资料/封面：管理员与上传者。

    历史数据里可能存在 `role="user"`（旧的两档模型），按最保守的「听众」处理。
    """
    return user.role in (ROLE_ADMIN, ROLE_EDITOR)


def can_delete_cover(user: User, book: Book) -> bool:
    """管理员可删任意封面；上传者只能删自己传的那张。"""
    if user.role == ROLE_ADMIN:
        return True
    return book.cover_uploaded_by is not None and book.cover_uploaded_by == user.id


def get_download_user(
    book_id: int,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    download_token: str | None = Header(default=None, alias="X-Download-Token"),
    db: Session = Depends(get_db),
) -> User:
    """章节下载/切片鉴权：支持普通 access token 或单本书下载票据。

    下载票据只允许本书的 `bid`，不能访问其他书籍或普通 API；如果同时带了
    无效票据，不会回退到 access token，避免客户端误以为票据可用。
    """
    if download_token:
        user_id = decode_download_token(download_token, book_id)
        if user_id is None:
            raise HTTPException(
                status_code=401,
                detail="下载票据无效或已过期",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user = db.get(User, user_id)
        if user is None or not user.is_active:
            raise HTTPException(status_code=401, detail="下载账号不可用")
        return user
    return get_current_user(credentials, db)


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not is_admin(current_user):
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user


def require_editor(current_user: User = Depends(get_current_user)) -> User:
    if not can_edit(current_user):
        raise HTTPException(status_code=403, detail="需要上传者或管理员权限")
    return current_user
