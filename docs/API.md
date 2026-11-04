# EchoShelf HTTP API 契约（v0.2.10）

> 面向 WebUI、安卓 App 与第三方客户端。本文件与代码同步维护，**以服务端实现为准**。
> 机器可读契约：`GET /api/openapi.json`，交互式文档：`GET /api/docs`。
> 客户端按集离线下载的完整约定见 [`CLIENT_DOWNLOAD.md`](./CLIENT_DOWNLOAD.md)。

## 0. 通用约定

### 0.1 地址与版本

```
Base URL   http://<host>:8080/api/v1
OpenAPI    GET /api/openapi.json
Swagger UI GET /api/docs
```

版本通过 `GET /health` 的 `version` 暴露；破坏性变更会提升版本号并更新本文件。

### 0.2 认证

除下表外的所有接口都需要 `Authorization: Bearer <access_token>`：

| 无需认证 | 说明 |
|---|---|
| `POST /auth/login` | 登录 |
| `POST /auth/refresh` | 刷新令牌 |
| `POST /auth/logout` | 退出（幂等） |
| `POST /auth/register` | 仅在 `ECHOSHELF_ALLOW_REGISTRATION=true` 时可用，否则 403 |
| `GET /health` | 健康检查 |

- `access_token` 有效期 **30 分钟**，`refresh_token` **30 天**；刷新后旧的 refresh token 立即失效。
- 唯一例外：音频流 `GET /books/{id}/tracks/{track_id}/stream` 额外接受 `?token=<play-token>`，
  因为 `<audio>` 标签与 ExoPlayer 的原生数据源不方便加请求头。play-token 由
  `POST /books/{id}/play-token` 签发，**6 小时**有效，且只对签发时的 `book_id` 生效。

### 0.3 错误格式

```json
{ "error": { "code": "not_found", "message": "书籍不存在", "details": null } }
```

| HTTP | 默认 code | 场景 |
|---|---|---|
| 400 | `bad_request` | 参数语义错误（如 position 超出总时长、library 路径不存在） |
| 401 | `unauthorized` | 未登录 / token 过期 / 流令牌无效 |
| 403 | `forbidden` | 已登录但无权访问该书库，或非管理员调用了管理员接口 |
| 404 | `not_found` | 资源不存在 |
| 409 | `conflict` | 唯一性冲突（重复书库路径、系统已初始化） |
| 413 | `payload_too_large` | 上传超过 5 MB |
| 422 | `validation_error` | 字段校验失败，`details` 为逐字段错误数组 |
| 429 | `too_many_requests` | 登录失败次数过多 |
| 500 | `internal_error` | 服务端异常 |
| 501 | `not_implemented` | 预留能力尚未开放 |
| 503 | `service_unavailable` | 数据库不可用 / 功能被配置关闭 |

部分端点会用更精确的 code 覆盖默认值（如 `chapter_not_found`、`ffmpeg_missing`），
以各接口说明为准。

### 0.4 分页、时间与单位

- 分页参数：`page` 从 **1** 开始；`page_size` 上限按接口不同（`/books` 200、`/chapters` 500、其余 50）。
  响应统一为 `{ items, total, page, page_size }`。
- 所有时间戳为 **Unix 秒（整数）**；所有时长字段以 `_sec` 结尾、浮点秒。
- `percent` 为 **0–100** 的百分比（两位小数），不是 0–1。
- ID 均为整数；`series_index` 为浮点（支持 `1.5` 这类分卷）。

### 0.5 权限模型

| 角色 | 能力 |
|---|---|
| `user` | 读取可见书库的书籍/章节/封面，播放，写自己的进度与书签 |
| `admin` | 上述全部 + 书库增删改、扫描、书籍资料修改、封面上传/删除 |

书库可见性：`library_users` **没有任何授权行 = 全员可见**；一旦有行，则只对该清单内用户可见。
管理员始终可见全部。越权访问返回 403。

### 0.6 接口总览（56 个操作）

| 分组 | 方法 | 路径 | 权限 |
|---|---|---|---|
| | POST | `/auth/register` | 公开（受开关控制） |
| | POST | `/auth/login` | 公开 |
| | POST | `/auth/refresh` | 公开 |
| | POST | `/auth/logout` | 公开 |
| | GET | `/me` | 登录 |
| | PATCH | `/me/password` | 登录 |
| 书库 | GET | `/libraries` | 登录 |
| | POST | `/libraries` | 管理员 |
| | PATCH | `/libraries/{id}` | 管理员 |
| | DELETE | `/libraries/{id}` | 管理员 |
| | POST | `/libraries/{id}/scan` | 管理员 |
| | GET | `/libraries/{id}/scan/status` | 登录 |
| 书籍 | GET | `/books` | 登录 |
| | GET | `/books/{id}` | 登录 |
| | PATCH | `/books/{id}` | 管理员 |
| | POST | `/books/{id}/metadata/reset` | 管理员 |
| | GET | `/books/{id}/cover` | 登录 |
| | PUT | `/books/{id}/cover` | 管理员 |
| | DELETE | `/books/{id}/cover` | 管理员 |
| | GET | `/series` | 登录 |
| | GET | `/authors` | 登录 |
| 章节 | GET | `/books/{id}/chapters` | 登录 |
| | GET | `/books/{id}/chapters/cache` | 登录 |
| | DELETE | `/books/{id}/chapters/cache` | 登录 |
| | POST | `/books/{id}/chapters/{idx}/cache` | 登录 |
| | GET | `/books/{id}/chapters/{idx}/audio` | 登录 |
| 播放 | POST | `/books/{id}/play-token` | 登录 |
| | GET/HEAD | `/books/{id}/tracks/{track_id}/stream` | 登录 / 流令牌 |
| | POST | `/books/{id}/tracks/{track_id}/transcode` | 登录 |
| 进度 | GET | `/progress/{book_id}` | 登录 |
| | GET | `/progress/{book_id}/history` | 登录 |
| | PUT | `/progress/{book_id}` | 登录 |
| | DELETE | `/progress/{book_id}` | 登录 |
| 统计 | GET | `/stats` | 登录 |
| | GET | `/progress/recent` | 登录 |
| 书签 | GET | `/books/{id}/bookmarks` | 登录 |
| | POST | `/books/{id}/bookmarks` | 登录 |
| | PATCH | `/bookmarks/{id}` | 登录 |
| | DELETE | `/bookmarks/{id}` | 登录 |
| 书单 | GET | `/collections` | 登录 |
| | POST | `/collections` | 登录 |
| | GET | `/collections/{id}` | 登录（本人） |
| | PATCH | `/collections/{id}` | 登录（本人） |
| | DELETE | `/collections/{id}` | 登录（本人） |
| | POST | `/collections/{id}/books` | 登录（本人） |
| | DELETE | `/collections/{id}/books/{book_id}` | 登录（本人） |
| 用户 | GET | `/users` | 管理员 |
| | POST | `/users` | 管理员 |
| | PATCH | `/users/{id}` | 管理员 |
| | DELETE | `/users/{id}` | 管理员 |
| 设备 | GET | `/devices` | 登录 |
| | PATCH | `/devices/{id}` | 登录 |
| | POST | `/devices/{id}/presence` | 登录 |
| | DELETE | `/devices/{id}` | 登录（管理员可踢他人） |
| 系统 | GET | `/health` | 公开 |

