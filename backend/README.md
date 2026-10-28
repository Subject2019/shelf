# backend — FastAPI 服务

**状态：M1–M6 后端全部交付**。认证、书库授权、扫描、元数据/CUE/章节、书籍查询、Range 流式、整轨转码、FTS5 搜索、进度合并 + 回溯点、收听统计、按集切片缓存均可用（**208 passed**，**49 个接口**，迁移 head `0011`）。下一步是 M5 安卓 App。本文件说明每个文件该放什么，实现时不要随意改变分层。

## 目录职责

```
backend/
├── requirements.txt        # 固定版本，M1-T01 创建
├── Dockerfile              # 多阶段：web 构建 → python runtime，M3-T01 创建
├── alembic.ini             # 迁移配置
├── alembic/versions/       # 迁移脚本（001_init...）
├── app/
│   ├── main.py             # FastAPI 实例、路由挂载、启动自检、SIGTERM
│   ├── core/
│   │   ├── config.py       # pydantic-settings，读环境变量与 .env
│   │   ├── security.py     # 密码哈希、JWT 签发/校验、依赖注入 current_user
│   │   ├── logging.py      # JSON 结构化日志 + 按天轮转
│   │   └── exceptions.py   # AppError 及全局异常处理器（统一错误体）
│   ├── db/
│   │   ├── session.py      # engine（WAL、busy_timeout、foreign_keys）、SessionLocal
│   │   └── base.py         # DeclarativeBase + 通用 TimestampMixin
│   ├── models/             # 与 docs/DATA_MODEL.md 一一对应
│   ├── schemas/            # 与 docs/API.md 一一对应
│   ├── api/v1/
│   │   ├── router.py       # 汇总路由，prefix=/api/v1
│   │   ├── auth.py  libraries.py  books.py  stream.py
│   │   ├── progress.py  bookmarks.py  collections.py
│   │   └── system.py       # /health
│   ├── services/
│   │   ├── scanner.py      # 遍历、分组、判重、missing
│   │   ├── metadata.py     # mutagen 标签 + ffprobe 章节/流信息
│   │   ├── cue.py          # CUE 解析（编码探测、帧转换）
│   │   ├── streamer.py     # Range 解析 + 分块读取 + 416 处理
│   │   ├── transcoder.py   # ffmpeg 子进程转码（可关闭）
│   │   ├── cover.py        # 封面抽取/缩略图（Pillow）
│   │   └── progress.py     # 合并规则（见 ADR-0002）
│   └── workers/scan_worker.py  # 单写者队列线程
└── tests/
    ├── conftest.py         # 临时库 + TestClient fixture
    ├── fixtures/gen.sh     # 用 ffmpeg 生成各格式样本
    └── test_*.py
```

## 本地启动

```bash
cd backend
python3 -m venv .venv && . .venv/bin/activate    # 要求 Python ≥ 3.11
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
curl -s http://127.0.0.1:8080/api/v1/health
# {"status":"ok","version":"0.1.0","db":"ok","ffmpeg":true,"libraries":0,"books":0,"uptime_sec":3}
```

配置全部走环境变量（模板见 `deploy/.env.example`）：`AUDIOBOOKS_PATH` 媒体目录、
`ECHOSHELF_DATA_PATH` 运行时目录（默认项目根 `data/`，自动建 `config/`、`logs/`、`cache/`）。
交互式 API 文档在 `/api/docs`。

测试：

```bash
bash tests/fixtures/gen.sh       # 首次需要，生成被 .gitignore 忽略的音频样本
python -m pytest -q
```

## 实现顺序（严格按依赖）

1. `core/config.py` + `main.py` + `system.py` → 能返回 health（M1-T01）
2. `db/` + `models/` + alembic 初始迁移（M1-T02）
3. `services/cue.py` + `metadata.py`（纯函数，可脱离 DB 单测，M1-T05）
4. `services/scanner.py` + `workers/`（M1-T04）
5. `core/security.py` + `api/v1/auth.py`（M1-T03）
6. `services/streamer.py` + `api/v1/stream.py`（M1-T06）
7. `api/v1/progress.py` + `bookmarks.py`（M1-T07）
8. `api/v1/books.py` + `libraries.py`（M1-T08）

## 硬性约束

- 所有文件系统操作使用 `pathlib.Path`，路径必须经 `resolve()` 后校验仍在 `library.root_path` 之内（防目录穿越）。
- `streamer.py` 只读打开文件，`seek` 后按 64 KB 分块 `yield`，禁止一次性 `read()` 整个文件。
- 任何阻塞调用（mutagen、ffprobe、Pillow、磁盘遍历）不得直接放在 `async def` 里，走 `run_in_threadpool`。
- 扫描写库与进度写库共用一把写锁，避免 `database is locked`。
