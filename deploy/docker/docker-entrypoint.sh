#!/bin/sh
# 容器入口：按 PUID/PGID 降权 → 跑迁移 → 启动应用
set -eu

DATA_DIR="${ECHOSHELF_DATA_PATH:-/data}"
MEDIA_DIR="${ECHOSHELF_AUDIOBOOKS_PATH:-/audiobooks}"
PUID="${PUID:-1000}"
PGID="${PGID:-1000}"

log() { echo "[echoshelf] $*"; }

RUN_UID=""
if [ "$(id -u)" = "0" ]; then
    # 组：优先复用已存在的 gid，否则新建
    if ! getent group "$PGID" >/dev/null 2>&1; then
        addgroup -g "$PGID" echoshelf 2>/dev/null || true
    fi
    GROUP_NAME="$(getent group "$PGID" | cut -d: -f1)"

    if ! getent passwd "$PUID" >/dev/null 2>&1; then
        adduser -D -H -u "$PUID" -G "$GROUP_NAME" echoshelf 2>/dev/null || true
    fi
    USER_NAME="$(getent passwd "$PUID" | cut -d: -f1)"

    mkdir -p "$DATA_DIR"
    current_owner="$(stat -c '%u:%g' "$DATA_DIR")"
    if [ "$current_owner" != "$PUID:$PGID" ]; then
        log "修正数据目录属主 $current_owner → $PUID:$PGID"
        chown -R "$PUID:$PGID" "$DATA_DIR" 2>/dev/null \
            || log "警告：chown 失败，请手动调整宿主机目录权限"
    fi
    [ -n "$USER_NAME" ] && RUN_UID="$PUID:$PGID"
else
    log "已以非 root 运行（uid=$(id -u)），跳过降权"
fi

run() {
    if [ -n "$RUN_UID" ]; then
        su-exec "$RUN_UID" "$@"
    else
        "$@"
    fi
}

log "数据目录：$DATA_DIR（uid:gid = $PUID:$PGID）"
log "媒体目录：$MEDIA_DIR"
log "执行数据库迁移（alembic upgrade head）"
run alembic upgrade head

log "启动应用：$*"
if [ -n "$RUN_UID" ]; then
    exec su-exec "$RUN_UID" "$@"
fi
exec "$@"