> 文档里的路径参数写作 `{id}`、`{idx}`，与 OpenAPI 中的 `{book_id}`、`{chapter_index}` 是同一个位置参，
> 实际调用时为数字，例如 `/books/1/chapters/34/audio`。

### 0.7 典型接入顺序

```
1. POST /auth/login                       → 存 access/refresh，记住 expires_in
2. GET  /libraries                        → 决定默认库；记录 user.libraries
3. GET  /books?library_id=1&sort=added_desc → 书架（分页拉取 + q 搜索）
4. GET  /books/{id}                       → 详情：tracks + chapters + 当前进度
5. 播放：
   POST /books/{id}/play-token            → token（6h）
   GET  /books/{id}/tracks/{track}/stream?token=…   （Range 交给播放器）
   或按集离线：POST /chapters/{idx}/cache → GET /chapters/{idx}/audio?download=1
6. PUT  /progress/{id}                    → 每 15–30s 或暂停/切章时上报（带 client_updated_at）
7. 其他：书签 /books/{id}/bookmarks；系列 GET /series
```

客户端约定补充：`access_token` 过期用 `POST /auth/refresh` 换新；`PUT /progress` 返回
`accepted=false` 时以服务端值为准。

---

## 1. 认证 `/auth`

### 管理员初始化（不在 API 内）

`POST /auth/bootstrap` **已移除**（返回 404/405）。管理员只能带外创建，网页端没有入口：

```bash
# Docker
docker exec -it shelf python -m app.cli admin create
docker exec -it shelf python -m app.cli admin reset-password

# 常规部署
sudo -u echoshelf /opt/echoshelf/bin/echoshelf admin create
```

容器里设置 `ECHOSHELF_ADMIN_PASSWORD`（或 `ECHOSHELF_ADMIN_PASSWORD_FILE`）时，
**首次启动**会自动创建；默认库里已有用户时**不覆盖**密码（重启改环境变量无效是预期行为）。
需要让环境变量持续生效时设 `ECHOSHELF_ADMIN_SYNC_PASSWORD=true`：每次启动比对并更新管理员密码，
同时吊销旧 refresh token；密码没变则不动。系统只允许一个管理员，
`POST /users` 与 `PATCH /users/{id}` 都**不接受** `role="admin"`（422）。

### POST /auth/register

自助注册，仅在 `ECHOSHELF_ALLOW_REGISTRATION=true` 时开放，否则 403。

```json
{ "username": "alice", "password": "至少8位", "display_name": "Alice",
  "device": { "id": "android-xyz", "name": "Pixel 8", "platform": "android" } }
```

`201` → `TokenResponse`（直接登录）。新账号角色固定 `listener`，**没有任何书库授权**，
需要管理员在 `PATCH /users/{id}` 里分配；重复用户名 409。

### POST /auth/login

```json
{ "username": "admin", "password": "******",
  "device": { "id": "android-abc123", "name": "Pixel 8", "platform": "android",
              "app_version": "0.2.10", "os": "Android 14",
              "form_factor": "phone", "screen": "1080×2400 · 2.6x",
              "user_agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8) …" } }
```

`device` 可省略；带上后会登记到设备列表，并让进度按设备区分。
同一用户名连续失败 5 次会短暂返回 429。

`200` → `TokenResponse`：

```json
{ "access_token": "eyJ...", "refresh_token": "rt_...", "expires_in": 1800,
  "user": { "id": 1, "username": "admin", "display_name": "管理员",
            "role": "admin", "libraries": [1], "created_at": 1792772955 } }
```

### POST /auth/refresh

```json
{ "refresh_token": "rt_..." }
```

`200` → 新的 `TokenResponse`（**旧 refresh token 立即失效，必须替换**）。
失效/过期返回 401。

### POST /auth/logout

```json
{ "refresh_token": "rt_..." }
```

`204`。幂等：token 不存在也返回 204。

### GET /me

`200` → `UserOut`。

### PATCH /me/password

```json
{ "old_password": "...", "new_password": "至少8位" }
```

`204`。修改后该用户**所有** refresh token 失效，客户端需要重新登录。

---

## 2. 书库 `/libraries`

### GET /libraries

`?page=1&page_size=50`

```json
{ "items": [ { "id": 1, "name": "有声书", "root_path": "/audiobooks",
               "enabled": true, "book_count": 4, "total_duration_sec": 832408.85,
               "last_scan_at": 1792781879,
               "scan": { "status": "success", "finished_at": 1792781879 } } ],
  "total": 1, "page": 1, "page_size": 50 }
```

`scan` 是最新一次扫描的简报（`status`：`pending|running|success|failed`），从未扫描时为 `null`。

> 管理员调用时 `items` 还包含 `enabled=false` 的**停用书库**（便于在设置页再次启用）；普通用户只返回启用且已授权的库。

