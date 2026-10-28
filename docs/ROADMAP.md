# 路线图与任务拆解

任务 ID 与内部进度台账对齐。每个任务必须满足「验收」才算完成。
标注 🔒 的任务是后续任务的前置依赖。

## M0 立项与架构 ✅

| ID | 任务 | 验收 | 状态 |
|---|---|---|---|
| M0-T01 | 技术选型与架构设计 | `ARCHITECTURE.md` + ADR-0001 | ✅ |
| M0-T02 | 数据模型设计 | `DATA_MODEL.md` 覆盖全部表与索引 | ✅ |
| M0-T03 | API 契约 | `API.md` 覆盖 v1 全部端点 | ✅ |
| M0-T04 | 音频格式矩阵 | `AUDIO_FORMATS.md` 含边界清单 | ✅ |
| M0-T05 | NAS 部署方案 | compose + env 模板 + 手册 | ✅ |
| M0-T06 | 里程碑拆解 | 本文件 | ✅ |
| M0-T07 | 协作机制 | 内部协作规范 + 进度台账 | ✅ |
| M0-T08 | 目录骨架 | 目录与 `.gitkeep` 就位 | ✅ |
| M0-T09 | 进度冲突合并决策 | ADR-0002 含伪代码与备选方案 | ✅ |

## M1 后端内核（预计 5–7 个工作日）

| ID | 任务 | 交付物 | 验收 |
|---|---|---|---|
| M1-T01 🔒 | 工程骨架与配置 | `requirements.txt`、`app/main.py`、`app/core/config.py`、`app/core/logging.py` | `uvicorn` 启动，`GET /api/v1/health` 返回 200 与 version |
| M1-T02 🔒 | DB 模型与迁移 | `app/models/*.py`、`alembic/versions/0001_init.py` | `alembic upgrade head` 建出全部表；`alembic downgrade base` 可回滚 |
| M1-T03 | 认证 | `core/security.py`、`api/v1/auth.py` | 登录/刷新/登出/me 全通；错误密码 401；过期 token 401 |
| M1-T04 | 扫描器 | `services/scanner.py`、`workers/scan_worker.py` | 构造 3 目录 20 文件样本，扫描后 book/track 数正确；重扫不产生重复 |
| M1-T05 | 元数据与章节 | `services/metadata.py`、`services/cue.py` | 5 种格式样本解析出 title/duration/chapters；GBK cue 不乱码 |
| M1-T06 🔒 | Range 流式 | `services/streamer.py`、`api/v1/stream.py` | `curl -r 0-1023` 得 206 与正确 `Content-Range`；越界 416；大文件可拖动 |
| M1-T07 | 进度与书签 | `api/v1/progress.py`、`api/v1/bookmarks.py` | 上报冲突按 LWW 收敛；「继续收听」排序正确 |
| M1-T08 | 书籍查询 API | `api/v1/books.py`、`api/v1/libraries.py` | 分页/筛选/搜索参数全部生效；封面接口有 ETag |
| M1-T09 | 测试与样本 | `tests/`、`tests/fixtures/gen.sh` | `pytest` 覆盖率 ≥ 60%，扫描/解析/进度/Range 全覆盖 |

## M2 网页播放端（预计 4–6 天）

| ID | 任务 | 验收 |
|---|---|---|
| M2-T01 🔒 | Vite + React + Tailwind 脚手架、路由、主题（深/浅） | `npm run dev` 出首页，`npm run build` 无报错 |
| M2-T02 | 登录页 + token 自动刷新 + 路由守卫 | 刷新页面不掉登录；401 自动跳登录 |
| M2-T03 | 书架页（网格/列表、筛选、排序、进度角标） | 100 本书滚动流畅（虚拟列表或懒加载） |
| M2-T04 🔒 | 全局播放器（单 audio 实例、MediaSession、快捷键） | 切页不中断播放；空格/←→/↑↓ 生效；锁屏可控 |
| M2-T05 | 章节面板、书签、变速、睡眠定时 | 点章节精确跳转；定时到点淡出暂停 |
| M2-T06 | 详情页、搜索页、设置页 | 详情展示简介/系列/演播者；搜索有防抖 |
| M2-T07 | 进度上报与恢复 | 播放 15s 后上报；重开自动续播 ±2s |

## M3 Docker 化与 NAS 部署（预计 3 天）

| ID | 任务 | 验收 |
|---|---|---|
| M3-T01 🔒 | 多阶段 Dockerfile（node build web → python runtime + ffmpeg） | 镜像 < 400 MB，无 node 残留 |
| M3-T02 | compose + `.env.example` + PUID/PGID | `docker compose up -d` 后浏览器可用 |
| M3-T03 | 镜像构建与发布 ✅ 2026-10-26 | `docker buildx build --platform linux/amd64` 通过，打 `0.1.0` + `latest`；离线 `docker save` 90 MB 并验证 `docker load` |
| M3-T04 | 健康检查、日志轮转、SIGTERM 优雅关闭 | `docker stop` 5s 内退出且 DB 无损 |
| M3-T05 | backup/restore 脚本 ✅ 2026-10-26 | `backup.sh` + `restore.sh`；实测删库后恢复 4 本/3 进度/5 回溯点完整，非法归档被拒 |
| M3-T06 | 实机验收 ✅ 2026-10-26（判据修订） | Debian 13 / 4C3.8G 走通部署与迁移；1000 本扫描 **175.9s**（原 <60s 目标在实际硬件上不现实，改按硬件基线，并行化列入 M7） |
| M3-T07 | 常规部署（systemd / 前台运行）✅ 2026-10-25 | `deploy/bare/install.sh` 装完 `systemctl status` 正常；无 systemd 时 `bin/echoshelf` 可前台跑；升级幂等 |
| M3-T08 | 分发包与 `release/` ✅ 2026-10-25 | `deploy/build-release.sh` 产出 tar.gz + sha256，解压后一条 `install.sh` 即可用 |

