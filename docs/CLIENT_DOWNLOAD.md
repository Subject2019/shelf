# 客户端下载约定（按章节离线缓存）

> 面向安卓 / 第三方客户端。服务端接口见 [`API.md`](./API.md) 第 10 节。
> **WebUI 不使用这套接口**：网页播放走整文件 Range 直出，见 `services/streamer.py`。

## 1. 能力概述

服务端可以按「第 N 集」切出独立音频文件并缓存，客户端拿到的就是一个完整可播放的 m4a
（mp3/flac 源会保持原容器）。切片在**首次请求时同步生成**，之后命中缓存。

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/v1/books/{id}/chapters?page=&page_size=` | 取章节目录（`idx`、`title`、`start_sec`、`track_id`） |
| GET | `/api/v1/books/{id}/chapters/cache` | 查询服务端已切好的集 |
| POST | `/api/v1/books/{id}/chapters/{idx}/cache` | 预生成（幂等，返回体积/时长） |
| GET | `/api/v1/books/{id}/chapters/{idx}/audio?download=1` | 下载/续传该集 |
| DELETE | `/api/v1/books/{id}/chapters/cache` | 清空该书服务端缓存 |

`idx` 从 **0** 开始，与章节目录里的 `idx` 一致；界面上的「第 35 集」对应 `idx=34`。

## 2. 鉴权

```
POST /api/v1/auth/login          {"username","password"}
  → { access_token, refresh_token, expires_in, user }
POST /api/v1/auth/refresh        {"refresh_token"}
  → 新的 access_token + refresh_token（旧的立即失效，务必替换）
```

- 下载接口支持两种鉴权：
  - `Authorization: Bearer <access_token>`：适合浏览器/短任务；
  - `X-Download-Token: <download-ticket>`：适合 Android 原生后台下载。
- `access_token` 有效期只有 **30 分钟**，后台批量下载很容易在队列中途过期。
  因此原生客户端应先调 `POST /books/{id}/download-ticket` 换一张 **12 小时**、
  只允许访问单本书章节音频的票据，再开始队列。
- 票据不能访问其他书籍或普通 API；过期后重新签发，不要把 refresh token 落盘到原生层。
- 401 处理：access token 刷新一次后重放；下载票据则重新申请票据。不要循环重试。

## 3. 标准流程

```
1. GET  /books/{id}/download-manifest
   → 书名、总时长、全部章节、服务端已缓存章节
2. POST /books/{id}/download-ticket
   → 单本书 12 小时下载票据
   客户端可以先让用户从 manifest.chapters 里选择要下载的章节；
   未选择的章节不写入本地下载索引。
3. 对每一集（串行，最多 1–2 并发）：
   a. GET /books/{id}/chapters/{idx}/audio?download=1
      Header: X-Download-Token: <ticket>
      - 首次：200/206，边收边写本地 .part
      - 续传：Range: bytes=<已下载字节>-
   b. 校验本地文件大小 == Content-Range 总长
   c. 原子 rename 为正式文件，写入本地索引
4. PUT /progress/{id}                    ← 播放时按第 8 节换算
```

伪代码：

```text
manifest = GET /books/{id}/download-manifest
ticket = POST /books/{id}/download-ticket
for chapter in manifest.chapters:
    local = store.find(book_id, chapter.idx)
    if local and local.cache_key == server_key(chapter):
        continue
    offset = local?.downloaded_bytes or 0
    resp = GET audio with Range(offset) and X-Download-Token(ticket)
    append_stream_to_file(resp.body, local.part)
    assert file_size == total_from(resp)
    rename(local.part, local.final)
```

## 4. 下载响应与续传细节

**请求**

```http
GET /api/v1/books/1/chapters/34/audio?download=1 HTTP/1.1
Authorization: Bearer <access_token>
Range: bytes=10485760-
```

**响应**

```http
HTTP/1.1 206 Partial Content
Content-Type: audio/mp4
Content-Range: bytes 10485760-11311294/11311295
Content-Length: 825535
Content-Disposition: attachment; filename="chapter-0035.m4a";
                     filename*=UTF-8''间客_第一卷...-0035-035 逃难的小西瓜.m4a
