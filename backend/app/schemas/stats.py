"""收听统计响应模型。"""

from __future__ import annotations

from pydantic import BaseModel


class DayStat(BaseModel):
    day: str
    seconds: int


class StatsOut(BaseModel):
    today_sec: int
    total_sec: int
    streak_days: int
    days: list[DayStat]
