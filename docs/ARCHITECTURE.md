# 系统架构

## 1. 总体形态

```
┌──────────────┐   HTTPS/HTTP    ┌─────────────────────────────────────┐
│  浏览器 SPA  │ ───────────────▶│  EchoShelf 容器（单进程）            │
│  React       │                 │                                     │
└──────────────┘                 │  FastAPI (uvicorn, 1 worker)         │
                                 │   ├─ /api/v1/*      业务 REST        │
┌──────────────┐                 │   ├─ /stream/*      Range 音频直出   │
│  Android App │ ───────────────▶│   ├─ /assets/*      前端静态资源     │
│  Media3      │                 │   └─ 后台扫描线程（单写者）           │
└──────────────┘                 │                                     │
                                 │  SQLite (WAL)  +  封面/转码缓存       │
                                 └───────────┬─────────────────────────┘
                                             │ 只读挂载
                                    ┌────────▼─────────┐
                                    │ /audiobooks      │
                                    │ 用户的有声书目录  │
                                    └──────────────────┘
```

设计原则：**一个容器、一个进程、一个数据库文件**。用户 `docker compose up -d` 后不需要理解任何中间件。

## 2. 分层

| 层 | 路径 | 职责 | 约束 |
|---|---|---|---|
| 路由层 | `backend/app/api/v1/` | 参数校验、鉴权依赖、调用 service、组装响应 | 不写业务逻辑，不直接碰文件系统 |
| 服务层 | `backend/app/services/` | 扫描、元数据、流式、转码、封面、检索、进度合并、回溯点、收听统计 | 可独立单测，纯函数优先 |
| 模型层 | `backend/app/models/` | SQLAlchemy ORM | 不导入 services（避免环） |
| 契约层 | `backend/app/schemas/` | Pydantic 请求/响应 DTO | 与 `docs/API.md` 一一对应 |
| 核心层 | `backend/app/core/` | 配置、安全、日志、异常 | 被所有层依赖，不反向依赖 |
| 任务层 | `backend/app/workers/` | 扫描线程、清理任务 | 只通过队列与路由层交互 |

依赖方向：`api → services → models → db`，`core` 全局可用。禁止 `models → services`。

## 3. 关键流程

### 3.1 媒体扫描（幂等）

```
触发：POST /libraries/{id}/scan  →  入队 ScanTask(status=queued)
后台线程：
  1. os.walk(root_path)，跳过隐藏目录与 @eaDir/#recycle（NAS 系统目录）
  2. 按「书」聚合：同一目录下的音频文件 = 一本书；
     · 若目录内含 .cue → 每个 cue 视为一本书（cue 分轨）
     · 若单文件为 .m4b/.mp3 且内嵌章节 → 该文件即一本书
  3. 每条音频文件读 stat(mtime,size,inode) 与 audio_files 表比对
     · 新文件 → 解析元数据入队
     · mtime/size 变化 → 重解析
     · 记录消失 → 标记 missing（不立即删除，保留用户进度/书签）
  4. 解析：mutagen 读标签/时长/采样率/内嵌封面；ffprobe 兜底未知容器
  5. 章节来源优先级：内嵌章节 > CUE > 单轨多文件(每个文件=一章) > 按时长切虚拟章节(默认 15min)
  6. 封面 → 抽取到 /data/cache/covers/{book_id}.jpg（含 400px 缩略图）
  7. 写入 ScanTask 统计，更新 book.updated_at
```

并发控制：全局**单写者**（`threading.Lock` + 队列），扫描永远串行；读请求走 WAL 不受阻塞。

### 3.2 音频播放传输

客户端播放某章时：

