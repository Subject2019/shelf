"""书库接口：登记、列表、触发扫描与任务状态。"""

from __future__ import annotations

import os
import threading
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import get_current_user
from app.db.base import now_ts
from app.db.session import get_db
from app.models import Book, Library, LibraryUser, ScanTask, User
from app.schemas.library import (
    LibraryCreate,
    LibraryList,
    LibraryOut,
    LibraryUpdate,
    ScanBrief,
    ScanStatusOut,
    ScanTriggerOut,
)
from app.services.permissions import (
    can_view_library,
    require_admin,
    visible_library_ids,
)

router = APIRouter(tags=["libraries"])

# 单进程部署下用进程内锁消除「同时触发两次扫描」的竞态
_scan_trigger_lock = threading.Lock()


def _audiobooks_root() -> Path | None:
    """服务端只允许登记有声书根目录下的路径，避免书库越界。"""
    if os.environ.get("ECHOSHELF_CONTAINER") != "1":
        return None
    return get_settings().audiobooks_path.expanduser().resolve()


def _library_out(db: Session, library: Library) -> LibraryOut:
    book_count, total_duration = db.execute(
        select(
            func.count(Book.id),
            func.coalesce(func.sum(Book.total_duration_sec), 0.0),
        ).where(
            Book.library_id == library.id,
            Book.is_missing.is_(False),
            Book.hidden.is_(False),
        )
    ).one()
    latest = db.scalar(
        select(ScanTask)
        .where(ScanTask.library_id == library.id)
        .order_by(ScanTask.id.desc())
        .limit(1)
    )
    return LibraryOut(
        id=library.id,
        name=library.name,
        root_path=library.root_path,
        enabled=library.enabled,
        book_count=int(book_count),
        total_duration_sec=float(total_duration),
        last_scan_at=library.last_scan_at,
        scan=(
            ScanBrief(status=latest.status, finished_at=latest.finished_at)
            if latest is not None
            else None
        ),
    )


@router.get("/libraries", response_model=LibraryList)
def list_libraries(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LibraryList:
    # 管理员需要看到「已停用」的书库（否则停用后列表里消失、无法再启用）；
    # 普通用户仍只看到启用且已授权的书库。
    if current_user.role == "admin":
        visible = list(db.scalars(select(Library.id).order_by(Library.id)))
    else:
        visible = visible_library_ids(db, current_user)
    page_ids = visible[(page - 1) * page_size : page * page_size]
    if not page_ids:
        return LibraryList(items=[], total=len(visible), page=page, page_size=page_size)
    libraries = list(
        db.scalars(select(Library).where(Library.id.in_(page_ids)).order_by(Library.id))
    )
    return LibraryList(
        items=[_library_out(db, library) for library in libraries],
        total=len(visible),
        page=page,
        page_size=page_size,
    )


@router.post("/libraries", response_model=LibraryOut, status_code=201)
def create_library(
    payload: LibraryCreate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> LibraryOut:
    root_input = Path(payload.root_path).expanduser()
    if not root_input.is_absolute():
        raise HTTPException(
            status_code=400,
            detail="请填写有声书目录的绝对路径，例如 /audiobooks 或 /vol1/@appshare/shelfnative/media",
        )
    root = root_input.resolve()

    audiobooks_root = _audiobooks_root()
    if audiobooks_root is not None:
        try:
            root.relative_to(audiobooks_root)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"书库路径必须位于有声书根目录 {audiobooks_root} 下；"
                    "Docker 的根目录由挂载决定，原生安装的根目录由安装时选择"
                ),
            ) from None

    if not root.is_dir():
        raise HTTPException(
            status_code=400,
            detail="目录不存在或不是目录；请确认有声书目录已挂载/存在",
        )
    if not os.access(root, os.R_OK | os.X_OK):
        raise HTTPException(
            status_code=400,
            detail=(
                "目录存在，但应用当前用户无权读取；"
                "Docker 请检查 PUID/PGID，原生安装请检查目录权限"
            ),
        )
    normalized = str(root)

    exists = db.scalar(select(Library).where(Library.root_path == normalized))
    if exists is not None:
        if exists.enabled:
            raise HTTPException(status_code=409, detail="该书库路径已登记")
        # 之前被停用的登记：重新启用并更新名称/授权，避免「路径已登记却又看不见」的死锁
        exists.enabled = True
        exists.name = payload.name.strip()
        db.execute(delete(LibraryUser).where(LibraryUser.library_id == exists.id))
        for user_id in sorted(set(payload.user_ids)):
            if db.get(User, user_id) is None:
                raise HTTPException(status_code=400, detail=f"用户 {user_id} 不存在")
            db.add(LibraryUser(library_id=exists.id, user_id=user_id))
        db.commit()
        db.refresh(exists)
        return _library_out(db, exists)

    library = Library(
        name=payload.name.strip(),
        root_path=normalized,
        enabled=True,
        created_at=now_ts(),
    )
    db.add(library)
    db.flush()

    for user_id in sorted(set(payload.user_ids)):
        if db.get(User, user_id) is None:
            raise HTTPException(status_code=400, detail=f"用户 {user_id} 不存在")
        db.add(LibraryUser(library_id=library.id, user_id=user_id))

    db.commit()
    db.refresh(library)
    return _library_out(db, library)


