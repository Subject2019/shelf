"""健康检查响应契约，对应 docs/API.md 第 10 节。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class TranscodeStats(BaseModel):
    """转码占用情况，用来判断「现在有没有在转、转过多少」。"""

    enabled: bool
    active: int
    completed: int


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    db: Literal["ok", "error"]
    ffmpeg: bool
    libraries: int
    books: int
    uptime_sec: int
    transcode: TranscodeStats
