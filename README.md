# shelf

> 自托管有声书服务器 · 原 EchoShelf · 声架

在 NAS 上用 Docker 跑一个容器，用浏览器或安卓 App 听书，进度多端互通。轻量、单容器、SQLite，不需要 Postgres / Redis。

> **开发说明**：本项目由 **subject** 与 AI 共同开发。需求定义、验收与部署由 subject 负责，代码、文档与测试在 AI 辅助下完成；使用前请自行评估与测试。

---

## 目录

- [简介](#简介)
- [功能特性](#功能特性)
- [技术栈](#技术栈)
- [架构概览](#架构概览)
- [快速开始](#快速开始)
- [配置项](#配置项)
- [数据与目录](#数据与目录)
- [API](#api)
- [项目结构](#项目结构)
- [文档](#文档)
- [常见问题](#常见问题)
- [路线图](#路线图)
- [许可证与作者](#许可证与作者)

## 简介

shelf 是一个面向 NAS 的自托管有声书服务器。把有声书目录挂载进容器，shelf 会自动扫描、识别标签 / 章节 / CUE、提取封面并入库；网页端提供完整的播放器，支持多端进度同步；同一套 WebUI 也可作为手机 PWA 或 Android WebView 壳使用。

设计目标是 **单容器 + SQLite** 的轻量部署：无需额外的数据库或消息队列，一台普通 NAS 即可承载大规模文件索引与多路并发播放。

## 功能特性

### 书库与扫描

- 登记服务器目录，递归扫描音频文件，自动识别标题 / 作者 / 演播者 / 系列等标签
- 支持 CUE 分轨、内嵌章节、封面提取
- 重扫幂等，不会产生重复书籍；缺失文件标记、隐藏书籍
- 按书库授权，未授权用户不可见

### 播放

- 全局播放器：切换路由不断音，底部播放条 + 全屏播放页
- 倍速、上一章 / 下一章、±15 秒、音量、静音
- 章节列表、书签、进度回溯点（每本书保留多个检查点）
- 睡眠定时（按时长 / 按集数，最后 30 秒淡出）
- 自动连播；跳过片头 / 片尾（按每个音频文件 / 每集生效）
- 多端进度同步：同一账号在网页 / 手机上共享进度

### 格式与转码

- 直接流式播放：mp3 / m4a / m4b / aac / flac / ogg / opus / wav
- 浏览器不支持的格式（wma / ape 等）由服务端 ffmpeg 转码为 opus / mp3
- 支持 HTTP Range，大文件拖动不整段传输

### 检索与统计

- FTS5 全文搜索（书名 / 副标题 / 作者 / 演播者 / 系列 / 简介），中文短词回退 LIKE
- 作者视图、系列分组
- 收听统计：今日 / 累计 / 连续天数 / 近 7 天

### 多用户与安全

- 三级角色：管理员 / 上传者 / 听众
- 书库级授权（未授权用户不可见）
- 设备管理、密码修改、refresh token 吊销
- 管理员只能带外创建（环境变量或 CLI），网页端不提供初始化入口

### 客户端

- WebUI 响应式布局，可作为 PWA 安装
- Android WebView 壳（`android-pwa/`）：复用 WebUI，支持系统返回键、状态栏安全区适配
- 原生 Compose 版（`android/`）为早期实验，已搁置

## 技术栈

| 层 | 选型 |
|---|---|
| 后端 | Python 3.11+ · FastAPI · SQLAlchemy 2.0 · Alembic · SQLite（WAL / FTS5）· mutagen · ffmpeg |
| 网页端 | React 18 · TypeScript · Vite · TailwindCSS · Zustand · TanStack Query |
| 移动端 | Android WebView 壳（`android-pwa/`）· PWA |
| 部署 | Docker 多阶段构建（单镜像含前端静态资源）· docker compose · systemd |

## 架构概览

- **单体优先**：一个 FastAPI 进程 + SQLite；后台扫描任务在进程内调度。
- **直出优先，转码兜底**：支持 Range 的原文件直接流式传输；客户端不支持时才走 ffmpeg。
- **元数据以文件为准**：数据库只做索引缓存，删库可重建，扫描幂等。
- **进度以客户端为准，服务端仲裁**：多端冲突按「最后写入胜 + 单调不回退」合并。

更完整的架构与数据流见 [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md)。

## 快速开始

### 方式一：Docker（推荐）

```bash
docker run -d --name shelf \
  -p 8080:8080 \
  -v /path/to/audiobooks:/audiobooks:ro \
  -v /path/to/data:/data \
  -e ECHOSHELF_ADMIN_USERNAME=admin \
  -e ECHOSHELF_ADMIN_PASSWORD='change-me-please' \
  -e PUID=1000 -e PGID=1000 \
  ghcr.io/subject2019/shelf:latest
```

打开 `http://<NAS_IP>:8080`，用上面的管理员账号登录。

> 数据目录必须放在本地盘，不要用 SMB / NFS；媒体目录以只读方式挂载。

### 方式二：docker compose

```yaml
services:
  shelf:
    image: ghcr.io/subject2019/shelf:latest
    container_name: shelf
    restart: unless-stopped
    ports:
      - "8080:8080"
    environment:
      ECHOSHELF_ADMIN_USERNAME: admin
      ECHOSHELF_ADMIN_PASSWORD: change-me-please
      PUID: 1000
      PGID: 1000
    volumes:
      - /path/to/audiobooks:/audiobooks:ro
      - /path/to/data:/data
```

```bash
docker compose up -d
```

### 方式三：本地开发

```bash
# 后端
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080

# 前端（另开终端）
cd web
npm ci
npm run dev        # http://localhost:5173 ，/api 代理到 127.0.0.1:8080
```

默认数据目录为仓库根 `data/`，可通过 `ECHOSHELF_DATA_PATH` 覆盖。

### 构建镜像

```bash
docker build -f deploy/docker/Dockerfile -t shelf:latest .
```

## 配置项

宿主机 `.env`（compose）/ 容器环境变量：

| 变量 | 默认 | 说明 |
|---|---|---|
| `AUDIOBOOKS_PATH` | `/volume1/media/audiobooks` | 宿主机媒体目录，挂载到容器 `/audiobooks:ro` |
| `ECHOSHELF_DATA_PATH` | `/volume1/docker/shelf` | 数据目录（数据库 / 封面缓存），必须本地盘 |
| `SHELF_HOST_PORT` | `8080` | 宿主机映射端口（容器内固定 8080） |
| `ECHOSHELF_ADMIN_USERNAME` | `admin` | 管理员用户名 |
| `ECHOSHELF_ADMIN_PASSWORD` | — | 管理员密码（建议 ≥8 位）；也可用 `_FILE` 指向 secret 文件 |
| `ECHOSHELF_ADMIN_SYNC_PASSWORD` | `false` | 每次启动用上面的密码覆盖管理员密码 |
| `ECHOSHELF_ALLOW_REGISTRATION` | `false` | 是否允许网页注册 |
| `ECHOSHELF_ENABLE_TRANSCODE` | `true` | 是否启用 ffmpeg 转码 |
| `PUID` / `PGID` | `1000` | 容器运行身份，需对媒体目录有读权限 |
| `TZ` | `Asia/Shanghai` | 时区 |
| `ECHOSHELF_LOG_LEVEL` | `info` | 日志级别 |

> **权限提示**：容器以 `PUID/PGID` 运行，媒体目录必须对该用户可读（例如 `sudo chmod -R a+rX /path/to/audiobooks`），否则扫描会读不到文件。

## 数据与目录

| 容器路径 | 用途 |
|---|---|
| `/audiobooks` | 媒体目录（只读挂载） |
| `/data` | 数据库、封面缓存、日志等运行数据 |

数据库使用 SQLite WAL + FTS5；容器启动时自动执行 `alembic upgrade head`（幂等）。

## API

后端为 FastAPI，接口前缀 `/api/v1`，自动生成 OpenAPI 文档：

- Swagger UI：`http://<host>:8080/docs`
- OpenAPI JSON：`http://<host>:8080/openapi.json`

完整接口参考见 [`docs/API.md`](./docs/API.md)。

## 项目结构

```
shelf/
├── backend/                 FastAPI 服务（app/ + alembic/ + tests/）
├── web/                     React 网页端（Vite）
├── android-pwa/             Android WebView 壳
├── android/                 原生 Compose 版（实验，已搁置）
├── deploy/
│   ├── docker/              Dockerfile / entrypoint / compose
│   ├── bare/                systemd 常规部署
│   └── scripts/             backup / restore / healthcheck
├── docs/                    架构 / 接口 / 数据模型 / 部署文档
├── data/                    运行时数据（git 忽略）
├── release/                 分发包输出（git 忽略）
└── README.md
```

## 文档

| 文档 | 内容 |
|---|---|
| [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) | 系统架构与关键流程 |
| [docs/API.md](./docs/API.md) | 接口参考（权限 / 示例 / 错误码） |
| [docs/DATA_MODEL.md](./docs/DATA_MODEL.md) | 数据库表结构 |
| [docs/AUDIO_FORMATS.md](./docs/AUDIO_FORMATS.md) | 音频格式 / 章节 / CUE 支持矩阵 |
| [docs/CLIENT_DOWNLOAD.md](./docs/CLIENT_DOWNLOAD.md) | 客户端按章节下载约定 |
| [docs/DEPLOY_NAS.md](./docs/DEPLOY_NAS.md) | NAS 部署与运维 |
| [docs/ROADMAP.md](./docs/ROADMAP.md) | 里程碑与任务拆解 |
| [docs/ADR/](./docs/ADR/) | 架构决策记录 |

## 常见问题

**扫描后书是 0 本？**
先确认媒体目录已挂载到 `/audiobooks`，且容器用户（PUID/PGID）可读。可在「设置 → 书库」重新登记 / 扫描。

**浏览器无法播放 wma / ape？**
属于预期：这两类由服务端转码为 opus / mp3 输出，首次播放会有转码延迟。

**修改管理员密码后重启被覆盖？**
若设置了 `ECHOSHELF_ADMIN_SYNC_PASSWORD=true`，每次启动都会用环境变量覆盖；改密码请改环境变量或关闭该开关。

**忘记管理员密码？**
修改 `ECHOSHELF_ADMIN_PASSWORD` 并重启（或开启同步开关）；也可进入容器执行 CLI 重置。

## 路线图

核心 Web 端已完成；后续主要是打磨与移动端。详见 [`docs/ROADMAP.md`](./docs/ROADMAP.md)。

## 许可证与作者

- 作者：**subject**
- 开发：**subject** 与 AI 共同开发
- 版权：Copyright © 2026 subject
- 许可证：仓库暂未附带 `LICENSE` 文件；如需开源分发，请先补充许可证。
