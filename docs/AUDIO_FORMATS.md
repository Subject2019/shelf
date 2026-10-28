# 音频格式与元数据支持

## 1. 支持矩阵

`直出` = 原文件按 Range 直接流式传输（零 CPU）；`转码` = 服务端 ffmpeg 实时转 opus/mp3。

| 容器 | 常见编码 | Web 浏览器 | Android (Media3) | 服务端策略 | 章节来源 |
|---|---|---|---|---|---|
| `.mp3` | MPEG-1/2 Layer III | ✅ 全支持 | ✅ | **直出** | ID3v2 CHAP / CUE / 文件切分 |
| `.m4a` | AAC-LC / ALAC | ✅（ALAC 需 Chrome/Firefox） | ✅ | **直出** | chpl / 文件切分 |
| `.m4b` | AAC-LC / ALAC | ✅ | ✅ | **直出** | **chpl（Nero 章节）** / CUE |
| `.aac` | ADTS AAC | ✅ | ✅ | **直出** | 无 → 虚拟章节 |
| `.flac` | FLAC | ✅ Chrome/FF/Edge；Safari 14+ | ✅ | **直出** | Vorbis comment / CUE |
| `.ogg` | Vorbis | ✅ Chrome/FF；Safari ❌ | ✅ | **直出**（Safari 判定不支持时转码） | Vorbis comment |
| `.opus` | Opus（ogg/webm） | ✅ Chrome/FF；Safari 18 部分 | ✅ | **直出** | Vorbis comment |
| `.wav` | PCM | ✅ | ✅ | **直出**（体积大，建议用户自行压缩） | CUE / 虚拟章节 |
| `.wma` | WMA v2 | ❌ | ❌ | **转码为 mp3 64k** | ASF 标签（无章节） |
| `.ape` | Monkey's Audio | ❌ | ❌ | **转码为 mp3 64k** | CUE |
| `.dsf/.dff` | DSD | ❌ | ❌ | **转码为 mp3 64k** | CUE |
| `.aiff` | PCM | ✅ Safari/Chrome | ✅ | **直出** | 无 |

补充规则：
- 格式判定以**文件头魔数**为准，扩展名仅作提示（防止 `.mp3` 实为 m4a 的错误命名）。
- 不支持的容器在「扫描」阶段标记 `needs_transcode=1`，前端显示「转码播放」徽标。
- 转码会带来 CPU 开销，NAS 上默认单路并发，且 `?transcode=1` 才启用。

## 2. 元数据字段映射

内部统一字段：`title / author / narrator / publisher / year / language / description / series / series_index / cover`。

| 内部字段 | ID3v2 (mp3) | MP4 (m4a/m4b) | Vorbis (flac/ogg/opus) | ASF (wma) |
|---|---|---|---|---|
| title | `TIT2` | `©nam` | `TITLE` | `Title` |
| author | `TPE1` | `©ART` | `ARTIST` | `Author` |
| album_artist | `TPE2` | `aART` | `ALBUMARTIST` | — |
| narrator | `TXXX:NARRATOR` | `©nrt` / `----:com.apple.iTunes:NARRATOR` | `NARRATOR` | — |
| series | `TXXX:SERIES` | `----:com.apple.iTunes:SERIES` | `SERIES` | — |
| series_index | `TXXX:SERIES-PART` | `----...:SERIES-PART` | `SERIES-PART` | — |
| publisher | `TPUB` | `©pub` | `PUBLISHER` | — |
| year | `TDRC` | `©day` | `DATE` | `WM/Year` |
| language | `TLAN` | `©lan` / `----...:LANGUAGE` | `LANGUAGE` | `WM/Language` |
| description | `COMM` | `desc` / `©cmt` | `DESCRIPTION` | `Description` |
| cover | `APIC` | `covr`（atom 数组） | `METADATA_BLOCK_PICTURE`（base64） | `WM/Picture` |

实现：优先 `mutagen`（纯 Python、快、无外部进程），字段缺失时回退 `ffprobe -show_format`。

**字段回退链**（决定 book 展示信息）：

```
title        : 标签 title → 首轨文件名（去序号） → 目录名
author       : 标签 author → album_artist → "未知作者"
narrator     : 标签 narrator → null
series       : 标签 SERIES → 书名/文件名匹配「第N卷·部·册·集·季」（含中文数字）→ null
series_index : 标签 SERIES-PART → 上面匹配到的卷号（十/十二/二十一 等会被换算）
```

## 3. 章节解析

### 3.1 优先级

```
1. 内嵌章节（m4b chpl / ID3 CHAP / ffmpeg chapters）  → source=embedded
2. 同目录 .cue 文件                                    → source=cue
3. 一本书 = 多个音频文件（每文件一章）                  → source=track_split
4. 兜底：按 15 分钟切虚拟章节（可配置）                 → source=virtual
5. 用户手工编辑                                        → source=manual（最高优先，扫描不覆盖）
```

### 3.2 m4b 的 chpl

`chpl` 是 `moov/udta/chpl` atom（Nero 章节格式）。mutagen 不直接暴露，方案：

1. 首选 `ffprobe -v quiet -print_format json -show_chapters`（ffmpeg ≥ 4.4 会解析 chpl 与 ID3 章节），解析 `chapters[].start_time/end_time/tags.title`；
2. ffprobe 不可用时，用轻量 atom walker 手工读 `moov/udta/chpl`（约 60 行）。