@router.post(
    "/libraries/{library_id}/scan", response_model=ScanTriggerOut, status_code=202
)
def trigger_scan(
    library_id: int,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ScanTriggerOut:
    library = db.get(Library, library_id)
    if library is None:
        raise HTTPException(status_code=404, detail="书库不存在")
    if not library.enabled:
        raise HTTPException(status_code=400, detail="书库已停用")

    worker = getattr(request.app.state, "scan_worker", None)
    if worker is None:
        raise HTTPException(status_code=503, detail="扫描器未启动")

    with _scan_trigger_lock:
        active = db.scalar(
            select(ScanTask).where(
                ScanTask.library_id == library_id,
                ScanTask.status.in_(("queued", "running")),
            )
        )
        if active is not None:
            raise HTTPException(status_code=409, detail="扫描已在进行中")
        task = ScanTask(
            library_id=library_id,
            status="queued",
            triggered_by=admin.id,
            created_at=now_ts(),
        )
        db.add(task)
        db.commit()
        db.refresh(task)

    worker.submit(task.id)
    return ScanTriggerOut(task_id=task.id, status=task.status)


@router.patch("/libraries/{library_id}", response_model=LibraryOut)
def update_library(
    library_id: int,
    payload: LibraryUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> LibraryOut:
    library = db.get(Library, library_id)
    if library is None:
        raise HTTPException(status_code=404, detail="书库不存在")

    if payload.name is not None:
        library.name = payload.name.strip()
    if payload.enabled is not None:
        library.enabled = payload.enabled
    if payload.user_ids is not None:
        user_ids = sorted(set(payload.user_ids))
        for user_id in user_ids:
            if db.get(User, user_id) is None:
                raise HTTPException(status_code=400, detail=f"用户 {user_id} 不存在")
        db.execute(delete(LibraryUser).where(LibraryUser.library_id == library_id))
        for user_id in user_ids:
            db.add(LibraryUser(library_id=library_id, user_id=user_id))

    db.commit()
    db.refresh(library)
    return _library_out(db, library)


@router.delete("/libraries/{library_id}", status_code=204)
def delete_library(
    library_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Response:
    library = db.get(Library, library_id)
    if library is None:
        raise HTTPException(status_code=404, detail="书库不存在")
    # 只删登记与索引，媒体文件保持原样；子表由 SQLite 外键级联清理
    db.delete(library)
    db.commit()
    return Response(status_code=204)


@router.get("/libraries/{library_id}/scan/status", response_model=ScanStatusOut)
def scan_status(
    library_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScanStatusOut:
    if not can_view_library(db, current_user, library_id):
        raise HTTPException(status_code=403, detail="无权访问该书库")
    task = db.scalar(
        select(ScanTask)
        .where(ScanTask.library_id == library_id)
        .order_by(ScanTask.id.desc())
        .limit(1)
    )
    if task is None:
        raise HTTPException(status_code=404, detail="尚无扫描记录")
    return ScanStatusOut(
        task_id=task.id,
        status=task.status,
        started_at=task.started_at,
        finished_at=task.finished_at,
        files_seen=task.files_seen,
        files_added=task.files_added,
        files_updated=task.files_updated,
        files_removed=task.files_removed,
        books_created=task.books_created,
        books_updated=task.books_updated,
        error=task.error,
    )
