# 数据模型

数据库：**SQLite 3**（WAL 模式）。所有时间戳为 UTC ISO-8601 字符串或 epoch 秒（实现统一用 `INTEGER` epoch 秒，简单且无时区歧义）。

约定：
- 主键统一 `INTEGER PRIMARY KEY AUTOINCREMENT`（除 `devices` 用 `TEXT` uuid）。
- 布尔用 `INTEGER 0/1`。
- 所有 `*_at` 为 epoch 秒。
- `rel_path` 一律相对**所属书库根目录**，用 `/` 分隔，不存绝对路径。

## 1. ER 概览

```
users ──< library_users >── libraries ──< media_files
  │                              │            │
  │                              └──< books ──┤
  │                                     │     │
  ├──< progress >───────────────────────┤     │
  ├──< bookmarks >──────────────────────┤     │
  ├──< collections ──< collection_books ┘     │
  ├──< devices ──< refresh_tokens            │
  └──< scan_tasks                              │
                                     books ──< tracks >── media_files
                                       │
                                       └──< chapters >── tracks
```

**关键设计**：`media_files`（物理文件）与 `tracks`（逻辑播放轨）分离。
一个 CUE 分轨的整轨 FLAC 是 **1 条 media_file + N 条 track**，它们同属一张 book；
而一个「每章一个 mp3」的书是 **N 条 media_file + N 条 track**（1:1）。
这样扫描不会因 CUE 而重复解析大文件，进度/章节也能统一到「全书绝对秒数」。

另有 `progress_history`（每本书 7 个回溯点）与 `listening_daily`（按天收听秒数）两张辅助表，见 2.14 / 2.15。

## 2. 表定义

### 2.1 users

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | INTEGER | PK | |
| username | TEXT | UNIQUE NOT NULL | 登录名，大小写不敏感（存小写） |
| password_hash | TEXT | NOT NULL | argon2id |
| display_name | TEXT | | |
| role | TEXT | NOT NULL DEFAULT 'user' | `admin` / `editor` / `listener`；旧值 `user` 已迁移为 `listener` |
| is_active | INTEGER | NOT NULL DEFAULT 1 | 禁用后 token 失效 |
| created_at | INTEGER | NOT NULL | |
| last_login_at | INTEGER | | |

### 2.2 libraries

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | INTEGER | PK | |
| name | TEXT | NOT NULL | 展示名，如「评书」「英文小说」 |
| root_path | TEXT | NOT NULL | 容器内路径，如 `/audiobooks/fiction` |
| enabled | INTEGER | NOT NULL DEFAULT 1 | 停用后不扫描、不出现在**普通用户**列表；管理员列表仍返回（便于再次启用） |
| scan_cron | TEXT | | 预留，如 `0 3 * * *`；NULL = 仅手动 |
| last_scan_at | INTEGER | | |
| created_at | INTEGER | NOT NULL | |

### 2.3 library_users（书库授权）

| 列 | 类型 | 说明 |
|---|---|---|
| library_id | INTEGER | FK libraries，ON DELETE CASCADE |
| user_id | INTEGER | FK users，ON DELETE CASCADE |

PK `(library_id, user_id)`。**约定：某书库无任何行 = 全员可见**（避免新用户看不到内容）。

### 2.4 media_files（物理音频文件）

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | INTEGER | PK | |
| library_id | INTEGER | FK, NOT NULL | |
| rel_path | TEXT | NOT NULL | 相对库根；与 `library_id` 联合唯一（`uq_media_library_relpath`），对应项目架构红线 3 |
| format | TEXT | NOT NULL | 容器：`mp3`/`m4a`/`m4b`/`flac`/`ogg`/`opus`/`wav`/`aac`/`wma` |
| codec | TEXT | | `mp3`/`aac`/`alac`/`flac`/`vorbis`/`opus`/`pcm_s16le`/`wmav2` |
| bitrate | INTEGER | | kbps，可空 |
| sample_rate | INTEGER | | Hz |
| channels | INTEGER | | |
| duration_sec | REAL | | 文件总时长（cue 时是整轨时长） |
| size_bytes | INTEGER | | |
| mtime | INTEGER | | 用于幂等判重 |
| inode | INTEGER | | NAS 上可能为 0，仅辅助 |
| has_embedded_chapters | INTEGER | NOT NULL DEFAULT 0 | |
| embedded_chapters_json | TEXT | | `[{"title","start_sec","end_sec"}]` 原文缓存 |
| is_missing | INTEGER | NOT NULL DEFAULT 0 | 扫描时未见但保留记录 |
| first_seen_at | INTEGER | NOT NULL | |
| last_seen_at | INTEGER | NOT NULL | |

