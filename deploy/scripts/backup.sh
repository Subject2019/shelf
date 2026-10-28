#!/usr/bin/env bash
# EchoShelf 在线备份脚本
#
# 用法：
#   ./backup.sh [/备份输出目录]
#   KEEP=14 ./backup.sh /volume1/backups
#
# 依赖：docker compose、tar。SQLite 备份使用 Python 的在线 backup API（镜像内自带），
# 不需要安装 sqlite3 CLI，也不会因写入而产生不一致快照。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_DIR="${1:-$COMPOSE_DIR/backups}"
KEEP="${KEEP:-7}"
STAMP="$(date +%Y%m%d-%H%M%S)"
CONTAINER="${SHELF_CONTAINER:-${ECHOSHELF_CONTAINER:-shelf}}"

mkdir -p "$BACKUP_DIR"

echo "[1/4] 在线备份数据库..."
docker exec -i "$CONTAINER" python - <<'PY'
import sqlite3
src = sqlite3.connect("/data/config/echoshelf.db")
dst = sqlite3.connect("/data/config/.backup-tmp.db")
with dst:
    src.backup(dst)
dst.close()
src.close()
print("db backup ok")
PY

echo "[2/4] 从容器导出 db 与密钥..."
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
docker cp "$CONTAINER:/data/config/.backup-tmp.db" "$TMP_DIR/echoshelf.db"
docker cp "$CONTAINER:/data/config/secret.key"   "$TMP_DIR/secret.key" 2>/dev/null || echo "  (无 secret.key，跳过)"
docker exec -i "$CONTAINER" rm -f /data/config/.backup-tmp.db

echo "[3/4] 打包 -> $BACKUP_DIR/shelf-$STAMP.tar.gz"
tar -czf "$BACKUP_DIR/shelf-$STAMP.tar.gz" -C "$TMP_DIR" .

echo "[4/4] 清理旧备份（保留最近 $KEEP 份）..."
ls -1t "$BACKUP_DIR"/{shelf,echoshelf}-*.tar.gz 2>/dev/null | tail -n +"$((KEEP + 1))" | xargs -r rm -f

echo "完成：$BACKUP_DIR/shelf-$STAMP.tar.gz"
echo
echo "恢复：deploy/scripts/restore.sh $BACKUP_DIR/shelf-$STAMP.tar.gz"
echo "  （会先停容器、把当前库留底为 echoshelf.db.before-restore-<时间>，再解包并等健康检查）"