### POST /libraries（管理员）

```json
{ "name": "有声书", "root_path": "/audiobooks", "user_ids": [1] }
```

- `root_path` 是**服务端容器内路径**，必须已存在，否则 400；Docker 部署时必须位于 `/audiobooks` 下；重复路径 409。
- `user_ids` 省略/空数组 = 全员可见（不写授权行）。

`201` → `LibraryOut`。

> 若 `root_path` 命中一条**已停用**记录，会直接重新启用并更新名称/授权（不再 409）；只有 `enabled=true` 的同路径才返回 409。目录存在但容器用户不可读时返回 400。

### PATCH /libraries/{id}（管理员）

```json
{ "name": "英文有声书", "enabled": true, "user_ids": [1, 2] }
```

字段可只传一部分；`user_ids: []` 表示恢复为全员可见。`200` → `LibraryOut`。

### DELETE /libraries/{id}（管理员）

`204`。该库下的书籍、章节、媒体记录一并删除，**不动磁盘文件**。

### POST /libraries/{id}/scan（管理员）

触发后台扫描，立即返回，不阻塞。

`202` → `{ "task_id": 12, "status": "pending" }`

### GET /libraries/{id}/scan/status

```json
{ "task_id": 12, "status": "success",
  "started_at": 1792781860, "finished_at": 1792781879,
  "files_seen": 4, "files_added": 0, "files_updated": 0, "files_removed": 0,
  "books_created": 0, "books_updated": 0, "error": null }
```

`status` 为 `success` / `failed` 即结束；`error` 里有失败原因。客户端建议 1 秒轮询。

---

## 3. 书籍 `/books`

### GET /books

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `library_id` | int | — | 只看某个库；无权限返回 403 |
| `q` | string(≤256) | — | 全文检索：书名 / 副标题 / 作者 / 讲述者 / 系列 / 简介（见下方说明） |
| `author` | string(≤256) | — | 作者精确匹配 |
| `series` | string(≤256) | — | 系列名精确匹配 |
| `include_hidden` | bool | `false` | **仅管理员**：把管理员隐藏的书也列出来；普通用户传 `true` 得 403 |
| `sort` | enum | `added_desc` | 见下 |

**搜索（`q`）的实现**：`books_fts` 是 FTS5 虚拟表（迁移 `0007`），tokenizer 用 `trigram`，
正文仍在 `books` 表里（external content），由三个触发器自动同步增删改。

- 查询词按空格拆开，逐个词判断：
  - **长度 ≥3 的词** → 拼进一个 `MATCH`，中文按子串命中（`东林皆` → `间客·第一卷 东林皆石`）
  - **长度 1–2 的词**（`三体`、`猫腻`）→ trigram 产生不了词元，退回 `LIKE %x%`，
    只在 书名 / 作者 / 系列名 里匹配（此时不查简介）
  - 两类条件在 SQL 里 AND，所以 `刘慈欣 闪电` 这种混搭也能查
- 用户输入会被包成带引号的短语，`*`、`-`、`OR` 之类不会被当成 FTS 语法
- 被管理员隐藏的书（`hidden=1`）不参与搜索、系列与作者聚合，普通用户直接访问详情得 404

十万行实测（本机 SQLite）：

| 查询 | FTS | LIKE |
|---|---|---|
| 6 字精确（命中 1 行） | 0.1 ms | 28.1 ms |
| 5 字作者（命中 2200 行） | 1.0 ms | 29.4 ms |
| 4 字宽泛（命中 100000 行） | 38.2 ms | 43.1 ms |
| `filter` | enum | `all` | 见下 |
| `page` / `page_size` | int | 1 / 50 | `page_size` ≤ 200 |

`sort`：`added_desc`（最近入库）、`title_asc`、`author_asc`、`duration_desc`、
`progress_desc`（最近在听）、`series_asc`（卷号升序，无卷号排最后）。

`filter`：`all`、`in_progress`（有进度未听完）、`finished`、`unplayed`（从未播放）、
`downloaded`。⚠️ `downloaded` 在服务端**恒为空**——下载状态只存在于客户端，见
[`CLIENT_DOWNLOAD.md`](./CLIENT_DOWNLOAD.md)。

```json
{ "items": [ { "id": 1, "library_id": 1, "title": "间客·第一卷 东林皆石",
               "author": "猫腻", "narrator": null, "series_name": "间客",
               "series_index": 1.0, "language": null,
               "cover_url": "/api/v1/books/1/cover?size=thumb",
               "manual_override": false, "hidden": false, "total_duration_sec": 39269.87,
               "track_count": 1, "size_bytes": 635694933,
               "chapter_source": "embedded", "added_at": 1792772955,
               "progress": { "position_sec": 19011.796, "percent": 48.41, "is_finished": false } } ],
  "total": 4, "page": 1, "page_size": 1 }
```

`progress` 为当前用户的进度，未播放过是 `null`。`cover_url` 为相对路径，自己拼 host；
即使没有封面文件也会给出该地址（服务端返回内置占位图）。

### 系列名（`series_name`）的来源

优先级：音频标签的 `series` → **多文件书的父文件夹名** → 书名里的「第N卷」。

书名（`title`）规则：**多文件书直接取文件夹名**（`消失大陆的爱情/` → `消失大陆的爱情`；
跳过 `CD1`/`Disc2` 这类分盘目录取上一级），单文件书仍用标签 `title`。
这样文件夹里各章的标题（如 `钟楼街的游行`）或文件名里的序号（`…爱情1.mp3`）不会再变成书名。

- 按文件夹归组的多 MP3 书：`间客/Ⅰ第一卷 东林皆石/` → 系列 `间客`，卷号 `1`
  （卷号从目录名解析：`第N卷` / `Ⅰ–Ⅻ` / 前导数字）
- 顶层单本目录（`消失大陆的爱情/`）没有父目录，不建只有一个成员的系列
- 单文件书（一本一个 m4b）不按目录推断，避免把「作者/书名」的作者目录变成系列

### GET /books/{id}

