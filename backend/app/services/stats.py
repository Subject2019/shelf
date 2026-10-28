"""收听统计的累计与汇总。

数据来源就是 `PUT /progress`：每次进度被接受时，用「新位置 - 旧位置」
估算这段时间听了多少。规则：

- `explicit_seek=True`（用户拖进度条 / 跳章）不算收听
- 位置倒退不算
- 单次最多计 10 分钟，防止离线设备补传时把大段空白算进去
- 播放倍速 1.5× 时，10 分钟进度只等于约 6.7 分钟真实收听时间，所以除以倍速
"""

from __future__ import annotations

import time
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ListeningDaily

MAX_REPORT_SEC = 600.0
DEFAULT_DAYS = 7


def day_key(ts: int | None = None) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(ts) if ts else time.localtime())


def listened_seconds(
    *,
    previous: float,
    current: float,
    playback_rate: float | None,
    explicit_seek: bool,
) -> float:
    """这次上报折算成多少「真实收听秒数」。"""
    if explicit_seek:
        return 0.0
    delta = current - previous
    if delta <= 0:
        return 0.0

    rate = playback_rate if playback_rate and playback_rate > 0 else 1.0
    return min(delta, MAX_REPORT_SEC) / rate


def record_listening(
    db: Session,
    *,
    user_id: int,
    seconds: float,
    now: int | None = None,
) -> ListeningDaily | None:
    """把一段收听时长累加到「今天」。不足 1 秒不入账。"""
    if seconds < 1:
        return None

    stamp = now if now is not None else int(time.time())
    day = day_key(stamp)
    row = db.get(ListeningDaily, (user_id, day))
    if row is None:
        row = ListeningDaily(user_id=user_id, day=day, seconds=0, updated_at=stamp)
        db.add(row)
    row.seconds += int(round(seconds))
    row.updated_at = stamp
    return row


def collect_stats(
    db: Session,
    *,
    user_id: int,
    days: int = DEFAULT_DAYS,
    now: int | None = None,
) -> dict:
    """返回今日秒数、累计秒数、连续天数与最近 N 天明细（升序）。"""
    today = date.fromtimestamp(now if now is not None else time.time())
    window = [today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]
    keys = [item.isoformat() for item in window]

    rows = db.execute(
        select(ListeningDaily.day, ListeningDaily.seconds).where(
            ListeningDaily.user_id == user_id,
            ListeningDaily.day.in_(keys),
        )
    ).all()
    by_day = {day: int(seconds or 0) for day, seconds in rows}

    total = db.scalar(
        select(func.sum(ListeningDaily.seconds)).where(
            ListeningDaily.user_id == user_id
        )
    )
    active_days = set(
        db.scalars(
            select(ListeningDaily.day).where(
                ListeningDaily.user_id == user_id,
                ListeningDaily.seconds > 0,
            )
        )
    )

    # 今天还没听不算断签，从昨天往前数
    cursor = today if today.isoformat() in active_days else today - timedelta(days=1)
    streak = 0
    while cursor.isoformat() in active_days:
        streak += 1
        cursor -= timedelta(days=1)

    return {
        "today_sec": by_day.get(today.isoformat(), 0),
        "total_sec": int(total or 0),
        "streak_days": streak,
        "days": [{"day": key, "seconds": by_day.get(key, 0)} for key in keys],
    }