> 决策：**把 ffprobe 作为章节解析的唯一入口**，mutagen 只负责标签与封面。理由是章节逻辑统一在 ffmpeg 里维护、覆盖格式最广；代价是扫描时对含章节的文件多一次进程调用（每文件约 50–150 ms，可接受，且可缓存）。

### 3.3 CUE 分轨

解析 `.cue` 文本（GBK/UTF-8 自动探测）：

```
FILE "整轨.flac" WAVE
  TRACK 01 AUDIO
    TITLE "第一章"
    INDEX 01 00:00:00
  TRACK 02 AUDIO
    TITLE "第二章"
    INDEX 01 12:34:56
```

规则：
- 每个 `TRACK` → 1 条 `tracks` 记录，`start_offset_sec` = 累计 `MM:SS:FF`（75 帧/秒）；
- 一本书 = 一个 cue（同 cue 的多个 FILE 合并为一本书）；
- 时长 = 下一轨 offset − 本轨 offset；末轨 = 文件总时长 − 起点；
- 整个 cue 只产生 **1 条 media_file**（物理文件），避免大文件重复解析。
- 编码探测：先 UTF-8，失败用 GB18030 重试（中文 CUE 常见）。

### 3.4 ID3 CHAP/CTOC

`mutagen.id3.CHAP` 帧含 `start_time/end_time/sub_frames`。注意：ID3 章节时间单位是毫秒，需转秒。

## 4. 「一本书」的识别规则

扫描器按下述顺序判定（避免把 100 个散装 mp3 变成 100 本书，同时避免把多卷 m4b 并成一本）：

| 场景 | 判定 |
|---|---|
| 文件扩展名是 `.m4b` | **每个 m4b = 一本书**，即使同一目录放了多卷也不合并 |
| 文件是 `.m4a` / `.mp4` 且带内嵌章节 | 每个文件 = 一本书 |
| 目录内有 `.cue` | 每个 cue = 一本书 |
| 目录内只有 1 个音频文件（mp3/flac…） | 该文件 = 一本书 |
| 其余多个音频文件（mp3/flac/ogg/无章节的 m4a…） | 整目录 = 一本书，每文件一章 |
| 无法归组 | 每个文件 = 一本书（保守，保证能播） |

实现见 `services/scanner.py` 的 `_group_media()`：先按上表把目录拆成若干组，再逐组建书。

**书籍身份**：`_find_existing_book()` 先按「这些媒体文件当前属于哪本书」匹配（`tracks.media_file_id`），
匹配不到才用 `(rel_dir, title)`，并跳过本次扫描已被认领的书 —— 因此同一目录可以稳定容纳多本书。
重扫时若书变短（拆卷、换文件），超出新时长的历史进度会被归零，避免进度条越界。

> 尚未实现：按专辑标签（`album`）把一个目录拆成多本（用于「一个目录塞了多张无关专辑」的散装库）。
> 目前这类场景建议按书分目录整理。

音频扩展名白名单：`mp3 mp3pro m4a m4b aac flac ogg oga opus wav wma ape dsf dff aiff aif mka webm`。
忽略：隐藏文件、`.part`、`@eaDir`、`#recycle`、`.DS_Store`、`Thumbs.db`、`*.tmp`、小于 100 KB 的音频（多为残留/广告）。

推荐用户命名（写入 `DEPLOY_NAS.md` 的规范建议，非强制）：

```
/audiobooks/
└── 刘慈欣/三体/            ← 作者/书名/，扫描器自动取作者
    ├── 三体.m4b            ← 单文件 + 内嵌章节（最省事）
    └── cover.jpg           ← 无内嵌封面时的备用封面
```

## 5. 封面提取

优先级：内嵌图片（APIC/covr/METADATA_BLOCK_PICTURE） > 目录内 `cover.jpg|folder.jpg|front.jpg`（大小写不敏感） > 书籍占位图。

处理：
- 抽出原始字节 → Pillow 转 JPEG（质量 82）→ 生成 400px 宽缩略图；
- 写 `/data/cache/covers/{book_id}.jpg` 与 `{book_id}_thumb.jpg`；
- 缓存键含 `book.updated_at`，元数据变了自动失效；
- 严禁写回媒体目录（只读挂载）。

## 6. 边界情况清单（实现时逐条测试）

| # | 情况 | 期望行为 |
|---|---|---|
| 1 | `.cue` 内 `FILE` 指向不存在的文件 | 跳过该 cue，日志 warn，不中断整次扫描 |
| 2 | 同一物理文件被两个 cue 引用 | `tracks` 各归属其 book，`media_files` 只 1 条 |
| 3 | GBK 编码 cue | 正确解码不出现乱码 |
| 4 | mp3 无任何标签 | 用文件名/目录名兜底，不报错 |
| 5 | 总时长 > 24h（合辑） | `REAL` 存秒，前端格式化为 `24:00:00` |
| 6 | 单文件 > 2 GB | Range 正常，偏移用 int64 |
| 7 | 存储介质 mtime 精度为秒 | 判重（mtime+size）足够，不依赖 ns |
| 8 | 文件名含 emoji/全角符号 | 数据库统一 UTF-8，路径不 URL 编码存库 |
| 9 | 文件在扫描中途被删除 | try/except 单文件，标记 missing |
| 10 | 目录符号链接循环 | 记录 visited inode，深度上限 12 |
| 11 | 章节时间重叠/越界 | 裁剪到 `[0, duration]`，丢弃零长章节 |
| 12 | 无 ffmpeg 的极简环境 | 启动自检告警，章节退化为虚拟章节，转码接口 501 |