被隐藏的书：管理员照常打开，普通用户得 404。

比列表多出 `subtitle`、`publisher`、`publish_year`、`description`、`rel_dir`、`is_missing`、
`updated_at`、**全量 `tracks`** 与 **全量 `chapters`**：

```json
{ "...": "BookOut 全部字段",
  "rel_dir": "猫腻/间客", "is_missing": false, "updated_at": 1792782765,
  "tracks": [ { "id": 1, "track_no": 1, "disc_no": 1, "title": "间客 第一卷 东林皆石",
                "duration_sec": 39269.87, "format": "m4b", "bitrate": 127,
                "stream_url": "/api/v1/books/1/tracks/1/stream" } ],
  "chapters": [ { "id": 1, "idx": 0, "title": "001 钟楼街的游行",
                  "start_sec": 0.0, "end_sec": 797.591, "track_id": 1 } ] }
```

注意：`stream_url` **不带 token**，播放前需先取 play-token 并自行拼 `?token=`。
章节很多时优先用分页的 `GET /books/{id}/chapters`。

### PATCH /books/{id}（管理员）

PATCH 语义，只改传入字段；**空字符串表示清空**。`hidden` 仅管理员可改（普通上传者 403），
且只切隐藏状态时**不会**置 `manual_override=true`。改其它字段会置 `manual_override=true`，
后续扫描不再覆盖这些字段。

```json
{ "title": "间客 第一卷", "author": "猫腻", "narrator": "某某",
  "publisher": "起点", "publish_year": 2009, "language": "zh",
  "series_name": "间客", "series_index": 1, "description": "……",
  "intro_sec": 15, "outro_sec": 10 }
```

`200` → `BookOut`。`intro_sec` / `outro_sec` 是**书籍默认的**跳过片头/片尾秒数（0 表示不跳），
两者相加不能超过 `total_duration_sec`，否则 `400`。
Web 客户端现在优先使用「播放偏好」里的**设备级秒数**（填 0 才回退到这里），并按**每个音频文件（每集）**跳：
切集跳片头、当前轨结尾跳片尾；单文件含章节只在整本首尾生效。

### POST /books/{id}/metadata/reset（管理员）

清除手工覆盖标记（`manual_override=false`），字段回到扫描推断值。`200` → `BookOut`。

### GET /books/{id}/cover

`?size=thumb|full`（默认 `thumb`）。

- `200`，`Content-Type: image/jpeg|image/png`，带 `ETag` 与 `Cache-Control: public, max-age=86400`
- 没有封面时返回**内置占位图**（仍是 200），所以可以直接放进 `<img>`
- 支持 `If-None-Match`，命中返回 304

### PUT /books/{id}/cover（管理员）

`multipart/form-data`，字段名 **`file`**，限制 **5 MB**，支持 JPEG / PNG / WebP。

- 400：文件为空或无法识别的图片格式
- 413：超过 5 MB

`200` → `BookOut`（`cover_url` 已更新，`cover_uploaded_by` 记录上传者 id）。
需要 `editor` 或 `admin`。

### DELETE /books/{id}/cover（管理员）

`200` → `BookOut`（`cover_url` 变为占位图地址，`cover_uploaded_by` 清空）。
需要 `editor` 或 `admin`；`editor` 只能删除**自己上传的**封面（扫描抽取的封面只有管理员能删），否则 `403`。

### GET /series

按 `series_name` 汇总，供书架「系列」视图使用。

```json
{ "items": [ { "name": "间客", "book_count": 4, "total_duration_sec": 832408.9,
               "cover_book_id": 1, "cover_url": "/api/v1/books/1/cover?size=thumb",
               "latest_added_at": 1792772955 } ] }
```

- `cover_book_id` 取卷号最小的一本（`series_index` 为空排最后）
- `cover_url` 仅在封面文件**真实存在**时给出，否则为 `null`（客户端应改用书名渐变占位）
- 只统计可见书库、未标 missing、`series_name` 非空的书

### GET /authors

按 `author` 汇总，供「作者」视图使用（一人多书很常见）。

```json
{ "items": [ { "name": "猫腻", "book_count": 4, "total_duration_sec": 832408.9,
               "cover_book_id": 1, "cover_url": "/api/v1/books/1/cover?size=thumb",
               "latest_added_at": 1792772955 } ] }
```

- 按「最近添加」倒序
- `cover_book_id` 优先取**有封面文件**的一本，其次任意一本
- `cover_url` 仅在封面文件真实存在时给出，否则为 `null`
- 只统计可见书库、未标 missing、`author` 非空的书
- WebUI 在「书库」右上角的「作者」入口进入 `/authors`，点卡片跳
  `/library?author=<名字>`，书库页会按作者筛选并显示横幅

---

## 4. 章节与按集下载

完整的客户端下载约定（续传、并发、错误重试、进度换算）见
[`CLIENT_DOWNLOAD.md`](./CLIENT_DOWNLOAD.md)，此处只列契约。

### GET /books/{id}/chapters

`?page=1&page_size=100`（≤ 500）

```json
{ "items": [ { "id": 1, "idx": 0, "title": "001 钟楼街的游行",
               "start_sec": 0.0, "end_sec": 797.591, "track_id": 1 } ],
  "total": 61, "page": 1, "page_size": 2 }
```

- `idx` 从 0 开始，是全书顺序；**界面上的「第 35 集」= `idx=34`**
- `start_sec` 是**全书绝对秒**，跨轨书需要减掉轨偏移才是文件内位置
- 章节来源见 `chapter_source`：`embedded`（文件内嵌）/ `cue`（CUE 分轨）/ `track_split`（多文件按轨切）/
  `virtual`（按时长切分）/ `manual`（手工编辑过）

### POST /books/{id}/chapters/{idx}/cache

预生成该集的独立音频切片，幂等。`200` → `ChapterAudioOut`：

```json
{ "book_id": 1, "index": 34, "title": "035 逃难的小西瓜",
  "cache_key": "0034-1791869584-635694933.m4a", "bytes": 11311295,
  "content_type": "audio/mp4", "start_sec": 19520.494, "duration_sec": 699.0,
  "created": true }
```

