"""账号进度检查点（回溯点）。

权威进度只有一条（`progress` 表主键 `user_id + book_id`）。这里额外记最多 3 个
「位置差异明显」的快照，用来在误拖、多设备互相覆盖之后找回之前听到的地方。

判定「差异明显」的阈值：`max(5 分钟, 总时长 3%)`，并封顶 30 分钟。

- 短篇（30 分钟）：5 分钟就算换了个地方
- 10 小时的长篇：18 分钟左右才算，避免每章都留一个点

阈值内的上报只**刷新**最近的那条快照（位置与时间跟着走），不新增行；
超出阈值则新增一行，并裁掉最旧的，始终最多 3 行。

「撤销误拖」会跳回原来的位置，此时与旧快照足够近，因此刷新旧快照而不是
再插一条几乎相同的记录。
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import ProgressHistory

HISTORY_LIMIT = 3
MIN_DELTA_SEC = 300.0
MAX_DELTA_SEC = 1800.0
DELTA_RATIO = 0.03


def history_delta(total_duration_sec: float | None) -> float:
    total = float(total_duration_sec or 0.0)
    return max(MIN_DELTA_SEC, min(MAX_DELTA_SEC, total * DELTA_RATIO))


def record_checkpoint(
    db: Session,
    *,
    user_id: int,
    book_id: int,
    position_sec: float,
    track_id: int | None,
    device_id: str | None,
    total_duration_sec: float | None,
    now: int,
) -> ProgressHistory:
    rows = list(
        db.scalars(
            select(ProgressHistory)
            .where(
                ProgressHistory.user_id == user_id,
                ProgressHistory.book_id == book_id,
            )
            .order_by(ProgressHistory.created_at.desc(), ProgressHistory.id.desc())
            .limit(HISTORY_LIMIT)
        )
    )

    delta = history_delta(total_duration_sec)
    # 与**任意**已有检查点足够近就刷新那一条，而不是新增：
    # 否则「误拖出去再撤销回来」会在列表里留下两个几乎相同的位置。
    nearest = None
    for row in rows:
        if abs(row.position_sec - position_sec) >= delta:
            continue
        if nearest is None or abs(row.position_sec - position_sec) < abs(
            nearest.position_sec - position_sec
        ):
            nearest = row

    if nearest is not None:
        nearest.position_sec = position_sec
        nearest.track_id = track_id
        nearest.device_id = device_id
        nearest.created_at = now
        return nearest

    row = ProgressHistory(
        user_id=user_id,
        book_id=book_id,
        position_sec=position_sec,
        track_id=track_id,
        device_id=device_id,
        created_at=now,
    )
    db.add(row)
    db.flush()

    # 保留最新的 HISTORY_LIMIT-1 条旧快照 + 刚插入的一条
    keep = [item.id for item in rows[: HISTORY_LIMIT - 1]] + [row.id]
    db.execute(
        delete(ProgressHistory).where(
            ProgressHistory.user_id == user_id,
            ProgressHistory.book_id == book_id,
            ProgressHistory.id.notin_(keep),
        )
    )
    return row
