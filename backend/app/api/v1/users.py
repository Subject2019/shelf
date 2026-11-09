"""用户管理接口（仅管理员）。

- 创建 / 停用 / 改角色 / 重置密码 / 分配书库（**不能创建或提升管理员**）
- 管理员唯一，只能由 Docker 环境变量或 `app.cli admin create` 带外创建
- 保护规则：不能停用或降级自己，不能删除自己，不能删除或降级最后一个可用管理员
- 停用与改密会立即吊销该用户所有 refresh token；配合设备管理可让 access 也失效
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.base import now_ts
from app.db.session import get_db
from app.models import Library, LibraryUser, RefreshToken, User
from app.schemas.user import UserAdminList, UserAdminOut, UserCreateIn, UserUpdateIn
from app.services.permissions import require_admin, visible_library_ids

router = APIRouter(tags=["users"])


def _to_out(db: Session, user: User) -> UserAdminOut:
    return UserAdminOut(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
        passwordless=user.passwordless,
        libraries=visible_library_ids(db, user),
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


def _normalize_username(raw: str) -> str:
    username = raw.strip().lower()
    if len(username) < 2:
        raise HTTPException(status_code=422, detail="用户名至少 2 个字符")
    return username


def _get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


def _active_admins(db: Session, exclude_id: int | None = None) -> int:
    query = (
        select(func.count())
        .select_from(User)
        .where(User.role == "admin", User.is_active.is_(True))
    )
    if exclude_id is not None:
        query = query.where(User.id != exclude_id)
    return db.scalar(query) or 0


def _revoke_tokens(db: Session, user_id: int) -> None:
    now = now_ts()
    for token in db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
        )
    ):
        token.revoked_at = now


def _set_libraries(db: Session, user: User, library_ids: list[int]) -> None:
    unique = sorted(set(library_ids))
    if unique:
        found = set(db.scalars(select(Library.id).where(Library.id.in_(unique))).all())
        missing = [item for item in unique if item not in found]
        if missing:
            raise HTTPException(
                status_code=400, detail=f"书库不存在：{', '.join(map(str, missing))}"
            )

    db.query(LibraryUser).filter(LibraryUser.user_id == user.id).delete(
        synchronize_session=False
    )
    for library_id in unique:
        db.add(LibraryUser(library_id=library_id, user_id=user.id))


@router.get("/users", response_model=UserAdminList)
def list_users(
    q: str | None = Query(None, max_length=64),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserAdminList:
    query = select(User)
    if q:
        keyword = f"%{q.strip().lower()}%"
        query = query.where(
            (func.lower(User.username).like(keyword))
            | (func.lower(func.coalesce(User.display_name, "")).like(keyword))
        )

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(
        query.order_by(User.id).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return UserAdminList(
        items=[_to_out(db, user) for user in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/users", response_model=UserAdminOut, status_code=201)
def create_user(
    payload: UserCreateIn,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserAdminOut:
    username = _normalize_username(payload.username)
    exists = db.scalar(select(User.id).where(User.username == username))
    if exists:
        raise HTTPException(status_code=409, detail="用户名已存在")

    if payload.passwordless:
        if payload.role != "listener":
            raise HTTPException(
                status_code=400, detail="免密账号只能创建为听众，不能是上传者"
            )
        if payload.password:
            raise HTTPException(
                status_code=400, detail="免密账号不能同时设置密码"
            )
        password_hash = ""
    else:
        if not payload.password:
            raise HTTPException(status_code=400, detail="请设置初始密码，或选择免密听众")
        password_hash = hash_password(payload.password)

    user = User(
        username=username,
        password_hash=password_hash,
        passwordless=payload.passwordless,
        display_name=payload.display_name,
        role=payload.role,
        is_active=True,
        created_at=now_ts(),
    )
    db.add(user)
    db.flush()
    if payload.library_ids:
        _set_libraries(db, user, payload.library_ids)
    db.commit()
    db.refresh(user)
    return _to_out(db, user)


@router.patch("/users/{user_id}", response_model=UserAdminOut)
def update_user(
    user_id: int,
    payload: UserUpdateIn,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserAdminOut:
    user = _get_user(db, user_id)
    protected = user.id == admin.id
    effective_role = payload.role if payload.role is not None else user.role

    if user.passwordless and effective_role != "listener":
        raise HTTPException(
            status_code=400, detail="免密账号只能作为听众；请先设置密码再修改角色"
        )
    if payload.passwordless is True:
        if effective_role != "listener":
            raise HTTPException(
                status_code=400, detail="免密账号只能作为听众，不能是上传者或管理员"
            )
        if payload.password is not None:
            raise HTTPException(
                status_code=400, detail="免密账号不能同时设置密码"
            )
    if payload.passwordless is False and payload.password is None:
        raise HTTPException(status_code=400, detail="关闭免密需要同时设置新密码")

    if payload.role is not None and payload.role != user.role:
        if protected:
            raise HTTPException(status_code=409, detail="不能修改自己的角色")
        if user.role == "admin" and payload.role != "admin":
            if _active_admins(db, exclude_id=user.id) == 0:
                raise HTTPException(status_code=409, detail="至少要保留一个管理员")
        user.role = payload.role

    if payload.is_active is not None and payload.is_active != user.is_active:
        if protected and not payload.is_active:
            raise HTTPException(status_code=409, detail="不能停用自己的账号")
        if not payload.is_active and user.role == "admin":
            if _active_admins(db, exclude_id=user.id) == 0:
                raise HTTPException(status_code=409, detail="至少要保留一个管理员")
        user.is_active = payload.is_active
        if not payload.is_active:
            _revoke_tokens(db, user.id)

    if payload.display_name is not None:
        user.display_name = payload.display_name

    if payload.password is not None:
        user.password_hash = hash_password(payload.password)
        user.passwordless = False
        # 改密后旧设备需要重新登录
        _revoke_tokens(db, user.id)

    if payload.passwordless is True:
        user.password_hash = ""
        user.passwordless = True

    if payload.library_ids is not None:
        _set_libraries(db, user, payload.library_ids)

    db.commit()
    db.refresh(user)
    return _to_out(db, user)


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Response:
    user = _get_user(db, user_id)
    if user.id == admin.id:
        raise HTTPException(status_code=409, detail="不能删除自己的账号")
    if (
        user.role == "admin"
        and user.is_active
        and _active_admins(db, exclude_id=user.id) == 0
    ):
        raise HTTPException(status_code=409, detail="至少要保留一个管理员")

    # 进度、书签、设备、refresh token 均由外键 CASCADE 清理
    db.delete(user)
    db.commit()
    return Response(status_code=204)
