#!/usr/bin/env bash
# EchoShelf 常规部署（bare metal / NAS 自带 Linux）
#
# 在解压后的分发包根目录执行：
#   sudo ./install.sh                       # 装到 /opt/echoshelf + systemd
#   sudo ./install.sh --prefix /volume1/@appstore/echoshelf
#   ./install.sh --no-service --no-user     # 测试用：不建用户、不装 systemd
#
# 依赖：python3 ≥ 3.10、ffmpeg/ffprobe（转码用，缺失只告警）
set -euo pipefail

PREFIX=/opt/echoshelf
DATA_DIR=/var/lib/echoshelf
ENV_DIR=/etc/echoshelf
RUN_USER=echoshelf
PORT=8080
SERVICE_NAME=echoshelf
INSTALL_SERVICE=1
CREATE_USER=1
OFFLINE=0
SKIP_MIGRATE=0
AUDIOBOOKS_DIR=""
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() { printf '\033[1;32m[echoshelf]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[echoshelf]\033[0m %s\n' "$*" >&2; }
die() { printf '\033[1;31m[echoshelf]\033[0m %s\n' "$*" >&2; exit 1; }

usage() {
    cat <<'EOF'
用法: sudo ./install.sh [选项]

  --prefix DIR       安装目录（默认 /opt/echoshelf）
  --data-dir DIR     数据目录：DB/缓存/日志（默认 /var/lib/echoshelf）
  --audiobooks DIR   媒体库根目录（默认在安装后手动填）
  --env-dir DIR      配置文件目录（默认 /etc/echoshelf）
  --port PORT        HTTP 端口（默认 8080）
  --user NAME        运行身份（默认 echoshelf）
  --no-service       不安装/启动 systemd 服务
  --no-user          不创建系统用户（以当前用户运行）
  --offline          从包内 wheels/ 离线安装依赖
  --skip-migrate     跳过数据库迁移
  -h, --help         显示帮助
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --prefix) PREFIX="$2"; shift 2 ;;
        --data-dir) DATA_DIR="$2"; shift 2 ;;
        --audiobooks) AUDIOBOOKS_DIR="$2"; shift 2 ;;
        --env-dir) ENV_DIR="$2"; shift 2 ;;
        --port) PORT="$2"; shift 2 ;;
        --user) RUN_USER="$2"; shift 2 ;;
        --no-service) INSTALL_SERVICE=0; shift ;;
        --no-user) CREATE_USER=0; shift ;;
        --offline) OFFLINE=1; shift ;;
        --skip-migrate) SKIP_MIGRATE=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) die "未知参数：$1（--help 查看用法）" ;;
    esac
done

# ---------------------------------------------------------------- 前置检查
[[ -d "$SOURCE_DIR/app" ]] || die "找不到 app/，请在解压后的分发包根目录运行"
[[ -f "$SOURCE_DIR/web/dist/index.html" ]] || die "找不到 web/dist/index.html（包不完整）"
command -v python3 >/dev/null || die "缺少 python3"

PY_OK="$(python3 -c 'import sys; print(1 if sys.version_info >= (3, 10) else 0)')"
[[ "$PY_OK" = "1" ]] || die "需要 Python ≥ 3.10，当前：$(python3 -V)"

if command -v ffmpeg >/dev/null; then
    log "ffmpeg：$(ffmpeg -version 2>/dev/null | head -1 | cut -d' ' -f1-3)"
else
    warn "未找到 ffmpeg/ffprobe：转码与章节探测不可用（mp3/m4a/m4b 仍可播放）"
fi

if [[ "$OFFLINE" = "1" && ! -d "$SOURCE_DIR/wheels" ]]; then
    die "--offline 需要包内 wheels/ 目录（构建时加 --with-wheels）"
fi