```
GET /api/v1/books/{book_id}/tracks/{track_id}/stream
  Header: Range: bytes=1048576-
  1. 鉴权 + 校验 track 属于该用户可见书库
  2. 检查 Accept 与 format：
     · 客户端声明支持（默认 mp3/aac/m4a/flac/opus in webm|ogg）→ 直出
     · 不支持（如 wma、ape、dsf）或 ?transcode=1 → 转码流
  3. 直出：open(path,'rb').seek(start)，逐块 yield 64KB，
     Content-Range / Accept-Ranges / Content-Length 严格按 RFC 7233
  4. 转码：subprocess ffmpeg -ss start -i path -t dur -c:a libopus -b:a 64k
     -f webm pipe:1 → 作为 chunked 响应（不缓存，除非命中预热缓存）
```

要点：
- 用 `int` 处理偏移，避免 2GB 溢出（Python 无此问题，但前端 JS 的 `number` 安全，勿转 int32）。
- `HEAD` 请求返回同样的头但无 body，供客户端探测大小。
- 断线重连依赖 Range，服务端**不做**连接状态保持，无状态化。

### 3.3 多端进度同步

```
客户端播放中每 15s（或暂停/切章/退出时）：
PUT /api/v1/progress/{book_id}
  { "track_id": 12, "position_sec": 733.5, "playback_rate": 1.25, "device_id": "web-abc", "client_updated_at": "..." }

服务端合并规则（LWW + 单调不回退）：
  1. 若 client_updated_at <= 已存 updated_at → 丢弃（旧数据）
  2. 否则按 position 比较：
     · 同一 track 且新 position < 旧 position - 30s，且未携带 "explicit_seek": true → 视为回退，保留较后位置
     · 显式跳转（用户点章节/拖动）→ 直接采纳
  3. 写库，返回权威值
```

客户端启动/进入书籍详情时 `GET /api/v1/progress/{book_id}` 拉权威值；书架 `GET /api/v1/progress/recent?limit=20` 展示「继续收听」。

### 3.4 鉴权

- 密码：`argon2id`（备选 bcrypt）。
- `POST /auth/login` → `access_token`（30min，JWT，`sub=user_id`）+ `refresh_token`（30d，存库可吊销）。
- 网页端：access token 存内存，refresh 用 httpOnly cookie；避免 localStorage 被 XSS 读取。
- 安卓端：两者均存 EncryptedSharedPreferences。
- 首次启动：管理员只能带外创建——容器用 `ECHOSHELF_ADMIN_PASSWORD` / `_FILE`，裸机用 `echoshelf admin create`；网页端无初始化接口，接口也不接受 `role="admin"`。
- 权限：`role ∈ {admin, user}`；`library_users` 表做书库级授权（空 = 全员可见）。

### 3.5 全文检索

- `books_fts`：FTS5 虚拟表，`tokenize='trigram'`，`content='books'`（正文不重复存），
  三个触发器同步增删改，迁移时 `rebuild` 回填
- 查询按空格拆词：≥3 字的词拼成 `MATCH` 短语（引号转义，用户输入不会被当 FTS 语法）；
  1–2 字的词 trigram 造不出词元，回退 `LIKE`，两类条件 AND
- 十万行基准：精确 6 字 0.1ms（LIKE 28.1ms）、5 字作者 1.0ms（LIKE 29.4ms）、宽泛查询两者约 40ms

### 3.6 收听统计

- 写入时机与进度同源：`PUT /progress` 被接受时，用 `新位置 - 旧位置` 估算这段播放
- `explicit_seek`（拖进度条/跳章）不计、位置倒退不计、单次最多 600 秒（防离线补传灌水）
- 按 `playback_rate` 折算真实时长（2 倍速下 60 秒进度 ≈ 30 秒收听），落 `listening_daily(user_id, day)`
- `GET /stats` 返回今日 / 累计 / 连续天数（今天没听不断签）+ 近 N 天明细（缺失补 0）

## 4. 数据与存储布局

| 路径 | 内容 | 备份必要性 |
|---|---|---|
| `/audiobooks`（只读挂载） | 用户媒体库 | 用户自备 |
| `/data/config/echoshelf.db` | SQLite 主库 | **必须** |
| `/data/config/secret.key` | JWT 签名密钥（首次启动生成） | **必须**（否则所有人需重登） |
| `/data/cache/covers/` | 封面与缩略图 | 可丢，会重建 |
| `/data/cache/transcode/` | 转码分片缓存（可选） | 可丢 |
| `/data/logs/` | 应用日志（按天轮转，保留 14 天） | 可选 |