`cache_key` = `集号-源文件mtime-源文件size.扩展名`，是**版本号**：源文件被替换后它会变。
`created=false` 表示命中已有缓存。

### GET /books/{id}/chapters/{idx}/audio

`?download=1` 时附带 `Content-Disposition`。支持 `Range`：

```
206 Partial Content
Content-Type: audio/mp4
Content-Range: bytes 0-11311294/11311295
X-Chapter-Cache: hit
```

错误：404 `chapter_not_found` / `media_missing`，409 `chapter_empty`，
502 `slice_failed`，503 `chapter_cache_disabled` / `ffmpeg_missing` / `transcode_disabled`。

### GET /books/{id}/chapters/cache

```json
{ "items": [ { "book_id": 1, "index": 34, "title": "035 逃难的小西瓜",
               "cache_key": "0034-1791869584-635694933.m4a", "bytes": 11311295,
               "content_type": "audio/mp4", "start_sec": null, "duration_sec": null,
               "created": false } ],
  "total_bytes": 11311295 }
```

### DELETE /books/{id}/chapters/cache

`204`。只删服务端缓存，不影响客户端已下载的文件。

---

## 5. 播放 `/books/{id}/play-token`、`/tracks/{id}/stream`

### POST /books/{id}/play-token

```json
{ "token": "eyJ...", "expires_in": 21600, "expires_at": 1792872329 }
```

- 有效期 **6 小时**，只对签发的 `book_id` 与当前用户有效
- 供 `<audio>` / ExoPlayer 这类无法加请求头的数据源使用

### GET /books/{id}/tracks/{track_id}/stream

| 参数 | 说明 |
|---|---|
| `token` | play-token；也可以用 `Authorization: Bearer` |
| `transcode` | `opus` / `mp3`；不传则直出原文件 |
| `bitrate` | 16–320（kbps），默认 64 |

- 直接读原文件，支持 `Range`（`206` + `Content-Range`），64 KB 分块流式输出，不落盘、不缓存
- `Accept-Ranges: bytes`；越界/非法 Range 返回 416
- `HEAD` 同路径可拿 `Content-Length` 与 `Content-Type`，适合探测与预分配

```http
GET /api/v1/books/1/tracks/1/stream?token=eyJ... HTTP/1.1
Range: bytes=19520000-
→ 206 Partial Content, Content-Range: bytes 19520000-635694932/635694933
```

**转码**（wma / ape 等浏览器不支持的格式，M6 起支持）：

- 整轨转码一次落盘 `${DATA}/cache/transcode/{book_id}/`，之后所有 Range 请求直接读缓存
- 缓存键含源文件 `mtime + size + 编码 + 码率`，源文件变了旧产物自动失效并清理
- 响应头：`X-Transcode: opus/64`、`X-Transcode-Cache: hit|miss`（未转码时为 `off`）
- 产物：`opus` → WebM（`audio/webm`）；`mp3` → `audio/mpeg`
- 同一轨并发请求串行化，先写临时文件再 `os.replace`，不会读到半成品
- 单轨时长超过 `ECHOSHELF_TRANSCODE_MAX_DURATION_SEC`（默认 2 小时）直接 **413 `transcode_too_long`**，
  避免一次请求挂几十分钟；这种超长文件请改用按集切片（见第 4 节）
- 缓存总量超过 `ECHOSHELF_TRANSCODE_MAX_BYTES`（默认 4 GiB）按最旧优先清理

### POST /books/{id}/tracks/{track_id}/transcode

播放前预生成转码文件，避免首播等待；WebUI 不调用，给客户端用。

| 参数 | 说明 |
|---|---|
| `codec` | `opus`（默认）/ `mp3` |
| `bitrate` | 16–320，默认 64 |

```json
{ "track_id": 1, "codec": "opus", "bitrate": 64, "bytes": 2896123,
  "content_type": "audio/webm",
  "cache_key": "000001-1792853410-4134944-opus-64.webm",
  "duration_sec": 300.055, "created": true }
```

`created=false` 表示命中已有缓存。

错误码：400 `transcode_unsupported`（格式/码率非法）、413 `transcode_too_long`、
502 `transcode_failed` / `transcode_timeout`、503 `transcode_disabled` / `ffmpeg_missing`。

WebUI 的接入方式：`track.format` 不在浏览器可播列表（mp3 / m4a / m4b / aac / flac / ogg / opus / wav / webm）时，
播放地址自动附加 `transcode=opus&bitrate=64`。

Android 端用 ExoPlayer 直接把该 URL 作为数据源即可；seek 由播放器自动发新的 Range 请求。

---

## 6. 进度 `/progress`

`position_sec` 始终是**全书绝对秒**（不是当前轨内的秒）。

### GET /progress/{book_id}

```json
{ "book_id": 1, "position_sec": 19011.796, "track_id": 1,
  "track_position_sec": 19011.796, "playback_rate": 1.0,
  "is_finished": false, "device_id": "android-abc123",
  "client_updated_at": 1792848242, "updated_at": 1792848242 }
```

从未播放过时返回 **200 + 零值**（`position_sec=0`、`updated_at=0`、`is_finished=false`），不是 404。

### PUT /progress/{book_id}

```json
{ "track_id": 1, "position_sec": 19011.796, "playback_rate": 1.0,
  "device_id": "android-abc123", "client_updated_at": 1792848242,
  "explicit_seek": false, "finished": false }
```

| 字段 | 说明 |
|---|---|
| `position_sec` | 必填，全书绝对秒；超过总时长 + 容差返回 400 |
| `client_updated_at` | 必填，客户端发生播放的时间（Unix 秒），用于冲突合并 |
| `explicit_seek` | 用户主动拖动/跳章时传 true（优先级更高） |
| `finished` | 客户端判定已听完；服务端也会在接近结尾时自动置位 |
| `track_id` | 可省略，服务端会按 `position_sec` 自动定位 |

`200` → `{ book_id, position_sec, track_id, accepted, is_finished, updated_at }`

