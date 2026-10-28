"""收听统计接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.stats import DayStat, StatsOut
from app.services.stats import DEFAULT_DAYS, collect_stats

router = APIRouter(tags=["stats"])


@router.get("/stats", response_model=StatsOut)
def get_stats(
    days: int = Query(DEFAULT_DAYS, ge=1, le=30),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StatsOut:
    """今日 / 累计 / 连续天数 + 最近 N 天明细（升序，缺失的日子补 0）。"""
    data = collect_stats(db, user_id=current_user.id, days=days)
    return StatsOut(
        today_sec=data["today_sec"],
        total_sec=data["total_sec"],
        streak_days=data["streak_days"],
        days=[DayStat(**item) for item in data["days"]],
    )