索引：`idx_media_library (library_id)`，`idx_media_missing (is_missing)`。

### 2.5 books

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | INTEGER | PK | |
| library_id | INTEGER | FK, NOT NULL | |
| rel_dir | TEXT | | 书所在目录（相对库根）；单文件书取其父目录 |
| title | TEXT | NOT NULL | 元数据缺失时用目录/文件名 |
| subtitle | TEXT | | |
| author | TEXT | | 多位用 `,` 分隔 |
| narrator | TEXT | | 演播者 |
| publisher | TEXT | | |
| publish_year | INTEGER | | |
| language | TEXT | | BCP-47，如 `zh-CN` |
| description | TEXT | | |
| series_name | TEXT | | 系列名 |
| series_index | REAL | | 支持 1.5 这类中篇 |
| cover_path | TEXT | | 相对 `/data/cache/covers/` |
| cover_uploaded_by | INTEGER | | `users.id`：手工封面的上传者；扫描抽取的封面为 NULL（不加外键，避免重建表丢失 FTS 触发器） |
| intro_sec | REAL | NOT NULL DEFAULT 0 | 书籍默认跳过片头秒数，0 = 不跳（Web 端优先用设备级偏好，填 0 才回退） |
| outro_sec | REAL | NOT NULL DEFAULT 0 | 书籍默认跳过片尾秒数，0 = 不跳（同上） |
| total_duration_sec | REAL | NOT NULL DEFAULT 0 | 由 tracks 汇总 |
| track_count | INTEGER | NOT NULL DEFAULT 0 | |
| size_bytes | INTEGER | NOT NULL DEFAULT 0 | |
| chapter_source | TEXT | | 全书主章节来源，见 2.7 |
| is_missing | INTEGER | NOT NULL DEFAULT 0 | 目录消失 |
| manual_override | INTEGER | NOT NULL DEFAULT 0 | 管理员手工改过元数据，扫描器不再覆盖书名/作者等字段 |
| hidden | INTEGER | NOT NULL DEFAULT 0 | 管理员在书架中隐藏：列表/搜索/系列/作者均不返回，普通用户详情 404（迁移 0011） |
| added_at | INTEGER | NOT NULL | |
| updated_at | INTEGER | NOT NULL | |

索引：`idx_books_library (library_id)`，`idx_books_title (title)`，`idx_books_author (author)`，`idx_books_series (series_name, series_index)`。

> 书名冲突允许存在（同一本书两个版本），不设唯一约束。

### 2.6 tracks（逻辑播放轨）

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | INTEGER | PK | |
| book_id | INTEGER | FK, NOT NULL | |
| media_file_id | INTEGER | FK, NOT NULL | |
| disc_no | INTEGER | NOT NULL DEFAULT 1 | |
| track_no | INTEGER | NOT NULL DEFAULT 1 | 书内播放顺序 |
| title | TEXT | | 章节名/文件名 |
| start_offset_sec | REAL | NOT NULL DEFAULT 0 | 在物理文件内的起点（CUE 分轨必填） |
| duration_sec | REAL | NOT NULL DEFAULT 0 | 本轨时长 |
| size_bytes | INTEGER | | 冗余，便于算下载体积 |