`accepted=false` 表示这次写入比服务端现有状态旧（例如离线设备补传），服务端保留新值，
**客户端应以返回的 `position_sec` 覆盖本地**。这就是多端并发的收敛方式。

### DELETE /progress/{book_id}

`204`，清除当前用户在该书上的进度。

### GET /progress/{book_id}/history

该账号在这本书上的**进度回溯点**，最多 7 条，新 → 旧。

```json
{ "items": [ { "id": 12, "position_sec": 20694.0, "track_id": 1,
               "device_id": "web-gs7oqskm", "created_at": 1792856120 },
             { "id": 9, "position_sec": 5000.0, "track_id": 1,
               "device_id": "web-gs7oqskm", "created_at": 1792855300 } ] }
```

权威进度仍然只有一条（`progress` 表）；这里只是额外的回溯点，用来在误拖进度、
多设备互相覆盖之后找回之前听的位置。写入时机由服务端决定：

- 每次 `PUT /progress` 被接受时检查，**位置差异达到阈值**才新增一条
- 阈值 = `max(5 分钟, 全书总时长 × 3%)`，并封顶 30 分钟
  - 30 分钟的书：5 分钟就算换了地方
  - 10 小时的书：约 18 分钟
- 差异小于阈值时只刷新最新那一条的位置与时间，不会产生大量无意义快照
- 始终只保留最新 3 条，第 4 条写入时最旧的被淘汰
- 与**任意**已有回溯点足够近时刷新那一条（不是只比较最新一条），
  所以「误拖出去再撤销回来」不会在列表里留下两条几乎相同的位置
- `DELETE /progress/{book_id}` 会连同该书的回溯点一起清空

WebUI 在播放器右侧栏的「进度」页签展示，点一条即 `seekTo(position_sec)` 恢复
（会以 `explicit_seek=true` 回写，因此可以往回跳）。

### GET /progress/recent

`?limit=20`（≤ 100）

```json
{ "items": [ { "book_id": 1, "title": "间客·第一卷 东林皆石", "author": "猫腻",
               "cover_url": "/api/v1/books/1/cover?size=thumb",
               "position_sec": 19011.796, "total_duration_sec": 39269.87,
               "percent": 48.41, "updated_at": 1792848242,
               "device_id": "web-gs7oqskm" } ] }
```

按 `updated_at` 倒序，只包含可见书库，`is_finished` 的书不出现。
`device_id` 是最后写这条进度的设备，客户端用它区分「是不是我自己写的」。

### 跨设备接续（客户端应该怎么做）

进度是**账号级**的：`progress` 表主键是 `(user_id, book_id)`，一个账号一本书只有一条，
所有设备的读写都落在同一行。因此客户端必须按下面的节奏对齐，否则会出现
「电脑听着 A 书、手机还停在 B 书」这种各播各的情况：

1. **冷启动 / 打开书本**：用 `GET /books/{id}` 返回的 `progress.position_sec` 作为起点（不要用本地缓存）
2. **回到前台 / 页面可见**：`GET /progress/recent`，取**最近 2 分钟内、`device_id` 不是自己**的那一条
   - 同一本书且当前是暂停状态 → `seekTo(position_sec)` 直接跟随过去
   - 换了一本书 → 弹提示「另一台设备正在听《X》」，用户点「接续」再打开
3. **开始播放时立刻 `PUT /progress`**：谁最后按下播放，账号进度就归谁，切设备时行为可预期
4. **播放中不要被远端打断**：只有暂停状态才跟随，避免两台设备互相拉扯

WebUI 已按此实现（`web/src/store/player.ts` 的 `syncFromServer()` +
`components/player/ProgressSyncToast.tsx`）。

---

### GET /stats

收听统计（独立路由，tag `stats`）。数据在 `PUT /progress` 被接受时累积：

```json
{ "today_sec": 600, "total_sec": 9360, "streak_days": 5,
  "days": [ { "day": "2026-10-19", "seconds": 0 },
            { "day": "2026-10-20", "seconds": 900 },
            { "day": "2026-10-25", "seconds": 600 } ] }
```

- `days` 固定返回最近 N 天（默认 7，`?days=` 可取 1–30），升序，缺失的日子补 0
- `streak_days`：从今天往前数连续有记录的天数；**今天还没听不算断签**，从昨天开始数
- 计入口径（`services/stats.py`）：
  - 只算自然播放推进 `新位置 - 旧位置`；`explicit_seek=true`（拖进度条/跳章）不计
  - 位置倒退不计
  - 单次最多计 600 秒，避免离线设备补传时把大段空白算成收听
  - 按 `playback_rate` 折算：2 倍速下 60 秒进度 ≈ 30 秒真实收听
- 按服务器本地时区划分自然日（`YYYY-MM-DD`）

---

## 7. 书签

书签的 `position_sec` 同样是**全书绝对秒**。

### GET /books/{id}/bookmarks

`200` → `BookmarkOut[]`（数组，不分页）：

```json
[ { "id": 3, "book_id": 1, "position_sec": 8821.5, "track_id": 1,
    "note": "许乐第一次出手", "created_at": 1792800000 } ]
```

### POST /books/{id}/bookmarks

```json
{ "position_sec": 8821.5, "track_id": 1, "note": "许乐第一次出手" }
```

`201` → `BookmarkOut`。

### PATCH /bookmarks/{bookmark_id}

```json
{ "note": "改个备注" }
```

`200` → `BookmarkOut`。

### DELETE /bookmarks/{bookmark_id}

`204`。

---

## 8. 个人书单 `/collections`

书单是当前登录用户的私有数据，接口只能操作自己的书单；书籍仍受书库权限和隐藏规则约束。

### GET /collections

`?book_id=123` 可选：额外返回每个书单是否包含这本书，用于详情页的「加入书单」勾选状态。

```json
{ "items": [
  { "id": 1, "name": "睡前推理", "book_count": 2, "created_at": 1792800000,
    "cover_url": "/api/v1/books/12/cover?size=thumb", "contains_book": true }
] }
```

### POST /collections

```json
{ "name": "睡前推理" }
```