## 5. 前端架构（web）

```
src/
├── api/          # 生成的/手写的 REST client，统一错误处理与 token 刷新
├── store/        # Zustand：player（当前书/轨/时间/速率）、auth、ui
├── components/
│   ├── player/   # PlayerBar（全局底部）、ChapterList、SleepTimer、SpeedMenu
│   ├── shelf/    # BookCard、BookGrid、FilterBar
│   └── layout/   # AppShell、Sidebar、TopBar
├── pages/        # Login、Home(继续收听)、Library、BookDetail、Search、Settings
├── lib/          # 时间格式化、Range/进度工具、快捷键 hook
└── styles/       # Tailwind 入口与主题变量
```

播放器内核使用**单个全局 `<audio>` 元素**（`PlayerBar` 持有），切页不中断；`MediaSession API` 提供锁屏/系统媒体控制；`useEffect` 里每 15s 上报进度。Android 壳内改由原生 Media3 接管音频，见 §6。

## 6. 安卓架构（android-pwa）

当前发布客户端是 `android-pwa/`：WebView 复用 WebUI，原生 Media3 只负责音频播放。`android/` 的 Compose 版是早期实验，已搁置。

```
android-pwa/app/src/main/java/com/shelf/pwa/
├── SetupActivity.java   首次启动：填写并校验服务器地址（/api/v1/health）
├── MainActivity.java    WebView、状态栏安全区、ShelfPlayer JS 桥、通知权限
└── player/
    ├── PlaybackService.java  MediaSessionService + ExoPlayer + 媒体通知
    └── NativePlayer.java     MediaController：播放列表、片头片尾、状态回传
```

- **UI 复用**：壳不打包前端，启动后加载服务器 WebUI；登录、书库、播放页与浏览器一致。
- **原生桥**：网页检测到 `window.ShelfPlayer` 后，把整本书的播放列表、起始位置、倍速和封面交给原生；原生每 500ms 回传播放状态。
- **后台播放**：`MediaSessionService` + `ExoPlayer` 持有前台服务和媒体会话；`onTaskRemoved` 不停止播放。
- **通知/锁屏**：五个标准 `playerCommand`（上一集、快退 15 秒、播放/暂停、快进 15 秒、下一集）；封面写入 `MediaMetadata.artworkData`；对系统隐藏时长和当前项 seek，隐藏进度条。
- **前端耦合**：服务端 `web/dist` 必须包含 `ShelfPlayer` 适配层；只更新 APK 不会让旧网页走原生播放。

详细构建、连接与排查见 [`android-pwa/README.md`](../android-pwa/README.md)。

## 7. 可观测性与容错

- 日志：结构化 JSON（`ts, level, logger, msg, extra`），`/data/logs/app.log` 按天轮转。
- 健康检查：`GET /api/v1/health` 返回 `{status, version, db, libraries, uptime}`；容器 healthcheck 用它。
- 启动自检：DB 可写、目录可读、ffmpeg 可用（缺失时降级为「不支持转码」而非崩溃）。
- 优雅关闭：`SIGTERM` → 停止接受新请求 → 等待扫描线程当前文件处理完 → 关闭 DB。

## 8. 明确的技术债与未来扩展点

| 项 | 现状 | 未来 |
|---|---|---|
| 转码 | 整轨转码落盘缓存（单路） | 多档码率、按集切片预热 |
| 搜索 | FTS5 trigram（≥3 字）+ 短词 `LIKE` | 自建按字分词索引，让 1–2 字也走索引 |
| 扫描 | 全量 walk | inotify 监听增量（NAS 上 inotify 常不可靠，需降级） |
| 多用户 | 书库隔离 + 设备/进度/统计 | 分享链接、家长控制、统计导出 |
| 同步 | 60 秒轮询 + 前后台事件 | WebSocket/SSE 实时推送（可选） |