X-Chapter-Cache: hit
Accept-Ranges: bytes
```

约定：

- `200` 表示服务端返回整文件（没带 Range 或 Range 被忽略）；`206` 才是续传命中。
- 续传前校验 `Content-Range` 的起始字节 == 你请求的 offset，否则**丢弃本地片段从头再来**。
- 文件总长取 `Content-Range` 的 `/total`，没有则取 `Content-Length`。
- **首字节延迟**：未缓存时服务端要先切片（实测 10 分钟集 0.24–0.42s，源文件 600MB 也只切该段）。
  读超时建议 **≥ 60s**，不要用 5s 级超时误判为网络失败。
- 服务端不提供 checksum / ETag 校验，**用字节数判断完整性**即可。
- 文件名优先使用 `filename*=UTF-8''...`（RFC 5987）里的中文名，`filename=` 只是 ASCII 兜底。

**缓存版本**

`cache_key` 形如 `0034-1791869584-635694933.m4a`（集号-源文件 mtime-源文件 size）。
源文件被替换后 key 会变化 → 客户端应视为新版本，重新下载。
本地索引里保存这个 key，**它就是你的版本号**，不要用「文件存在」判断已是最新。

## 5. 并发与节流

| 场景 | 建议 |
|---|---|
| NAS / 机械盘 | 同时 **1** 个下载 |
| SSD / x86 小主机 | 最多 **2** 个 |
| 同一集重复请求 | 服务端已按集加锁，会串行等待，不要用它来做重试 |
| 一次勾选整本 60 集 | 队列串行 + 失败退避，不要并发打满 |

服务端没有限流；并发过高只会在 `ffmpeg` 与磁盘上互相拖慢。

## 6. 错误码与重试

错误体统一为 `{"error": {"code": "...", "message": "...", "details": null}}`。

| HTTP | code | 是否重试 | 处理 |
|---|---|---|---|
| 401 | `unauthorized` | 刷新后重试 1 次 | token 过期 |
| 403 | `forbidden` | 否 | 该书库未授权给当前用户 |
| 404 | `chapter_not_found` | 否 | `idx` 不存在，重拉章节目录 |
| 404 | `media_missing` | 否 | 源文件被删/移走，提示重新扫描 |
| 409 | `chapter_empty` | 否 | 该集时长为 0，跳过 |
| 416 | — | 否 | 本地片段越界，删掉本地文件从 0 重新下 |
| 502 | `slice_failed` | 重试 1 次 | ffmpeg 切片失败，多为源文件异常 |
| 503 | `chapter_cache_disabled` | 否 | 服务端关了按章节缓存，提示管理员 |
| 503 | `ffmpeg_missing` | 否 | 服务端镜像没装 ffmpeg（正常镜像应自带） |
| 503 | `transcode_disabled` | 否 | wma/ape 等格式需转码，但服务端关了转码 |

退避建议：`1s → 3s → 跳过该集`，并把失败集留在队列里供用户手动重试。

## 7. 本地存储建议

```
<app>/audiobooks/{book_id}/{idx:04d}-{cache_key 里的 mtime}-{size}.m4a
```

索引表至少存这些字段，便于离线启动时秒开书架：

| 字段 | 说明 |
|---|---|
| `book_id` / `index` | 主键 |
| `title` | 章节名（离线也要显示） |
| `cache_key` | 服务端版本号，用于判断是否需要重下 |
| `bytes` | 服务端给出的总字节数 |
| `downloaded_bytes` | 断点续传用 |
| `status` | `pending` / `downloading` / `done` / `failed` |
| `start_sec` | 全书绝对起点，进度换算要用（第 8 节） |

体积估算：`字节 ≈ 码率(kbps) × 1000 ÷ 8 × 时长(秒)`。
实测 128kbps 有声书约 **16 KB/s ≈ 9.6 MB/10 分钟**，一本 10 小时约 **570 MB**。
下载前用 `/books/{id}` 的 `total_duration_sec` 给用户预估空间。

## 8. 与播放、进度上报的衔接

- 切片文件是**单集独立音频**，播放器里的 `currentTime` 从 0 开始，**不是全书绝对秒**。
- 服务端进度 `position_sec` 是**全书绝对秒**，因此离线播放上报时要换算：

```text
PUT /api/v1/progress/{book_id}
{
  "track_id": <该集 track_id>,
  "position_sec": chapter.start_sec + player.currentTime,
  "playback_rate": 1.0,
  "client_updated_at": <unix 秒>,
  "explicit_seek": <用户是否拖动/跳章>,
  "finished": <本集播放完毕>
}
```

- 从全书进度恢复到某一集时：`localSeek = progress.position_sec - chapter.start_sec`，
  落在哪个 `[start_sec, 下一集 start_sec)` 区间就播哪一集。
- 在线（未下载）播放仍走整文件流：`POST /books/{id}/play-token` + `GET .../tracks/{track_id}/stream?token=`，
  两者进度语义一致，可以混用。

## 9. 服务端缓存的边界（重要）

- 服务端缓存目录 `${DATA}/cache/chapters/{book_id}/` 只是**避免重复切片**的加速层。
- 默认上限 **2 GiB**（`ECHOSHELF_CHAPTER_CACHE_MAX_BYTES`），超出会按最旧优先删除；
  管理员也可能随时 `DELETE /books/{id}/chapters/cache`。
- 因此：**不要把服务端的「已缓存」当作离线库**，客户端必须自己落盘。
- 下载完成后如果 NAS 空间紧张，可以主动 `DELETE` 该书的服务端缓存，不影响已下载的本地文件。

## 10. 已知限制（后续可能变化）

| 限制 | 现状 | 后续 |
|---|---|---|
| 无批量打包 | 一集一个请求 | 可加 `GET /books/{id}/bundle` 打包 zip（未排期） |
| 无校验和 | 只比对字节数 | 可加 `X-Chapter-Checksum`（sha256） |
| 同步切片 | 首字节延迟 0.2–0.4s | 可改成后台预生成任务 |
| 单集粒度 | 章节即集 | 长章节可支持按秒切段 |
| 离线 UI | 已内置 `web/dist`，断网时启动 127.0.0.1 本机 API；书库、详情、搜索、设置、播放页复用在线版式，进度/书签保存在本机 | 封面、简介和在线书单仍需联网 |
| 部分下载 | 下载至少一章即可在离线书架显示；未下载章节灰色不可播放 | 需要客户端保存完整章节目录（Android 已保存） |

客户端接入前建议先请求 `GET /api/v1/health` 读 `version`，低于 `0.1.0` 的实例没有本章节接口。