IS_ROOT=0
[[ "$(id -u)" = "0" ]] && IS_ROOT=1
if [[ "$INSTALL_SERVICE" = "1" && "$IS_ROOT" != "1" ]]; then
    warn "非 root 无法安装 systemd 服务，自动改为前台运行模式"
    INSTALL_SERVICE=0
fi

# ---------------------------------------------------------------- 复制文件
log "安装到 $PREFIX（源码：$SOURCE_DIR）"
mkdir -p "$PREFIX" "$PREFIX/web"

# app 采用「先复制到临时目录再替换」，升级时不会残留旧文件
rm -rf "$PREFIX/app.new"
mkdir -p "$PREFIX/app.new"
cp -a "$SOURCE_DIR/app/." "$PREFIX/app.new/"
rm -rf "$PREFIX/app"
mv "$PREFIX/app.new" "$PREFIX/app"

rm -rf "$PREFIX/web/dist.new"
cp -a "$SOURCE_DIR/web/dist" "$PREFIX/web/dist.new"
rm -rf "$PREFIX/web/dist"
mv "$PREFIX/web/dist.new" "$PREFIX/web/dist"

# ---------------------------------------------------------------- Python 环境
if [[ ! -x "$PREFIX/venv/bin/python" ]]; then
    log "创建虚拟环境：$PREFIX/venv"
    python3 -m venv "$PREFIX/venv"
fi

PIP_ARGS=(install --no-cache-dir --disable-pip-version-check)
if [[ "$OFFLINE" = "1" ]]; then
    PIP_ARGS+=(--no-index --find-links "$SOURCE_DIR/wheels")
    log "离线安装依赖（wheels/）"
else
    log "安装依赖（联网，见 requirements-prod.txt）"
fi
"$PREFIX/venv/bin/pip" "${PIP_ARGS[@]}" -r "$PREFIX/app/requirements-prod.txt"

# ---------------------------------------------------------------- 目录与用户
mkdir -p "$DATA_DIR" "$ENV_DIR"
ENV_FILE="$ENV_DIR/echoshelf.env"

if [[ ! -f "$ENV_FILE" ]]; then
    log "生成配置：$ENV_FILE"
    MEDIA_LINE="${AUDIOBOOKS_DIR:-/srv/audiobooks}"
    sed \
        -e "s#^ECHOSHELF_DATA_PATH=.*#ECHOSHELF_DATA_PATH=$DATA_DIR#" \
        -e "s#^ECHOSHELF_AUDIOBOOKS_PATH=.*#ECHOSHELF_AUDIOBOOKS_PATH=$MEDIA_LINE#" \
        -e "s#^ECHOSHELF_WEB_DIST_PATH=.*#ECHOSHELF_WEB_DIST_PATH=$PREFIX/web/dist#" \
        -e "s#^ECHOSHELF_PORT=.*#ECHOSHELF_PORT=$PORT#" \
        "$SOURCE_DIR/echoshelf.env.example" > "$ENV_FILE"
else
    log "沿用已有配置：$ENV_FILE"
fi
chmod 640 "$ENV_FILE" 2>/dev/null || true
if [[ "$CREATE_USER" = "1" ]]; then
    chown "root:$RUN_USER" "$ENV_FILE" 2>/dev/null || true
else
    chown "$(id -u):$(id -g)" "$ENV_FILE" 2>/dev/null || true
fi

if [[ "$IS_ROOT" = "1" && "$CREATE_USER" = "1" ]]; then
    if ! id -u "$RUN_USER" >/dev/null 2>&1; then
        log "创建系统用户：$RUN_USER"
        useradd --system --home-dir "$DATA_DIR" --shell /usr/sbin/nologin "$RUN_USER" 2>/dev/null \
            || useradd -r -d "$DATA_DIR" -s /sbin/nologin "$RUN_USER"
    fi
    chown -R "$RUN_USER":"$RUN_USER" "$DATA_DIR"
fi

# 源码副本是 0750，降权后可能读不到；统一给只读权限
chmod -R a+rX "$PREFIX/app" "$PREFIX/web" 2>/dev/null || true

