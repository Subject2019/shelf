#!/usr/bin/env bash
# EchoShelf 卸载（常规部署）
#
#   sudo ./uninstall.sh                 # 停服务、删程序与配置，保留数据
#   sudo ./uninstall.sh --purge         # 连数据目录一起删（会二次确认）
set -euo pipefail

PREFIX=/opt/echoshelf
DATA_DIR=/var/lib/echoshelf
ENV_DIR=/etc/echoshelf
SERVICE_NAME=echoshelf
PURGE=0

log() { printf '\033[1;32m[echoshelf]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[echoshelf]\033[0m %s\n' "$*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --prefix) PREFIX="$2"; shift 2 ;;
        --data-dir) DATA_DIR="$2"; shift 2 ;;
        --env-dir) ENV_DIR="$2"; shift 2 ;;
        --service-name) SERVICE_NAME="$2"; shift 2 ;;
        --purge) PURGE=1; shift ;;
        -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
        *) die "未知参数：$1" ;;
    esac
done

if [[ "$(id -u)" != "0" && "$PREFIX" = /opt/* ]]; then
    die "卸载系统目录需要 root：sudo $0"
fi

if systemctl list-unit-files 2>/dev/null | grep -q "^$SERVICE_NAME.service"; then
    log "停止并禁用服务 $SERVICE_NAME"
    systemctl disable --now "$SERVICE_NAME" 2>/dev/null || true
    rm -f "/etc/systemd/system/$SERVICE_NAME.service"
    systemctl daemon-reload || true
fi

if [[ -d "$PREFIX" ]]; then
    log "删除程序目录 $PREFIX"
    rm -rf "$PREFIX"
fi

if [[ -d "$ENV_DIR" ]]; then
    log "删除配置目录 $ENV_DIR"
    rm -rf "$ENV_DIR"
fi

if [[ "$PURGE" = "1" ]]; then
    if [[ -d "$DATA_DIR" ]]; then
        printf '将永久删除数据目录 %s（数据库、封面、日志），确认？[y/N] ' "$DATA_DIR"
        read -r answer
        if [[ "$answer" =~ ^[Yy]$ ]]; then
            rm -rf "$DATA_DIR"
            log "已删除 $DATA_DIR"
        else
            log "保留数据目录 $DATA_DIR"
        fi
    fi
else
    log "数据目录保留在 $DATA_DIR（需要彻底清理时加 --purge）"
fi

log "卸载完成。媒体库目录不会被删除。"
