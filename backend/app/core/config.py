"""应用配置。

所有路径来自环境变量，代码中不假设 NAS 的挂载点，满足 AGENTS.md 架构红线第 1 条。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_NAME = "shelf"
APP_VERSION = "0.2.9"
APP_AUTHOR = "subject"

# 源码布局下指向项目根；容器内 /app/app/core/config.py 解析为 /，即 /data 与 /audiobooks。
# 两种场景都无需在代码里写死 NAS 挂载点，实际路径始终可被环境变量覆盖。
_LAYOUT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../deploy/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    audiobooks_path: Path = Field(
        default=_LAYOUT_ROOT / "audiobooks",
        validation_alias=AliasChoices("AUDIOBOOKS_PATH", "ECHOSHELF_AUDIOBOOKS_PATH"),
    )
    data_path: Path = Field(
        default=_LAYOUT_ROOT / "data",
        validation_alias=AliasChoices("ECHOSHELF_DATA_PATH", "DATA_PATH"),
    )
    # 前端构建产物目录（容器内默认 /web/dist，源码布局下是 <repo>/web/dist）
    web_dist_path: Path = Field(
        default=_LAYOUT_ROOT / "web" / "dist",
        validation_alias=AliasChoices("ECHOSHELF_WEB_DIST_PATH", "WEB_DIST_PATH"),
    )
    host: str = Field(
        default="0.0.0.0", validation_alias=AliasChoices("ECHOSHELF_HOST", "HOST")
    )
    port: int = Field(
        default=8080, validation_alias=AliasChoices("ECHOSHELF_PORT", "PORT")
    )
    log_level: str = Field(
        default="info",
        validation_alias=AliasChoices("ECHOSHELF_LOG_LEVEL", "LOG_LEVEL"),
    )
    enable_transcode: bool = Field(
        default=True, validation_alias=AliasChoices("ECHOSHELF_ENABLE_TRANSCODE")
    )
    # 按章节切片缓存（供安卓/第三方客户端离线下载，WebUI 不使用）
    enable_chapter_cache: bool = Field(
        default=True, validation_alias=AliasChoices("ECHOSHELF_ENABLE_CHAPTER_CACHE")
    )
    chapter_cache_max_bytes: int = Field(
        default=2 * 1024**3,
        validation_alias=AliasChoices("ECHOSHELF_CHAPTER_CACHE_MAX_BYTES"),
    )
    # 单次切片的最长耗时，防止异常文件卡住请求
    chapter_slice_timeout: int = Field(
        default=120, validation_alias=AliasChoices("ECHOSHELF_CHAPTER_SLICE_TIMEOUT")
    )
    # 整轨转码（wma/ape 等浏览器不支持的格式）缓存上限与单次超时
    transcode_max_bytes: int = Field(
        default=4 * 1024**3,
        validation_alias=AliasChoices("ECHOSHELF_TRANSCODE_MAX_BYTES"),
    )
    transcode_timeout: int = Field(
        default=1800,
        validation_alias=AliasChoices("ECHOSHELF_TRANSCODE_TIMEOUT"),
    )
    # 单轨转码时长上限（秒）。超长整轨同步转码会让请求挂几十分钟，
    # 超过此值请改用按章节切片（/chapters/{idx}/cache）；0 表示不限制。
    transcode_max_duration_sec: int = Field(
        default=7200,
        validation_alias=AliasChoices("ECHOSHELF_TRANSCODE_MAX_DURATION_SEC"),
    )
    allow_registration: bool = Field(
        default=False, validation_alias=AliasChoices("ECHOSHELF_ALLOW_REGISTRATION")
    )
    # 管理员只能带外创建：容器用这两个环境变量（仅在库为空时生效）
    admin_username: str = Field(
        default="admin", validation_alias=AliasChoices("ECHOSHELF_ADMIN_USERNAME")
    )
    admin_password: str | None = Field(
        default=None, validation_alias=AliasChoices("ECHOSHELF_ADMIN_PASSWORD")
    )
    # 更安全：把密码放文件（Docker secret），避免出现在 docker inspect
    admin_password_file: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ECHOSHELF_ADMIN_PASSWORD_FILE"),
    )
    # 显式开启后，每次启动把环境变量里的密码同步到唯一管理员
    # （默认关闭：避免改完网页密码后被旧环境变量悄悄覆盖）
    admin_sync_password: bool = Field(
        default=False,
        validation_alias=AliasChoices("ECHOSHELF_ADMIN_SYNC_PASSWORD"),
    )
    scan_virtual_chapter_min: int = Field(
        default=15, validation_alias=AliasChoices("ECHOSHELF_SCAN_VIRTUAL_CHAPTER_MIN")
    )
    # access token 30 分钟、refresh token 30 天（见 docs/ARCHITECTURE.md §3.4）
    access_token_ttl_sec: int = 1800
    refresh_token_ttl_sec: int = 30 * 24 * 3600
    # 小于该体积的音频视为残留/广告（docs/AUDIO_FORMATS.md §4）
    scan_min_size_bytes: int = Field(
        default=100 * 1024,
        validation_alias=AliasChoices("ECHOSHELF_SCAN_MIN_SIZE_BYTES"),
    )

    # ---- 派生路径：运行时产物统一落在 data_path 下，媒体目录只读 ----
    @property
    def db_path(self) -> Path:
        return self.data_path / "config" / "echoshelf.db"

    @property
    def secret_key_path(self) -> Path:
        return self.data_path / "config" / "secret.key"

    @property
    def covers_dir(self) -> Path:
        return self.data_path / "cache" / "covers"

    @property
    def transcode_cache_dir(self) -> Path:
        return self.data_path / "cache" / "transcode"

    @property
    def chapter_cache_dir(self) -> Path:
        """按章节切片的缓存根目录，按 book_id 分子目录。"""
        return self.data_path / "cache" / "chapters"

    @property
    def logs_dir(self) -> Path:
        return self.data_path / "logs"

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.db_path}"

    def ensure_dirs(self) -> None:
        """启动自检：确保可写目录存在。不触碰 audiobooks_path。"""
        for path in (
            self.db_path.parent,
            self.covers_dir,
            self.transcode_cache_dir,
            self.chapter_cache_dir,
            self.logs_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
