#!/usr/bin/env bash
# EchoShelf 备份恢复脚本
#
# 用法：
#   ./restore.sh <备份文件.tar.gz> [--yes]
#   SHELF_CONTAINER=shelf ./restore.sh backup/shelf-20261026-021500.tar.gz --yes
#
# 行为：
#   1. 校验归档只含 echoshelf.db / secret.key，拒绝绝对路径与 ..
#   2. 停容器（保留当前库的副本 echoshelf.db.before-restore-<时间>）
#   3. 解包到容器的 /data 挂载点 config/
#   4. 启动容器并等待健康检查，打印恢复后的行数
#
# 与 backup.sh 配对使用；归档内是 `./echoshelf.db` 与 `./secret.key`。
set -euo pipefail

log() { printf '\033[1;32m[restore]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[restore]\033[0m %s\n' "$*" >&2; }
die() { printf '\033[1;31m[restore]\033[0m %s\n' "$*" >&2; exit 1; }

ARCHIVE=""
ASSUME_YES=0
CONTAINER="${SHELF_CONTAINER:-${ECHOSHELF_CONTAINER:-shelf}}"
DATA_DIR="${ECHOSHELF_DATA_PATH:-}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --yes|-y) ASSUME_YES=1; shift ;;
        --container) CONTAINER="$2"; shift 2 ;;
        --data-dir) DATA_DIR="$2"; shift 2 ;;
        -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
        -*) die "未知参数：$1" ;;
        *) ARCHIVE="$1"; shift ;;
    esac
done

[[ -n "$ARCHIVE" ]] || die "缺少备份文件参数（--help 查看用法）"
[[ -f "$ARCHIVE" ]] || die "备份文件不存在：$ARCHIVE"
command -v docker >/dev/null || die "需要 docker"

# ---------------------------------------------------------------- 归档校验
log "校验归档：$ARCHIVE"
ENTRIES="$(tar -tzf "$ARCHIVE")"
[[ -n "$ENTRIES" ]] || die "归档为空"
if printf '%s\n' "$ENTRIES" | grep -qE '^/|(^|/)\.\.(/|$)'; then
    die "归档包含绝对路径或 ..，拒绝恢复"
fi
printf '%s\n' "$ENTRIES" | grep -qxE '(\./)?echoshelf\.db' \
    || die "归档里没有 echoshelf.db，不是 shelf 备份"
if printf '%s\n' "$ENTRIES" | grep -qE '(\./)?secret\.key'; then
    HAS_SECRET=1
else
    HAS_SECRET=0
    warn "归档没有 secret.key：已登录会话在恢复后需要重新登录"
fi

# ---------------------------------------------------------------- 定位数据目录
if [[ -z "$DATA_DIR" ]]; then
    DATA_DIR="$(docker inspect "$CONTAINER" --format '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Source}}{{end}}{{end}}' 2>/dev/null || true)"
fi
[[ -n "$DATA_DIR" ]] || die "无法确定 /data 挂载点，请用 --data-dir 指定（容器名：$CONTAINER）"
[[ -d "$DATA_DIR" ]] || die "数据目录不存在：$DATA_DIR"
log "容器：$CONTAINER"
log "数据目录：$DATA_DIR"

if [[ "$ASSUME_YES" != "1" ]]; then
    printf '将用备份覆盖 %s/config/echoshelf.db，确认？[y/N] ' "$DATA_DIR"
    read -r answer
    [[ "$answer" =~ ^[Yy]$ ]] || die "已取消"
fi

# ---------------------------------------------------------------- 停服并保护现状
BEFORE="$DATA_DIR/config/echoshelf.db.before-restore-$(date +%Y%m%d-%H%M%S)"
if docker inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null | grep -q true; then
    log "停止容器：$CONTAINER"
    docker stop -t 20 "$CONTAINER" >/dev/null
    STOPPED=1
else
    warn "容器 $CONTAINER 未在运行，直接恢复文件"
    STOPPED=0
fi

if [[ -f "$DATA_DIR/config/echoshelf.db" ]]; then
    cp -a "$DATA_DIR/config/echoshelf.db" "$BEFORE"
    log "当前库已留底：$BEFORE"
fi

# ---------------------------------------------------------------- 解包
log "解包到 $DATA_DIR/config/"
mkdir -p "$DATA_DIR/config"
tar -xzf "$ARCHIVE" -C "$DATA_DIR/config/"
[[ "$HAS_SECRET" == "1" ]] || true

# 容器入口会 chown -R /data，这里只保证可读
chmod 600 "$DATA_DIR/config/echoshelf.db" 2>/dev/null || true

if command -v sqlite3 >/dev/null; then
    sqlite3 "$DATA_DIR/config/echoshelf.db" 'PRAGMA integrity_check;' \
        | grep -qx ok || warn "integrity_check 未通过，请人工确认备份来源"
fi

# ---------------------------------------------------------------- 起服并验证
if [[ "$STOPPED" == "1" ]]; then
    log "启动容器：$CONTAINER"
    docker start "$CONTAINER" >/dev/null
else
    log "请手动启动容器后再确认健康"
fi

log "等待健康检查（最多 40 秒）"
for _ in $(seq 1 20); do
    sleep 2
    if docker exec "$CONTAINER" python -c "
import urllib.request, sys
try:
    r = urllib.request.urlopen('http://127.0.0.1:8080/api/v1/health', timeout=3)
    sys.exit(0 if r.status == 200 else 1)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
        log "健康检查通过"
        docker exec -i "$CONTAINER" python - <<'PY' 2>/dev/null || true
import sqlite3
conn = sqlite3.connect("/data/config/echoshelf.db")
for table in ("users", "libraries", "books", "progress", "bookmarks", "listening_daily"):
    try:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table:<16} {count}")
    except sqlite3.Error:
        pass
conn.close()
PY
        exit 0
    fi
done

warn "40 秒内未通过健康检查，请查看：docker logs --tail=50 $CONTAINER"
warn "回滚：docker stop $CONTAINER && cp -a '$BEFORE' '$DATA_DIR/config/echoshelf.db' && docker start $CONTAINER"
exit 1
