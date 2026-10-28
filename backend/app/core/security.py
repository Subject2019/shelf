"""密码哈希、JWT 签发校验与当前用户依赖。

密码用 argon2id；JWT 用 HS256 + 32 字节随机密钥，密钥首次启动生成到
`data/config/secret.key`（docs/ARCHITECTURE.md §4），不写进代码与环境模板。
"""

from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass
from functools import lru_cache

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models import Device, User

JWT_ALGORITHM = "HS256"

_password_hasher = PasswordHasher()
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


@lru_cache
def get_secret_key() -> str:
    """读 secret.key，不存在则生成。容器重建后保留该文件用户无需重新登录。"""
    settings = get_settings()
    path = settings.secret_key_path
    if path.exists():
        key = path.read_text(encoding="utf-8").strip()
        if key:
            return key

    key = secrets.token_urlsafe(48)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(key, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return key


@dataclass(frozen=True, slots=True)
class AccessClaims:
    user_id: int
    # 绑定设备后，踢下线可以让该 access token 立即失效
    device_id: str | None = None


def create_access_token(user_id: int, device_id: str | None = None) -> tuple[str, int]:
    """返回 (token, expires_in_sec)。带 device_id 时写入 `did` 声明。"""
    ttl = get_settings().access_token_ttl_sec
    now = int(time.time())
    payload: dict[str, object] = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + ttl,
        "typ": "access",
    }
    if device_id:
        payload["did"] = device_id
    token = jwt.encode(payload, get_secret_key(), algorithm=JWT_ALGORITHM)
    return token, ttl


def decode_access_claims(token: str) -> AccessClaims | None:
    try:
        payload = jwt.decode(token, get_secret_key(), algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("typ") != "access":
        return None
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        return None
    device_id = payload.get("did")
    return AccessClaims(
        user_id=user_id, device_id=device_id if isinstance(device_id, str) else None
    )


def decode_access_token(token: str) -> int | None:
    claims = decode_access_claims(token)
    return claims.user_id if claims is not None else None


def create_stream_token(
    user_id: int, book_id: int, ttl_sec: int = 6 * 3600
) -> tuple[str, int]:
    """签发只能访问单本书音频流的令牌，供 <audio src> 这类无法带头的场景使用。"""
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "bid": book_id,
        "typ": "stream",
        "iat": now,
        "exp": now + ttl_sec,
    }
    token = jwt.encode(payload, get_secret_key(), algorithm=JWT_ALGORITHM)
    return token, ttl_sec


def decode_stream_token(token: str, book_id: int) -> int | None:
    try:
        payload = jwt.decode(token, get_secret_key(), algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("typ") != "stream" or payload.get("bid") != book_id:
        return None
    try:
        return int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        return None


def new_refresh_token() -> tuple[str, str]:
    """返回 (明文, sha256)。明文只回给客户端，库里只存哈希。"""
    plain = secrets.token_urlsafe(48)
    return plain, hash_refresh_token(plain)


def hash_refresh_token(plain: str) -> str:
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail="未登录或登录已过期",
        headers={"WWW-Authenticate": "Bearer"},
    )


# 每个请求都写 last_seen_at 代价太高，最多每 60 秒更新一次
_LAST_SEEN_THROTTLE_SEC = 60


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise _unauthorized()
    claims = decode_access_claims(credentials.credentials)
    if claims is None:
        raise _unauthorized()
    user = db.get(User, claims.user_id)
    if user is None or not user.is_active:
        raise _unauthorized()

    if claims.device_id:
        device = db.get(Device, claims.device_id)
        # 设备不存在 / 不属于该用户 / 已被踢下线，一律视为未登录
        if device is None or device.user_id != user.id or device.revoked_at is not None:
            raise _unauthorized()
        now = int(time.time())
        stale = (
            device.last_seen_at is None
            or now - device.last_seen_at >= _LAST_SEEN_THROTTLE_SEC
        )
        if stale or device.offline_at is not None:
            device.last_seen_at = now
            # 又有请求了（例如重新打开页面），自动恢复在线
            device.offline_at = None
            db.commit()
    return user