索引：`idx_tracks_book (book_id, track_no)`，`idx_tracks_media (media_file_id)`。
唯一：`uq_tracks_position (book_id, disc_no, track_no)`。

### 2.7 chapters

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | INTEGER | PK | |
| book_id | INTEGER | FK, NOT NULL | |
| track_id | INTEGER | FK, NOT NULL | 章节目录跳转需要 |
| idx | INTEGER | NOT NULL | 全书顺序，从 0 开始 |
| title | TEXT | NOT NULL | |
| start_sec | REAL | NOT NULL | **相对全书开头**的绝对秒数 |
| end_sec | REAL | | 可空 = 到下一章或结尾 |
| source | TEXT | NOT NULL | `embedded` / `cue` / `track_split` / `virtual` / `manual` |

索引：`idx_chapters_book (book_id, idx)`。
来源优先级（扫描时取最高者）：`embedded > cue > track_split > virtual`；`manual` 为用户手工编辑，永不被自动扫描覆盖。

### 2.8 progress（收听进度）

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| user_id | INTEGER | FK, NOT NULL | |
| book_id | INTEGER | FK, NOT NULL | |
| position_sec | REAL | NOT NULL DEFAULT 0 | **全书绝对秒数** |
| track_id | INTEGER | | 当前轨，便于快速定位 |
| track_position_sec | REAL | | 轨内偏移（= position - 轨起点） |
| playback_rate | REAL | NOT NULL DEFAULT 1.0 | 0.5–3.0 |
| is_finished | INTEGER | NOT NULL DEFAULT 0 | 由 position ≥ total-30s 自动置位 |
| device_id | TEXT | | 最后上报设备 |
| client_updated_at | INTEGER | | 客户端时间，用于 LWW |
| updated_at | INTEGER | NOT NULL | 服务端接收时间 |

PK `(user_id, book_id)`。索引：`idx_progress_updated (user_id, updated_at)`（「继续收听」列表；升序索引反向扫描即可满足 `ORDER BY updated_at DESC`，且 SQLite 能反射比较，便于 Alembic 校验）。

**合并规则**见 `ARCHITECTURE.md` §3.3：`client_updated_at` 旧者丢弃；同轨回退超过 30s 且非 `explicit_seek` 时保留较后位置。

### 2.9 bookmarks

| 列 | 类型 | 说明 |
|---|---|---|
| id | INTEGER | PK |
| user_id | INTEGER | FK |
| book_id | INTEGER | FK |
| position_sec | REAL | 全书绝对秒 |
| track_id | INTEGER | |
| note | TEXT | 可空，用户备注 |
| created_at | INTEGER | |

索引：`idx_bookmarks_user_book (user_id, book_id, position_sec)`。

### 2.10 collections / collection_books（自建书单）

collections：`id` PK，`user_id` FK，`name` TEXT NOT NULL，`created_at` INTEGER，UNIQUE `(user_id, name)`。
collection_books：`collection_id`，`book_id`，`added_at`，PK `(collection_id, book_id)`。

### 2.11 devices / refresh_tokens

devices：`id` TEXT PK（客户端生成的 uuid），`user_id` FK，`name` TEXT（「客厅 iPad」），`platform` TEXT（`web`/`android`），`app_version` TEXT，`last_seen_at` INTEGER。

refresh_tokens：`id` INTEGER PK，`user_id` FK，`device_id` TEXT，`token_hash` TEXT UNIQUE（sha256，不存明文），`expires_at` INTEGER，`revoked_at` INTEGER，`created_at` INTEGER。索引：`idx_refresh_user (user_id)`，用于改密码时批量吊销。

### 2.12 scan_tasks

| 列 | 类型 | 说明 |
|---|---|---|
| id | INTEGER | PK |
| library_id | INTEGER | FK |
| status | TEXT | `queued`/`running`/`success`/`failed`/`cancelled` |
| triggered_by | INTEGER | user_id，NULL = 定时 |
| started_at / finished_at | INTEGER | |
| files_seen / files_added / files_updated / files_removed | INTEGER | 统计 |
| books_created / books_updated | INTEGER | |
| error | TEXT | 失败原因 |
| created_at | INTEGER | 任务创建时间（epoch 秒） |

