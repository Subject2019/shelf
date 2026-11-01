"""v1 路由汇总。新模块在此挂载，prefix 由 main 统一加 /api/v1。"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    auth,
    bookmarks,
    books,
    chapters,
    collections,
    devices,
    libraries,
    progress,
    stats,
    stream,
    system,
    users,
)

api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(auth.router)
api_router.include_router(libraries.router)
api_router.include_router(books.router)
api_router.include_router(collections.router)
api_router.include_router(chapters.router)
api_router.include_router(users.router)
api_router.include_router(devices.router)
api_router.include_router(progress.router)
api_router.include_router(stats.router)
api_router.include_router(bookmarks.router)
api_router.include_router(stream.router)