`201` → `CollectionOut`。同名返回 `409`，名称最长 64 字。

### GET /collections/{id}

`200` → `CollectionDetail`，在 `CollectionOut` 基础上增加 `books`（`BookOut[]`，按加入时间倒序）。

### PATCH /collections/{id}

```json
{ "name": "新名字" }
```

`200` → `CollectionOut`。

### DELETE /collections/{id}

`204`。删除书单不会删除书籍。

### POST /collections/{id}/books

```json
{ "book_id": 123 }
```

`200` → `CollectionOut`。重复加入幂等。

### DELETE /collections/{id}/books/{book_id}

`204`。书籍不在书单中也返回成功（幂等）。

---

## 9. 用户管理 `/users`（仅管理员）

### 角色与权限

| 角色 | 说明 | 可改资料/封面 | 删封面 | 删书库/扫描 | 用户管理 |
|---|---|---|---|---|---|
| `admin` | 管理员 | ✅ | ✅ 任意 | ✅ | ✅ |
| `editor` | 上传者 | ✅ | 仅自己上传的 | ❌ | ❌ |
| `listener` | 听众（默认） | ❌ | ❌ | ❌ | ❌ |

所有角色都可以收听、上报进度、管理自己的书签与设备、查看统计。
**管理员唯一且只能带外创建**：接口不接受 `role="admin"`，网页端也没有初始化入口。
写接口用 `403`（`error.code = forbidden`）拒绝越权；旧数据里的 `role="user"` 按 `listener` 处理，
但接口**不再接受** `role="user"`（`422`），创建时请传三个新值之一。

书库授权有两种等价写法：`PATCH /users/{id}` 的 `library_ids`，或
`PATCH /libraries/{id}` 的 `user_ids`——两者都写 `library_users` 表。

### GET /users

`?q=&page=1&page_size=50`（`q` 模糊匹配用户名/显示名）。

```json
{ "items": [ { "id": 1, "username": "demo", "display_name": "demo",
               "role": "admin", "is_active": true, "libraries": [1],
               "created_at": 1792772955, "last_login_at": 1792872329 } ],
  "total": 2, "page": 1, "page_size": 50 }
```

`libraries` 是**生效中**的可见书库（公开库 + 显式授权），与 `/me` 口径一致。

### POST /users

```json
{ "username": "alice", "password": "至少8位", "display_name": "Alice",
  "role": "listener", "library_ids": [1] }
```

`201` → `UserAdminOut`。用户名统一转小写，重复返回 409。

### PATCH /users/{id}

```json
{ "display_name": "Alice", "role": "editor", "is_active": true,
  "password": "新密码至少8位", "library_ids": [1, 2] }
```

字段均可省略：

| 行为 | 影响 |
|---|---|
| `library_ids` | 整体替换该用户的授权集合，`[]` 表示取消单独授权（公开库仍可见） |
| `is_active=false` | 停用账号：立即吊销其所有 refresh token，旧 access token 也立即 401 |
| `password` | 重置密码：旧会话全部失效，新密码立即可用 |
| `role` | 改角色：`admin` / `editor` / `listener` |

保护规则（409）：不能修改自己的角色、不能停用/删除自己、不能把最后一个可用管理员降级或停用。

### DELETE /users/{id}

`204`。该用户的进度、书签、设备、refresh token 随外键级联删除。
同样受「不能删自己 / 不能删最后一个管理员」保护。

## 10. 设备 `/devices`

设备在登录或注册时用客户端生成的 `device.id` 登记。`online` 的判定是三者同时成立：

1. 未被踢下线（`revoked_at` 为空）
2. 没有主动上报离线（`offline_at` 为空）
3. **120 秒内有心跳**（`last_seen_at` 在窗口内）

只靠第 3 条会有明显延迟：用户关掉页面后，服务端要等窗口过期才知道。所以客户端应主动上报
（见本节末尾的 `POST /devices/{id}/presence`）：WebUI 已实现「可见时 45 秒心跳、隐藏 20 秒后离线、
`pagehide` 立即离线」。

### GET /devices

`?all=true` 仅管理员有效，返回所有用户的设备（多带 `username`）。

```json
{ "items": [ { "id": "web-dymrmm7k", "user_id": 1, "username": "demo",
               "name": "Chrome 141", "platform": "web", "app_version": "0.2.10",
               "os": "Android 14", "form_factor": "phone", "screen": "390×844 · 3x",
               "user_agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8) … Chrome/141.0.0.0 Mobile Safari/537.36",
               "created_at": 1792852192, "last_seen_at": 1792872329,
               "revoked_at": null, "offline_at": null, "online": true } ] }
```

| 字段 | 说明 |
|---|---|
| `name` | 展示名，客户端自报：网页端是「浏览器 + 主版本」，安卓建议「机型」 |
| `os` / `form_factor` / `screen` | 系统、形态（`phone`/`tablet`/`desktop`）、屏幕分辨率；旧客户端不传则为 `null` |
| `user_agent` | 原始 UA（最长 512 字符），网页端设置页可展开查看 |
| `created_at` | 首次登记时间；`last_seen_at` 为最近一次带该设备令牌的请求时间 |

登录时这些字段都是可选的；**只传部分字段不会清空已有信息**（便于老客户端升级过程中混用）。

### PATCH /devices/{id}

```json
{ "name": "Pixel 8 Pro" }
```

改名。只能改自己的设备（管理员可改任意设备）。

### POST /devices/{id}/presence

在线心跳 / 主动下线，供客户端在生命周期变化时调用。

```json
{ "online": true }
```

`200` → `DeviceOut`。

| 请求 | 效果 |
|---|---|
| `{"online": true}` | 刷新 `last_seen_at`，清除 `offline_at`（页面重新可见 / App 回到前台） |
| `{"online": false}` | 写入 `offline_at`（关闭页面 / 切后台超时 / App 退到后台） |

- 只能操作自己的设备，管理员可代操作
- 任何带该设备令牌的请求也会自动清除 `offline_at`，所以这只是**展示状态**，不影响鉴权
- `keepalive` 请求可在页面卸载过程中送达（WebUI 用 `fetch(..., { keepalive: true })`）
- 崩溃/断网等没来得及上报的情况，由 120 秒窗口兜底

