"""收听进度接口：合并上报、查询、清空与「继续收听」。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.base import now_ts
from app.db.session import get_db
from app.models import Book, Progress, ProgressHistory, Track, User
from app.schemas.progress import (
    ProgressHistoryItem,
    ProgressHistoryList,
    ProgressOut,
    ProgressPut,
    ProgressPutOut,
    RecentProgressItem,
    RecentProgressList,
)
from app.services.permissions import require_visible_book, visible_library_ids
from app.services.progress import (
    ProgressState,
    locate_track,
    merge_progress,
    track_position,
    track_start_offsets,
)
from app.services.progress_history import (
    HISTORY_LIMIT,
    record_checkpoint,
)
from app.services.stats import listened_seconds, record_listening

router = APIRouter(tags=["progress"])

FINISH_TOLERANCE_SEC = 30.0
POSITION_SLACK_SEC = 5.0


@router.get("/progress/recent", response_model=RecentProgressList)
def list_recent_progress(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecentProgressList:
    visible = visible_library_ids(db, current_user)
    if not visible:
        return RecentProgressList(items=[])

    rows = db.execute(
        select(Progress, Book)
        .join(Book, Book.id == Progress.book_id)
        .where(
            Progress.user_id == current_user.id,
            Progress.is_finished.is_(False),
            Book.is_missing.is_(False),
            Book.hidden.is_(False),
            Book.library_id.in_(visible),
        )
        .order_by(Progress.updated_at.desc())
        .limit(limit)
    ).all()

    items: list[RecentProgressItem] = []
    for progress, book in rows:
        percent = (
            0.0
            if book.total_duration_sec <= 0
            else min(100.0, progress.position_sec / book.total_duration_sec * 100)
        )
        items.append(
            RecentProgressItem(
                book_id=book.id,
                title=book.title,
                author=book.author,
                cover_url=(
                    f"/api/v1/books/{book.id}/cover?size=thumb"
                    if book.cover_path
                    else None
                ),
                position_sec=progress.position_sec,
                total_duration_sec=book.total_duration_sec,
                percent=round(percent, 2),
                updated_at=progress.updated_at,
                device_id=progress.device_id,
            )
        )
    return RecentProgressList(items=items)


@router.get("/progress/{book_id}", response_model=ProgressOut)
def get_progress(
    book_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProgressOut:
    book = require_visible_book(db, current_user, book_id)
    row = db.get(Progress, (current_user.id, book.id))
    if row is None:
        return ProgressOut(
            book_id=book.id,
            position_sec=0.0,
            track_id=None,
            track_position_sec=0.0,
            playback_rate=1.0,
            is_finished=False,
            device_id=None,
            client_updated_at=0,
            updated_at=0,
        )
    return ProgressOut(
        book_id=book.id,
        position_sec=row.position_sec,
        track_id=row.track_id,
        track_position_sec=row.track_position_sec or 0.0,
        playback_rate=row.playback_rate,
        is_finished=row.is_finished,
        device_id=row.device_id,
        client_updated_at=row.client_updated_at or 0,
        updated_at=row.updated_at,
    )


@router.put("/progress/{book_id}", response_model=ProgressPutOut)
def put_progress(
    book_id: int,
    payload: ProgressPut,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProgressPutOut:
    book = require_visible_book(db, current_user, book_id)
    tracks = list(
        db.scalars(
            select(Track)
            .where(Track.book_id == book.id)
            .order_by(Track.disc_no, Track.track_no)
        )
    )
    if not tracks:
        raise HTTPException(status_code=400, detail="该书没有可播放的轨道")

    total = book.total_duration_sec or 0.0
    if payload.position_sec > total + POSITION_SLACK_SEC:
        raise HTTPException(status_code=400, detail="position_sec 超过书籍总时长")

    offsets = track_start_offsets(tracks)
    track_id = (
        payload.track_id
        if payload.track_id in offsets
        else locate_track(offsets, tracks, payload.position_sec)
    )

    old_row = db.get(Progress, (current_user.id, book.id))
    old_position = old_row.position_sec if old_row is not None else None
    old_state = (
        ProgressState(
            position_sec=old_row.position_sec,
            track_id=old_row.track_id,
            client_updated_at=old_row.client_updated_at or 0,
        )
        if old_row is not None
        else None
    )
    now = now_ts()
    decision = merge_progress(
        old_state,
        ProgressState(
            position_sec=payload.position_sec,
            track_id=track_id,
            client_updated_at=payload.client_updated_at,
        ),
        server_now=now,
        explicit_seek=payload.explicit_seek,
    )

    if decision.accepted:
        row = old_row
        if row is None:
            row = Progress(user_id=current_user.id, book_id=book.id)
            db.add(row)
        row.position_sec = decision.position_sec
        row.track_id = decision.track_id
        row.track_position_sec = track_position(
            decision.position_sec, offsets.get(decision.track_id, 0.0)
        )
        row.playback_rate = payload.playback_rate
        row.device_id = payload.device_id
        row.client_updated_at = decision.client_updated_at
        row.is_finished = payload.finished or (
            total > 0 and decision.position_sec >= total - FINISH_TOLERANCE_SEC
        )
        row.updated_at = now
        # 位置差异超过阈值才新增回溯点，阈值内只刷新最新一条
        record_checkpoint(
            db,
            user_id=current_user.id,
            book_id=book.id,
            position_sec=decision.position_sec,
            track_id=decision.track_id,
            device_id=payload.device_id,
            total_duration_sec=total,
            now=now,
        )
        # 收听统计：只有自然播放推进才算，拖动/跳章不计
        if old_position is not None:
            record_listening(
                db,
                user_id=current_user.id,
                seconds=listened_seconds(
                    previous=old_position,
                    current=decision.position_sec,
                    playback_rate=payload.playback_rate,
                    explicit_seek=payload.explicit_seek,
                ),
                now=now,
            )
        db.commit()
        db.refresh(row)
    else:
        row = old_row
        assert row is not None  # 拒绝必然存在旧记录

    return ProgressPutOut(
        book_id=book.id,
        position_sec=row.position_sec,
        track_id=row.track_id,
        accepted=decision.accepted,
        is_finished=row.is_finished,
        updated_at=row.updated_at,
    )


@router.delete("/progress/{book_id}", status_code=204)
def delete_progress(
    book_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    book = require_visible_book(db, current_user, book_id)
    row = db.get(Progress, (current_user.id, book.id))
    if row is not None:
        db.delete(row)
    db.execute(
        delete(ProgressHistory).where(
            ProgressHistory.user_id == current_user.id,
            ProgressHistory.book_id == book.id,
        )
    )
    db.commit()
    return Response(status_code=204)


@router.get("/progress/{book_id}/history", response_model=ProgressHistoryList)
def list_progress_history(
    book_id: int,
    limit: int = Query(HISTORY_LIMIT, ge=1, le=HISTORY_LIMIT),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProgressHistoryList:
    """该账号在这本书上的最近回溯点（最多 3 条，新→旧）。"""
    book = require_visible_book(db, current_user, book_id)
    rows = db.scalars(
        select(ProgressHistory)
        .where(
            ProgressHistory.user_id == current_user.id,
            ProgressHistory.book_id == book.id,
        )
        .order_by(ProgressHistory.created_at.desc(), ProgressHistory.id.desc())
        .limit(limit)
    ).all()
    return ProgressHistoryList(
        items=[
            ProgressHistoryItem(
                id=row.id,
                position_sec=row.position_sec,
                track_id=row.track_id,
                device_id=row.device_id,
                created_at=row.created_at,
            )
            for row in rows
        ]
    )
