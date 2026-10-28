#!/usr/bin/env bash
# 构建可以直接分发的产物，输出到 release/
#
#   deploy/build-release.sh                 # 常规部署包（先构建前端）
#   deploy/build-release.sh --skip-web      # 复用已有 web/dist
#   deploy/build-release.sh --with-wheels   # 额外打包 Python 依赖 wheels（离线安装）
#   deploy/build-release.sh --docker        # 再做一个离线 Docker 镜像（较慢，建议最后跑）
#
# 产物：
#   release/shelf-<ver>-linux-<arch>-bare.tar.gz(+.sha256)
#   release/shelf-<ver>-linux-<arch>-docker.tar.gz(+.sha256)   # --docker
#   release/shelf-<ver>.apk(+.sha256)                            # 若已构建 android-pwa release
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RELEASE_DIR="$ROOT/release"
STAGE_ROOT="$RELEASE_DIR/staging"
SKIP_WEB=0
WITH_WHEELS=0
BUILD_DOCKER=0
KEEP_STAGE=0

log() { printf '\033[1;32m[build]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[build]\033[0m %s\n' "$*" >&2; }
die() { printf '\033[1;31m[build]\033[0m %s\n' "$*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-web) SKIP_WEB=1; shift ;;
        --with-wheels) WITH_WHEELS=1; shift ;;
        --docker) BUILD_DOCKER=1; shift ;;
        --keep-stage) KEEP_STAGE=1; shift ;;
        -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
        *) die "未知参数：$1" ;;
    esac
done

VERSION="$(grep -E '^APP_VERSION' "$ROOT/backend/app/core/config.py" | head -1 | cut -d'"' -f2)"
[[ -n "$VERSION" ]] || die "无法从 app/core/config.py 读取 APP_VERSION"

case "$(uname -m)" in
    x86_64|amd64) ARCH=amd64 ;;
    aarch64|arm64) ARCH=arm64 ;;
    *) ARCH="$(uname -m)" ;;
esac

NAME="shelf-$VERSION-linux-$ARCH"
STAGE="$STAGE_ROOT/$NAME"
TARBALL="$RELEASE_DIR/$NAME-bare.tar.gz"

log "版本 $VERSION · 架构 $ARCH"
mkdir -p "$RELEASE_DIR" "$STAGE"

# ---------------------------------------------------------------- 前端
if [[ "$SKIP_WEB" = "1" ]]; then
    [[ -f "$ROOT/web/dist/index.html" ]] || die "--skip-web 需要已有 web/dist"
    log "复用已有 web/dist"
else
    command -v npm >/dev/null || die "缺少 npm（或加 --skip-web 复用已有构建）"
    log "构建前端（npm ci + build）"
    (cd "$ROOT/web" && npm run build >/tmp/shelf-web-build.log 2>&1) \
        || { tail -20 /tmp/shelf-web-build.log >&2; die "前端构建失败"; }
fi

# ---------------------------------------------------------------- 后端源码
log "复制后端（排除 tests / venv / 缓存）"
rm -rf "$STAGE/app"
mkdir -p "$STAGE/app" "$STAGE/web"
tar -C "$ROOT/backend" -cf - \
    --exclude='./.venv' \
    --exclude='./tests' \
    --exclude='./.pytest_cache' \
    --exclude='./.ruff_cache' \
    --exclude='./.mypy_cache' \
    --exclude='./requirements.txt' \
    --exclude='./.coverage*' \
    --exclude='__pycache__' \
    . | tar -C "$STAGE/app" -xf -

rm -rf "$STAGE/web/dist"
cp -a "$ROOT/web/dist" "$STAGE/web/dist"