索引：`idx_scan_library_status (library_id, status)`。

### 2.13 settings

`key` TEXT PK，`value` TEXT（JSON 字符串），`updated_at` INTEGER。
存运行期可改项：默认语速、虚拟章节长度、是否允许转码、注册开关等。**不存密钥**（密钥在 `/data/config/secret.key` 与环境变量）。

### 2.14 progress_history（进度回溯点）

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | INTEGER | PK | |
| user_id | INTEGER | FK, NOT NULL | |
| book_id | INTEGER | FK, NOT NULL | |
| position_sec | REAL | NOT NULL | 全书绝对秒数 |
| track_id | INTEGER | FK tracks, ON DELETE SET NULL | |
| device_id | TEXT | | 记录时的设备 |
| created_at | INTEGER | NOT NULL | |

索引 `idx_progress_history_user_book (user_id, book_id, created_at)`。

每本最多 7 条：`PUT /progress` 被接受时，若与**任意**已有回溯点的距离 ≥ `max(5 分钟, 总时长 3%)`
（封顶 30 分钟）则新增并淘汰最旧；否则刷新最近的那条（避免「误拖后撤销」留下两条几乎相同的记录）。

### 2.15 listening_daily（每日收听）

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| user_id | INTEGER | FK, NOT NULL | |
| day | TEXT | NOT NULL | 本地日期 `YYYY-MM-DD` |
| seconds | INTEGER | NOT NULL DEFAULT 0 | 当日累计收听秒数 |
| updated_at | INTEGER | NOT NULL | |

PK `(user_id, day)`。由 `services/stats.py` 在 `PUT /progress` 被接受时累积：
只算自然播放推进（`explicit_seek` 不计、倒退不计），单次封顶 600 秒，并按 `playback_rate` 折算真实时长。

## 3. 典型查询

```sql
-- 继续收听（首页）
SELECT b.id, b.title, b.author, b.cover_path, p.position_sec, p.updated_at,
       CAST(p.position_sec * 100.0 / b.total_duration_sec AS INT) AS percent
FROM progress p JOIN books b ON b.id = p.book_id
WHERE p.user_id = ? AND p.is_finished = 0 AND b.is_missing = 0
ORDER BY p.updated_at DESC LIMIT 20;

-- 书库列表 + 进度
SELECT b.*, p.position_sec, p.is_finished
FROM books b LEFT JOIN progress p ON p.book_id = b.id AND p.user_id = ?
WHERE b.library_id = ? AND b.is_missing = 0
  AND (? IS NULL OR b.title LIKE ? OR b.author LIKE ?)
ORDER BY b.added_at DESC LIMIT ? OFFSET ?;

-- 章节定位：全书秒数 → 轨
SELECT * FROM tracks WHERE book_id = ? AND start_offset_sec >= 0
ORDER BY disc_no, track_no;
-- 服务端在内存中按累计时长二分，命中 track_id
```

## 4. 容量估算

| 数据 | 单条占用 | 10 万文件估算 |
|---|---|---|
| media_files | ~300 B | ~30 MB |
| tracks | ~150 B | ~15 MB（含 CUE 分轨后可能 3 倍） |
| chapters | ~120 B | ~12 MB |
| progress | ~80 B | 用户数 × 书数，1e4 量级 ≈ 1 MB |

结论：SQLite 单文件 100 MB 级别，完全够用。备份只需拷 `echoshelf.db` + `secret.key`。

## 5. 迁移策略

- Alembic 管理，迁移脚本入库 `backend/alembic/versions/`。
- 升级流程：容器启动时执行 `alembic upgrade head`（幂等），失败则拒绝启动并写日志（避免半迁移状态）。
- 破坏性变更需在 `docs/ADR/` 记录，并在内部变更日志标注「需备份」。
