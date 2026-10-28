"""系统级接口（健康检查等）。

容器 healthcheck 依赖 `/health`，因此探测失败时返回 503 而非 200。
"""

from __future__ import annotations

import shutil
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import inspect, text

from app.core.config import APP_VERSION, get_settings
from app.db.session import get_engine
from app.schemas.health import HealthResponse, TranscodeStats
from app.services import transcode as transcode_service

router = APIRouter(tags=["system"])


def _probe_db() -> bool:
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 - 健康检查不允许因单个探测异常而中断
        return False


def _count_rows(table: str) -> int:
    """表尚未迁移时返回 0，让骨架阶段也能通过健康检查。"""
    engine = get_engine()
    try:
        if table not in inspect(engine).get_table_names():
            return 0
        with engine.connect() as connection:
            return int(
                connection.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
            )
    except Exception:  # noqa: BLE001
        return 0


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    db_ok = await run_in_threadpool(_probe_db)
    if not db_ok:
        raise HTTPException(status_code=503, detail="数据库不可用")

    libraries = await run_in_threadpool(_count_rows, "libraries")
    books = await run_in_threadpool(_count_rows, "books")
    started_at: float | None = getattr(request.app.state, "started_at", None)

    return HealthResponse(
        status="ok",
        version=APP_VERSION,
        db="ok",
        ffmpeg=shutil.which("ffmpeg") is not None,
        libraries=libraries,
        books=books,
        uptime_sec=int(time.monotonic() - started_at) if started_at else 0,
        transcode=TranscodeStats(
            enabled=get_settings().enable_transcode,
            **transcode_service.stats(),
        ),
    )