# ---------------------------------------------------------------- 部署文件
log "复制安装脚本与模板"
cp "$ROOT/deploy/bare/install.sh" "$ROOT/deploy/bare/uninstall.sh" "$STAGE/"
cp "$ROOT/deploy/bare/echoshelf.service.in" "$ROOT/deploy/bare/echoshelf.env.example" "$STAGE/"
cp "$ROOT/deploy/bare/README.md" "$STAGE/README.md"
chmod +x "$STAGE/install.sh" "$STAGE/uninstall.sh"

echo "$VERSION" > "$STAGE/VERSION"

if [[ "$WITH_WHEELS" = "1" ]]; then
    log "下载 Python 依赖 wheels（离线安装用）"
    mkdir -p "$STAGE/wheels"
    python3 -m pip download --only-binary=:all: --dest "$STAGE/wheels" \
        -r "$ROOT/backend/requirements-prod.txt" >/tmp/shelf-wheels.log 2>&1 \
        || { tail -20 /tmp/shelf-wheels.log >&2; warn "部分依赖没有 wheel，离线安装可能失败"; }
fi

# ---------------------------------------------------------------- 清单与打包
log "生成 MANIFEST（sha256）"
(
    cd "$STAGE"
    find . -type f ! -name MANIFEST.txt -print0 \
        | sort -z \
        | xargs -0 sha256sum > MANIFEST.txt
)

log "打包 $TARBALL"
tar -C "$STAGE_ROOT" -czf "$TARBALL" "$NAME"
(cd "$RELEASE_DIR" && sha256sum "$(basename "$TARBALL")" > "$(basename "$TARBALL").sha256")

# ---------------------------------------------------------------- Android APK（可选）
# APK 版本需与 APP_VERSION 一致；取 assembleRelease 的已签名产物。
APK="$ROOT/android-pwa/app/build/outputs/apk/release/app-release.apk"
if [[ -f "$APK" ]]; then
    log "复制 Android release APK"
    cp "$APK" "$RELEASE_DIR/shelf-$VERSION.apk"
    (cd "$RELEASE_DIR" && sha256sum "shelf-$VERSION.apk" > "shelf-$VERSION.apk.sha256")
fi

# ---------------------------------------------------------------- Docker（可选，最慢）
if [[ "$BUILD_DOCKER" = "1" ]]; then
    command -v docker >/dev/null || die "缺少 docker"
    # 用专用 builder（docker-container 驱动），构建缓存落在 docker data-root（/vol1），
    # 不占系统盘；若该 builder 不存在则自动创建。
    if ! docker buildx inspect shelf-builder >/dev/null 2>&1; then
        docker buildx create --name shelf-builder --driver docker-container --use 2>/dev/null \
            || warn "创建 shelf-builder 失败，回退默认 builder"
    fi
    log "构建镜像 shelf:$VERSION（缓存不在系统盘）"
    docker buildx build --builder shelf-builder \
        -f "$ROOT/deploy/docker/Dockerfile" \
        -t "shelf:$VERSION" -t "shelf:latest" --load "$ROOT"

    DOCKER_TAR="$RELEASE_DIR/$NAME-docker.tar.gz"
    log "导出镜像（docker save | gzip）"
    # 同时带上 latest（若存在），接收方 docker load 后可直接 docker run shelf:latest
    TAGS=("shelf:$VERSION")
    if docker image inspect shelf:latest >/dev/null 2>&1; then
        TAGS+=("shelf:latest")
    fi
    docker save "${TAGS[@]}" | gzip -9 > "$DOCKER_TAR"
    (cd "$RELEASE_DIR" && sha256sum "$(basename "$DOCKER_TAR")" > "$(basename "$DOCKER_TAR").sha256")
    log "镜像大小：$(du -h "$DOCKER_TAR" | cut -f1)"
fi

if [[ "$KEEP_STAGE" != "1" ]]; then
    rm -rf "$STAGE_ROOT"
fi

log "完成，产物："
ls -lh "$RELEASE_DIR"/*.tar.gz* "$RELEASE_DIR"/*.apk* 2>/dev/null \
    | awk '{printf "  %-70s %s\n", $9, $5}'
