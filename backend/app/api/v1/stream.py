"""音频流式接口：原文件 Range 直出 + 可选整轨转码。

- 默认：直接读原文件，支持 Range / HEAD
- `?transcode=opus|mp3&bitrate=64`：先转码到缓存，再按 Range 直出（wma/ape 等浏览器不支持时用）
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    bearer_scheme,
    decode_access_token,
    decode_stream_token,
    get_current_user,
)
from app.db.session import get_db
from app.models import Book, Library, MediaFile, Track, User
from app.schemas.book import TranscodeOut
from app.services import transcode as transcode_service
from app.services.permissions import can_view_library
from app.services.streamer import (
    ByteRange,
    RangeNotSatisfiable,
    content_type_for,
    iter_file_chunks,
    parse_range,
    resolve_media_path,
)
from app.services.transcode import TranscodeError

router = APIRouter(tags=["stream"])


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail="未登录或登录已过期",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _resolve_stream_user(
    book_id: int,
    token: str | None = Query(default=None, description="play-token 签发的流令牌"),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """<audio>/ExoPlayer 无法自定义请求头，因此 extra 支持 ?token= 的短时流令牌。"""
    if credentials and credentials.credentials:
        user_id = decode_access_token(credentials.credentials)
    elif token:
        user_id = decode_stream_token(token, book_id)
    else:
        raise _unauthorized()

    if user_id is None:
        raise _unauthorized()
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise _unauthorized()
    return user


def _load_track(
    db: Session, current_user: User, book_id: int, track_id: int
) -> tuple[Track, MediaFile, Path]:
    track = db.get(Track, track_id)
    if track is None or track.book_id != book_id:
        raise HTTPException(status_code=404, detail="轨道不存在")
    book = db.get(Book, book_id)
    if book is None or book.is_missing:
        raise HTTPException(status_code=404, detail="书籍不存在")
    library = db.get(Library, book.library_id)
    if library is None:
        raise HTTPException(status_code=404, detail="书籍不存在")
    if not can_view_library(db, current_user, library.id):
        raise HTTPException(status_code=403, detail="无权访问该书库")

    media = db.get(MediaFile, track.media_file_id)
    if media is None or media.is_missing:
        raise HTTPException(status_code=404, detail="音频文件不存在")

    path = resolve_media_path(library.root_path, media.rel_path)
    if path is None:
        raise HTTPException(status_code=404, detail="音频文件不存在")
    return track, media, path


def _base_headers() -> dict[str, str]:
    return {
        "Accept-Ranges": "bytes",
        "Cache-Control": "private, max-age=0, no-transform",
    }


def _range_headers(byte_range: ByteRange, file_size: int) -> dict[str, str]:
    headers = _base_headers()
    headers["Content-Range"] = f"bytes {byte_range.start}-{byte_range.end}/{file_size}"
    headers["Content-Length"] = str(byte_range.length)
    return headers


def _not_satisfiable(exc: RangeNotSatisfiable) -> Response:
    return Response(
        status_code=416,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Range": f"bytes */{exc.file_size}",
        },
    )


def _transcode_error(exc: TranscodeError) -> HTTPException:
    if exc.code in {"transcode_disabled", "ffmpeg_missing"}:
        status = 503
    elif exc.code in {"transcode_failed", "transcode_timeout"}:
        status = 502
    elif exc.code == "transcode_too_long":
        status = 413
    else:
        status = 400
    return HTTPException(
        status_code=status, detail={"code": exc.code, "message": exc.message}
    )


def _ensure_transcoded(
    *,
    book_id: int,
    track_id: int,
    source: Path,
    codec: str | None,
    bitrate: int | None,
    duration_sec: float | None = None,
) -> transcode_service.TranscodedAudio:
    settings = get_settings()
    try:
        name, rate = transcode_service.normalize(codec, bitrate)
        stat = source.stat()
        return transcode_service.ensure_transcoded(
            settings,
            book_id=book_id,
            track_id=track_id,
            source=source,
            mtime=int(stat.st_mtime),
            size=stat.st_size,
            codec=name,
            bitrate=rate,
            duration_sec=duration_sec,
        )
    except TranscodeError as exc:
        raise _transcode_error(exc) from exc


def _serve(
    request: Request,
    path: Path,
    media_type: str,
    extra_headers: dict[str, str] | None = None,
    head_only: bool = False,
) -> Response:
    file_size = path.stat().st_size
    try:
        byte_range = parse_range(request.headers.get("range"), file_size)
    except RangeNotSatisfiable as exc:
        return _not_satisfiable(exc)

    extra = extra_headers or {}

    if byte_range is None:
        headers = _base_headers()
        headers.update(extra)
        headers["Content-Length"] = str(file_size)
        if head_only:
            return Response(status_code=200, headers=headers, media_type=media_type)
        return StreamingResponse(
            iter_file_chunks(path, 0, file_size),
            status_code=200,
            media_type=media_type,
            headers=headers,
        )

    headers = _range_headers(byte_range, file_size)
    headers.update(extra)
    if head_only:
        return Response(status_code=206, headers=headers, media_type=media_type)
    return StreamingResponse(
        iter_file_chunks(path, byte_range.start, byte_range.length),
        status_code=206,
        media_type=media_type,
        headers=headers,
    )


@router.get("/books/{book_id}/tracks/{track_id}/stream")
def stream_track(
    book_id: int,
    track_id: int,
    request: Request,
    transcode: str | None = Query(default=None, description="opus / mp3"),
    bitrate: int | None = Query(default=None, ge=0, le=1024),
    current_user: User = Depends(_resolve_stream_user),
    db: Session = Depends(get_db),
) -> Response:
    track, media, path = _load_track(db, current_user, book_id, track_id)

    if transcode:
        audio = _ensure_transcoded(
            book_id=book_id,
            track_id=track_id,
            source=path,
            codec=transcode,
            bitrate=bitrate,
            duration_sec=track.duration_sec,
        )
        return _serve(
            request,
            audio.path,
            audio.content_type,
            {
                "X-Transcode": f"{audio.codec}/{audio.bitrate}",
                "X-Transcode-Cache": "hit" if not audio.created else "miss",
            },
        )

    media_type = content_type_for(media.format or path.suffix.lstrip("."))
    return _serve(request, path, media_type, {"X-Transcode-Cache": "off"})


@router.head("/books/{book_id}/tracks/{track_id}/stream")
def head_track(
    book_id: int,
    track_id: int,
    request: Request,
    transcode: str | None = Query(default=None),
    bitrate: int | None = Query(default=None, ge=0, le=1024),
    current_user: User = Depends(_resolve_stream_user),
    db: Session = Depends(get_db),
) -> Response:
    track, media, path = _load_track(db, current_user, book_id, track_id)

    if transcode:
        audio = _ensure_transcoded(
            book_id=book_id,
            track_id=track_id,
            source=path,
            codec=transcode,
            bitrate=bitrate,
            duration_sec=track.duration_sec,
        )
        return _serve(
            request,
            audio.path,
            audio.content_type,
            {
                "X-Transcode": f"{audio.codec}/{audio.bitrate}",
                "X-Transcode-Cache": "hit" if not audio.created else "miss",
            },
            head_only=True,
        )

    media_type = content_type_for(media.format or path.suffix.lstrip("."))
    return _serve(
        request, path, media_type, {"X-Transcode-Cache": "off"}, head_only=True
    )


@router.post(
    "/books/{book_id}/tracks/{track_id}/transcode", response_model=TranscodeOut
)
def prepare_transcode(
    book_id: int,
    track_id: int,
    codec: str = Query(default="opus", max_length=16),
    bitrate: int = Query(default=64, ge=0, le=1024),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TranscodeOut:
    """预生成转码文件，供客户端在播放前调用（避免首播等待）。"""
    track, _, path = _load_track(db, current_user, book_id, track_id)
    audio = _ensure_transcoded(
        book_id=book_id,
        track_id=track_id,
        source=path,
        codec=codec,
        bitrate=bitrate,
        duration_sec=track.duration_sec,
    )
    return TranscodeOut(
        track_id=track.id,
        codec=audio.codec,
        bitrate=audio.bitrate,
        bytes=audio.path.stat().st_size,
        content_type=audio.content_type,
        cache_key=audio.cache_key,
        duration_sec=track.duration_sec,
        created=audio.created,
    )
