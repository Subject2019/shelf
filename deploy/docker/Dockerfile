# shelf 单容器镜像：前端构建产物由 FastAPI 直接托管
#   docker build -f deploy/docker/Dockerfile -t shelf:latest .
#   docker run -d -p 8080:8080 -v /path/to/audiobooks:/audiobooks:ro -v /path/to/data:/data shelf:latest
#
# 体积取舍（目标 < 400MB）：
#   - Alpine + apk 安装 ffmpeg 约 116MB；Debian 版 ffmpeg 会拖进 libLLVM/libgallium 等 ~450MB 依赖
#   - 不用静态 ffmpeg 发行包：ffmpeg + ffprobe 两个二进制各 ~129MB，反而更大
#   - 健康检查用 python 内置 urllib，不额外装 curl
#   - 全部依赖都有 musllinux 轮子，不需要编译工具链

# ---------------- 前端构建 ----------------
FROM node:20-alpine AS web

WORKDIR /build/web
# 先只拷依赖清单，利用层缓存：源码改动不会重装 node_modules
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY web/ ./
RUN npm run build

# ---------------- 运行时 ----------------
FROM python:3.11-alpine AS runtime

LABEL org.opencontainers.image.title="shelf" \
      org.opencontainers.image.description="自托管有声书服务器" \
      org.opencontainers.image.authors="subject"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ffmpeg：ffmpeg（转码）+ ffprobe（章节探测）；su-exec：按 PUID/PGID 降权运行
RUN apk add --no-cache ffmpeg su-exec

WORKDIR /app

# 依赖层：只有 requirements 变动才重装
COPY backend/requirements-prod.txt ./
RUN pip install --no-compile --only-binary=:all: -r requirements-prod.txt \
    && find /usr/local/lib/python3.11 -name '__pycache__' -type d -prune -exec rm -rf {} + \
    && rm -rf /usr/local/lib/python3.11/site-packages/{pip,pip-*,setuptools,setuptools-*,_distutils_hack,distutils-precedence.pth}

COPY backend/ ./
# 前端产物放到 /web/dist：源码里 _LAYOUT_ROOT 在容器内解析为 /，默认路径正好命中
COPY --from=web /build/web/dist /web/dist

COPY deploy/docker/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
# 源码文件的权限带 `---`（开发机上是 0750/0640），降权后的 PUID 用户读不到，
# 统一放开只读权限：a+rX 给目录加执行位、文件加读位，不破坏已有可执行位
RUN chmod -R a+rX /app /web \
    && chmod +x /usr/local/bin/docker-entrypoint.sh

ENV ECHOSHELF_DATA_PATH=/data \
    ECHOSHELF_AUDIOBOOKS_PATH=/audiobooks \
    ECHOSHELF_CONTAINER=1 \
    ECHOSHELF_HOST=0.0.0.0 \
    ECHOSHELF_PORT=8080

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/api/v1/health', timeout=3).status==200 else 1)"

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "*"]