推荐节奏（WebUI 实现，安卓可照做）：

| 时机 | 上报 |
|---|---|
| 页面可见 / `pageshow` / App 回前台 | `online=true`，之后每 45 秒一次心跳 |
| 页面隐藏 / App 切后台，但**正在播放** | 不上报离线，继续心跳（听书本来就是后台行为） |
| 页面隐藏且未播放，超过 20 秒 | `online=false` |
| `pagehide` 且未播放 / App 退出 | `online=false` |

播放期间播放器每 15 秒还会上报一次 `PUT /progress`，同样会刷新 `last_seen_at`，两道信号互为兜底。
如果用户直接关掉正在播放的标签页（音频随之停止），则依赖 120 秒窗口过期后转为离线。

### DELETE /devices/{id}

踢下线，`204`。语义：

- 该设备所有 refresh token 立即吊销
- access token 带 `did` 声明，服务端每次请求校验设备状态，因此**旧 access token 也立即 401**，
  不用等 30 分钟自然过期
- 设备下次登录会自动恢复（清空 `revoked_at`），是「踢下线」而不是永久封禁
- 只能踢自己的设备；管理员可踢任意设备（用于「我的设备」页清理）

## 11. 系统

### GET /health（公开）

```json
{ "status": "ok", "version": "0.2.10", "db": "ok", "ffmpeg": true,
  "libraries": 1, "books": 4, "uptime_sec": 505,
  "transcode": { "enabled": true, "active": 1, "completed": 12 } }
```

`db` 异常时返回 503。容器 healthcheck 与客户端启动自检都用它。

> `libraries` 是**已登记书库总数**（含停用）；`books` 是未隐藏、未缺失的书籍数。
`transcode.active` 是当前正在转码的任务数（0 表示空闲），`completed` 为进程启动以来完成的次数——用来观察转码占用的 CPU。

---

## 12. 数据模型

| 模型 | 字段 |
|---|---|
| `TokenResponse` | `access_token` `refresh_token` `expires_in` `user:UserOut` |
| `UserOut` | `id` `username` `display_name?` `role` `libraries:int[]` `created_at` |
| `UserAdminOut` | `UserOut` + `is_active` `last_login_at?` |
| `DeviceOut` | `id` `user_id` `username?` `name?` `platform?` `app_version?` `os?` `form_factor?` `screen?` `user_agent?` `created_at?` `last_seen_at?` `revoked_at?` `offline_at?` `online` |
| `BookOut` | `id` `library_id` `title` `author?` `narrator?` `series_name?` `series_index?` `language?` `cover_url?` `cover_uploaded_by?` `manual_override` `hidden` `total_duration_sec` `intro_sec` `outro_sec` `track_count` `size_bytes` `chapter_source?` `added_at` `progress?` |
| `BookDetail` | `BookOut` + `subtitle?` `publisher?` `publish_year?` `description?` `rel_dir?` `is_missing` `updated_at` `tracks:TrackOut[]` `chapters:ChapterOut[]` |
| `TrackOut` | `id` `track_no` `disc_no` `title?` `duration_sec` `format?` `bitrate?` `stream_url` |
| `TranscodeOut` | `track_id` `codec` `bitrate` `bytes` `content_type` `cache_key` `duration_sec?` `created` |
| `ChapterOut` | `id` `idx` `title` `start_sec` `end_sec?` `track_id` |
| `ChapterAudioOut` | `book_id` `index` `title?` `cache_key` `bytes` `content_type` `start_sec?` `duration_sec?` `created` |
| `SeriesOut` | `name` `book_count` `total_duration_sec` `cover_book_id?` `cover_url?` `latest_added_at` |
| `LibraryOut` | `id` `name` `root_path` `enabled` `book_count` `total_duration_sec` `last_scan_at?` `scan:ScanBrief?` |
| `ScanStatusOut` | `task_id` `status` `started_at?` `finished_at?` `files_seen` `files_added` `files_updated` `files_removed` `books_created` `books_updated` `error?` |
| `ProgressOut` | `book_id` `position_sec` `track_id?` `track_position_sec` `playback_rate` `is_finished` `device_id?` `client_updated_at` `updated_at` |
| `ProgressHistoryItem` | `id` `position_sec` `track_id?` `device_id?` `created_at` |
| `StatsOut` | `today_sec` `total_sec` `streak_days` `days[]` (`day` `seconds`) |
| `RecentProgressItem` | `book_id` `title` `author?` `cover_url?` `position_sec` `total_duration_sec` `percent` `updated_at` `device_id?` |
| `BookmarkOut` | `id` `book_id` `position_sec` `track_id?` `note?` `created_at` |

字段名带 `?` 的可以为 `null`。

---

## 13. 未实现（规划中，**请勿依赖**）

下列接口在早期设计文档里出现过，但**服务端尚未实现**，调用会得到 404 或 501：

| 规划接口 | 现状 | 替代方案 |
|---|---|---|
| `GET /search?q=` | 未实现 | 用 `GET /books?q=`（模糊匹配书名/作者/系列） |
| `/collections`（书单） | 未实现 | 用 `series` + `author` 归组；跨系列合集待做 |
| ~~`/devices`（设备管理）~~ | **已实现**（见第 10 节） | 列表、改名、踢下线 |
| `GET /books/{id}/download?track_ids=` | 未实现 | 用 `/chapters/{idx}/audio?download=1` 按集下载 |
| ~~`stream?transcode=`~~ | **已实现**（见第 5 节） | 整轨转 opus/mp3 + 落盘缓存 |

如果客户端需要其中某一项，先提需求再实现，不要按旧文档编码。

## 14. 契约变更流程

1. 改代码同时更新本文件（含示例）；
2. 破坏性变更必须提升 `APP_VERSION` 并在 CHANGELOG 标注；
3. 新增字段默认可选、只增不改；
4. 新增端点同步补进第 0.6 节总览表。