run_as() {
    if [[ "$IS_ROOT" = "1" && "$CREATE_USER" = "1" ]]; then
        su -s /bin/sh "$RUN_USER" -c "$*"
    else
        sh -c "$*"
    fi
}

# ---------------------------------------------------------------- 数据库迁移
if [[ "$SKIP_MIGRATE" != "1" ]]; then
    log "执行数据库迁移（alembic upgrade head）"
    run_as "cd '$PREFIX/app' && ECHOSHELF_DATA_PATH='$DATA_DIR' ECHOSHELF_AUDIOBOOKS_PATH='${AUDIOBOOKS_DIR:-/srv/audiobooks}' ECHOSHELF_WEB_DIST_PATH='$PREFIX/web/dist' '$PREFIX/venv/bin/alembic' upgrade head"
fi

# ---------------------------------------------------------------- 前台启动脚本
mkdir -p "$PREFIX/bin"
cat > "$PREFIX/bin/echoshelf" <<EOF
#!/usr/bin/env bash
# 用法：
#   $PREFIX/bin/echoshelf                 # 前台启动服务
#   $PREFIX/bin/echoshelf admin create    # 创建唯一管理员（网页端不能创建）
#   $PREFIX/bin/echoshelf admin reset-password
#   $PREFIX/bin/echoshelf admin list
set -euo pipefail
set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a
cd "$PREFIX/app"
if [[ "\${1:-}" == "admin" ]]; then
    shift
    exec "$PREFIX/venv/bin/python" -m app.cli admin "\$@"
fi
exec "$PREFIX/venv/bin/uvicorn" app.main:app \\
    --host "\${ECHOSHELF_HOST:-0.0.0.0}" \\
    --port "\${ECHOSHELF_PORT:-$PORT}" \\
    --proxy-headers --forwarded-allow-ips='*'
EOF
chmod +x "$PREFIX/bin/echoshelf"

# ---------------------------------------------------------------- systemd
if [[ "$INSTALL_SERVICE" = "1" ]]; then
    UNIT="/etc/systemd/system/$SERVICE_NAME.service"
    log "安装 systemd 服务：$UNIT"
    sed \
        -e "s#@@PREFIX@@#$PREFIX#g" \
        -e "s#@@ENV_FILE@@#$ENV_FILE#g" \
        -e "s#@@DATA_DIR@@#$DATA_DIR#g" \
        -e "s#@@RUN_USER@@#$RUN_USER#g" \
        "$SOURCE_DIR/echoshelf.service.in" > "$UNIT"
    systemctl daemon-reload
    systemctl enable "$SERVICE_NAME" >/dev/null 2>&1 || true
    systemctl restart "$SERVICE_NAME"
    sleep 2
    systemctl --no-pager --lines=0 status "$SERVICE_NAME" || true
fi

cat <<EOF

安装完成。

  程序目录   $PREFIX
  数据目录   $DATA_DIR
  配置文件   $ENV_FILE
  媒体目录   $(grep -E '^ECHOSHELF_AUDIOBOOKS_PATH=' "$ENV_FILE" | cut -d= -f2-)

接下来的事：
  1. 编辑 $ENV_FILE，把 ECHOSHELF_AUDIOBOOKS_PATH 指向你的有声书目录
  2. 重启：$( [[ "$INSTALL_SERVICE" = "1" ]] && echo "systemctl restart $SERVICE_NAME" || echo "$PREFIX/bin/echoshelf &" )
  3. 创建唯一管理员（网页端不提供创建入口）：
       sudo -u $RUN_USER $PREFIX/bin/echoshelf admin create
  4. 打开 http://<这台机器IP>:$PORT 登录
     忘记密码：sudo -u $RUN_USER $PREFIX/bin/echoshelf admin reset-password

健康检查：curl -s http://127.0.0.1:$PORT/api/v1/health
EOF