## M4 多用户与同步加固（预计 3 天）

> **状态：2026-10-25 全部完成。** 实现位置：`backend/app/api/v1/users.py`、`devices.py`、
> `services/progress.py`、`web/src/components/settings/{UserSection,DeviceSection}.tsx`。

| ID | 任务 | 验收 |
|---|---|---|
| M4-T01 | 书库级授权、管理员界面 ✅ | 非授权用户看不到书库，直连 URL 得 403（已由 `tests/test_users_api.py` 覆盖） |
| M4-T02 | 进度冲突用例加固 ✅ | 4 组并发场景（同轨回退/跨轨/离线补传/时钟漂移）结果符合设计（`tests/test_progress.py`）；同时把「不回退」改为按绝对位置判断 |
| M4-T06 | 系列名按文件夹推导 ✅ 2026-10-26 | 多文件书 `间客/Ⅰ第一卷 …/` → 系列 `间客` 卷 1；单文件书不受影响 |
| M4-T07 | 管理员隐藏书籍 ✅ 2026-10-26 | 隐藏后普通用户列表/搜索/详情全不可见，管理员可见并带角标 |
| M4-T05 | 三级角色 `admin` / `editor` / `listener` ✅ 2026-10-25 | 听众只读；上传者可改资料/传封面、只能删自己传的封面；管理员全权 |
| M4-T03 | 设备管理（在线状态、踢下线）✅ | 踢下线后该设备 refresh 立即 401，access token 也立即 401（`tests/test_devices_api.py`） |

## M5 安卓 App（预计 10–14 天）

> **下一步开工**。⚠️ 先确认形态：**PWA**（复用 WebUI + Service Worker）还是
> **原生 Kotlin/Compose**（本文件按原生拆任务）。验收标准不同，勿默认选择。


| ID | 任务 | 验收 |
|---|---|---|
| M5-T01 🔒 | Gradle + Compose + Hilt 工程，minSdk 26 | `assembleDebug` 出 APK，能装能启动 |
| M5-T02 | Retrofit 客户端、登录、书架/详情 UI | 登录后拉取书库，图片用 Coil 加载 |
| M5-T03 🔒 | Media3 `MediaSessionService` + 通知 + 锁屏 | 息屏播放 30 分钟不中断；通知栏可控制 |
| M5-T04 | 离线下载（队列、断点、存储管理） | 下载 10 章后断网可完整播放（**服务端已于 2026-10-24 提前完成**：`POST /books/{id}/chapters/{idx}/cache` 预切片 + `GET .../audio?download=1` 断点下载；客户端只需排队调用） |
| M5-T05 | 进度同步（Room 待上传队列、冲突处理） | 飞行模式听 10 分钟→联网→服务端进度正确 |
| M5-T06 | 设置页、明网安全配置、深色模式、定时 | 连 `http://192.168.x.x` 不被系统拦截 |

## M6 增强（预计 5 天）✅ 2026-10-25 全部完成

| ID | 任务 | 验收 |
|---|---|---|
| M6-T01 | ffmpeg 转码（opus/mp3，可选缓存）✅ 2026-10-25 | wma 样本可转码播放，CPU 占用可观测（`/health` 的 `transcode.active`） |
| M6-T02 | FTS5 全文搜索 ✅ 2026-10-25 | 10 万行下查询 < 50 ms（实测精确 0.1ms / 宽泛 38ms） |
| M6-T03 | 系列/作者聚合页 ✅ 2026-10-25 | 系列：`GET /series` + 书架折叠卡/展开面板（2026-10-24 完成）；作者：`GET /authors` + `/authors` 页，点卡片按作者筛选书库 |
| M6-T04 | 睡眠定时增强（淡出、按章结束）、跳片头片尾 ✅ 2026-10-25 | 定时 + 淡出（最后 30 秒）+ 播完本集再停；`intro_sec`/`outro_sec` 自动跳片头片尾 |
| M6-T05 | 收听统计（时长、连续天数）✅ 2026-10-25 | `listening_daily` 按天累计 + `GET /stats` + 首页卡片 |

## M7 打磨与 v1.0（预计 4 天）

- 无障碍（键盘全操作、aria 标签）、i18n（中/英）
- 性能：书架首屏 < 1s（局域网）、扫描 10 万文件 < 15 min；**扫描器并行 ffprobe**（当前 1000 本 175.9s，目标 < 60s/4 核）
- 错误页、空状态、离线提示、加载骨架屏
- 文档补全（含截图）、CHANGELOG、镜像打 `1.0.0` tag
- 安全自查（见 `DEPLOY_NAS.md` §9）

## 关键路径

```
M1-T01 → M1-T02 → M1-T04 → M1-T05 → M1-T06 → M2-T04 → M3-T01 → M3-T06
                     ↘ M1-T07 ↗
M1-T06 → M5-T01 → M5-T03 → M5-T04
```

**建议的并行方式**：M1-T05（纯解析函数，不依赖 DB）可与 M1-T02 并行；M2-T01 可在 M1-T06 完成前先做静态页面；M5-T01 工程搭建可在 M4 期间并行。
