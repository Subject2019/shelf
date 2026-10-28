"""shelf 应用入口。

启动顺序：加载配置 → 建可写目录 → 初始化日志 → 就绪。媒体目录不在此阶段访问。
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.core.config import APP_AUTHOR, APP_NAME, APP_VERSION, Settings, get_settings
from app.core.logging import setup_logging
from app.core.security import hash_password, verify_password
from app.db.base import now_ts
from app.db.session import dispose_engine, get_session_factory
from app.models import RefreshToken, User
from app.workers.scan_worker import ScanWorker

logger = logging.getLogger(__name__)

_ERROR_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    413: "payload_too_large",
    422: "validation_error",
    429: "too_many_requests",
    500: "internal_error",
    501: "not_implemented",
    503: "service_unavailable",
}


def _error_body(code: str, message: str, details: Any = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details}}


def _resolve_admin_password(settings: Settings) -> str | None:
    """优先读 *_FILE（Docker secret），其次读环境变量。"""
    if settings.admin_password_file:
        try:
            value = (
                Path(settings.admin_password_file).read_text(encoding="utf-8").strip()
            )
            return value or None
        except OSError:
            logger.warning(
                "读取 ECHOSHELF_ADMIN_PASSWORD_FILE 失败：%s",
                settings.admin_password_file,
            )
            return None
    return settings.admin_password


def _sync_admin_password(session, password: str | None) -> None:
    """ECHOSHELF_ADMIN_SYNC_PASSWORD=true 时，让环境变量成为管理员密码的事实来源。

    只改唯一的管理员；密码没变则什么都不做，避免每次重启都吊销会话。
    """
    if not password:
        logger.warning(
            "ECHOSHELF_ADMIN_SYNC_PASSWORD=true 但没有提供管理员密码，跳过同步"
        )
        return
    if len(password) < 8:
        logger.error("同步管理员密码失败：密码少于 8 位")
        return

    admin = session.scalar(select(User).where(User.role == "admin").order_by(User.id))
    if admin is None:
        return
    if verify_password(admin.password_hash, password):
        return

    admin.password_hash = hash_password(password)
    now = now_ts()
    for token in session.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == admin.id, RefreshToken.revoked_at.is_(None)
        )
    ):
        token.revoked_at = now
    session.commit()
    logger.info(
        "已按 ECHOSHELF_ADMIN_SYNC_PASSWORD 更新管理员 %s 的密码，旧会话已失效",
        admin.username,
    )


def _ensure_initial_admin(settings: Settings) -> None:
    """仅在「库里一个用户都没有」时按环境变量创建管理员。

    管理员不再允许从网页创建；已存在管理员时绝不覆盖密码。
    裸机部署用 `echoshelf admin create` / `admin reset-password`。
    """
    password = _resolve_admin_password(settings)
    username = (settings.admin_username or "admin").strip().lower() or "admin"
    try:
        with get_session_factory()() as session:
            total = session.scalar(select(func.count()).select_from(User)) or 0
            if total:
                admins = (
                    session.scalar(
                        select(func.count())
                        .select_from(User)
                        .where(User.role == "admin")
                    )
                    or 0
                )
                if not admins:
                    logger.warning(
                        "当前没有任何管理员：请执行 `python -m app.cli admin create`"
                    )
                elif settings.admin_sync_password:
                    _sync_admin_password(session, password)
                return
            if not password:
                logger.warning(
                    "数据库为空且未设置 ECHOSHELF_ADMIN_PASSWORD(_FILE)；"
                    "请在容器环境变量里设置，或执行 `python -m app.cli admin create`"
                )
                return
            if len(password) < 8:
                logger.error("管理员密码少于 8 位，拒绝创建")
                return
            session.add(
                User(
                    username=username,
                    password_hash=hash_password(password),
                    display_name="管理员",
                    role="admin",
                    created_at=now_ts(),
                )
            )
            session.commit()
        logger.info("已按环境变量创建初始管理员：%s", username)
    except Exception:  # noqa: BLE001 - 迁移未执行时不要阻塞启动
        logger.warning("跳过初始管理员创建：数据库可能尚未迁移", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.ensure_dirs()
    setup_logging(settings)
    _ensure_initial_admin(settings)
    app.state.started_at = time.monotonic()
    app.state.scan_worker = ScanWorker()
    app.state.scan_worker.start()
    logger.info(
        "shelf 启动",
        extra={
            "extra_fields": {
                "version": APP_VERSION,
                "data_path": str(settings.data_path),
                "audiobooks_path": str(settings.audiobooks_path),
            }
        },
    )
    try:
        yield
    finally:
        app.state.scan_worker.stop()
        dispose_engine()
        logger.info("shelf 已停止")


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    contact={"name": APP_AUTHOR},
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)
app.include_router(api_router, prefix="/api/v1")


def _mount_web(app: FastAPI, settings: Settings) -> None:
    """托管前端构建产物（容器内单进程部署）。

    源码布局下 dist 可能不存在（前端跑 vite dev），此时只提供 API。
    """
    dist = settings.web_dist_path
    index = dist / "index.html"
    if not index.is_file():
        logger.info("未找到前端产物，仅提供 API：%s", dist)
        return

    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    root = dist.resolve()

    # 同时接受 HEAD：健康检查/反向代理常用 HEAD 探测首页
    @app.api_route(
        "/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False
    )
    async def spa_fallback(full_path: str) -> FileResponse:
        # /api 下没匹配到路由的路径仍然返回 JSON 404，不能落到 index.html
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="接口不存在")

        if full_path:
            candidate = (root / full_path).resolve()
            # 静态文件优先，且禁止 ../ 越界
            if candidate.is_file() and candidate.is_relative_to(root):
                return FileResponse(candidate)
        # 其余交给前端路由（/library、/books/1、/player …）
        return FileResponse(index)


_mount_web(app, get_settings())


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    _: Request, exc: StarletteHTTPException
) -> JSONResponse:
    code = _ERROR_CODES.get(exc.status_code, "error")
    message = exc.detail if isinstance(exc.detail, str) else "请求失败"
    details: Any = None
    # 端点需要更精确的 error.code 时（如 transcode_unavailable）可传 dict
    if isinstance(exc.detail, dict):
        code = str(exc.detail.get("code", code))
        message = str(exc.detail.get("message", message))
        details = exc.detail.get("details")
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(code, message, details),
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=_error_body(
            "validation_error", "参数校验失败", jsonable_encoder(exc.errors())
        ),
    )
