# web — 网页播放端

**状态：M2 + M6 前端功能完整**。登录、书架（网格/列表/系列文件夹/作者）、搜索、书籍详情、全局播放器（章节/书签/进度回溯/睡眠定时与淡出/跳片头片尾/跨设备接续/误拖撤销）、作者页、设置（外观/账号/设备/用户/书库）、首页收听统计。React 18 + TypeScript + Vite + TailwindCSS + Zustand + TanStack Query。

## 目录职责

```
web/
├── index.html
├── package.json
├── vite.config.ts          # dev 代理 /api -> http://localhost:8080
├── tailwind.config.ts
├── src/
│   ├── main.tsx            # 挂载 + QueryClientProvider + Router
│   ├── App.tsx             # 路由表 + AppShell
│   ├── api/
│   │   ├── client.ts       # fetch 封装：baseURL、Bearer、401 自动 refresh 重试
│   │   ├── types.ts        # 与 docs/API.md 对齐的 DTO
│   │   └── endpoints.ts    # books/libraries/progress/auth 函数
│   ├── store/
│   │   ├── auth.ts         # access 只在内存，refresh 存 localStorage（后端用 body 换发，未下发 cookie）
│   │   ├── player.ts       # 当前书/轨/时间/速率/队列/睡眠定时
│   │   └── ui.ts           # 抽屉、主题
│   ├── components/
│   │   ├── player/         # PlayerBar、ChapterDrawer、SpeedMenu、SleepTimer
│   │   ├── shelf/          # BookCard、BookGrid、FilterBar、SkeletonCard
│   │   └── layout/         # AppShell、Sidebar、TopBar
│   ├── pages/              # Login、Home、Library、BookDetail、Authors、Search、Settings、PlayerPage
│   ├── lib/                # format.ts（时长/日期）、hotkeys.ts、mediaSession.ts
│   └── styles/
│       ├── index.css       # Tailwind 入口 + 默认 brand 色阶变量
│       └── accent.ts       # 主题色 → brand 50–900 色阶推导
└── public/
```

## 播放器实现要点

- **全局单例 `<audio>`**，挂在 `PlayerBar` 里，路由切换不卸载（否则会断音）。`store/player.ts` 持有状态与命令，`bindAudioElement` 把原生事件接回 store。
- **播放鉴权**：`<audio>` 带不了 `Authorization`，先 `POST /books/{id}/play-token` 换绑定本书的 6 小时令牌，再拼 `?token=` 到 `stream_url`。
- 切轨 = 改 `src` + `loadedmetadata` 后设 `currentTime`；同轨跳转直接设 `currentTime`。
- `MediaSession API`：`metadata`（书名/章名/作者）+ `play`/`pause`/`seekbackward`/`seekforward`/`previoustrack`/`nexttrack` + `setPositionState`。
- 进度上报：15s 定时 + `pause`/`ended`/`close`/`beforeunload`（`fetch keepalive`，sendBeacon 无法带头）+ UI 跳转后 500ms 防抖。跳转上报 `explicit_seek=true`。
- 变速：`audio.playbackRate`（0.75–3.0），本地记忆并随进度上报。
- 快捷键：`Space` 播放/暂停、`←/→` ±15s、`↑/↓` 音量 ±5%、`J/L` ±30s、`[`/`]` 切轨、`M` 静音；输入框内不拦截。

## 本地启动

需要 Node ≥ 18（已验证 20.18）。

```bash
npm install
npm run dev     # http://localhost:5173，/api 代理到 8080
npm run build   # 先 tsc --noEmit 再 vite build，产物 dist/
```

当前已实现：`api/client.ts`（Bearer + 401 单飞刷新 + 会话失效回调）、`store/auth.ts`、`store/ui.ts`（深浅模式 + 主题色）、
`components/layout/AppShell.tsx`（桌面侧栏 + 移动底栏）、`components/auth/RequireAuth.tsx`（路由守卫）、
`pages/Home.tsx`（服务状态 + 最近添加）、`pages/Login.tsx`（登录 / 初始化管理员）、`pages/Settings.tsx`（外观 / 账号 / 设备 / 用户 / 书库）、`pages/Authors.tsx`（作者聚合）、
`pages/Library.tsx`（书架 + 搜索/筛选/排序/无限滚动）、`components/player/PlayerBar.tsx`（全局播放条）、
`store/player.ts`（播放状态机 + 进度上报）、`lib/{hotkeys,mediaSession}.ts`。

## 书架页

- `useInfiniteQuery` 每页 40 本，底部哨兵用 `IntersectionObserver`（`rootMargin: 400px`）自动续页，另留「加载更多」兜底
- 搜索输入 300ms 防抖；筛选（全部/在听/已听完/未开始）与排序（最近添加/书名/作者/时长/最近收听）直接映射后端参数
- 网格与列表两种视图共享同一份分页数据，切换不重新请求
- 无封面时按书名哈希生成稳定渐变色块 + 首字（`lib/format.ts` 的 `coverGradient`），同一本书颜色始终一致
- 卡片/行点击进入 `/books/:id`，详情页在 M2-T06 实现，当前为占位

## 章节与跳转

m4b/m4a 的内嵌章节在**扫描阶段**就由 ffprobe 解析写入 `chapters` 表（`idx` / `start_sec` / `end_sec` / `title`），
播放器直接消费 `GET /books/{id}` 的 `chapters`，不额外解析音频：

- 播放条显示当前章名（点它或 `list` 按钮打开章节抽屉）
- 抽屉列出全部章节（序号、标题、起点 · 时长），当前章高亮并自动滚动到可视区
- 点击章节 = `seekTo(chapter.start_sec)`，按 UI 跳转上报 `explicit_seek=true`
- 「上一章 / 下一章」按钮、`[` `]` 快捷键、锁屏的上一首/下一首都**按章推进**；本章已播 5 秒时「上一章」先回章首
- 详情接口对 >500 章的书会省略 `chapters`，播放器会再用 `/books/{id}/chapters?page_size=500` 兜底
- 没有内嵌章节的书（多文件无 cue 等）自动退化为按轨显示

## 播放页工具条 / 睡眠定时

播放页主控制区下方是一条四格工具条 `components/player/PlayerTools.tsx`（`PlayerStage` 渲染，
全屏播放页 `FullPlayer` 共用）：

| 格子 | 行为 |
|---|---|
| 定时 | 打开睡眠定时面板；启用后格子直接显示 `18:20` / `2 集` / `本集后停` |
| 倍速 | 弹出 0.75×–3× 八档；非 1× 时常亮 |
| 音量 | 弹窗内滑块 + 静音，格子显示当前百分比（静音显示 0%） |
| 书签 | 在当前进度加书签，成功后变「已添加」1.5 秒并刷新右侧书签列表 |

播放条（其他 tab）上仍保留纯图标月亮按钮，两处状态同源。
`SleepTimer` 用 `variant: "icon" | "pill" | "tool"` 适配三种样式。

### 淡出

- 按时长计时时，**最后 30 秒**音量线性降到 0（每秒按 `剩余/30` 重算 `audio.volume`）
- 只影响 `audio.volume`，不改用户设置的 `volume` 状态；`clearSleep()` / 开始新定时 /
  切换书籍时都会把音量恢复成用户设置值，不会出现「下次打开没声音」
- 「播完本集再停」模式下不淡出（已经由章节边界决定停止时刻）

### 跳过片头/片尾

书籍详情页「编辑资料」可以设置 `intro_sec` / `outro_sec`（秒，0 表示不跳）：

- **片头**：只在「接着上次进度/开始播放」且起点小于片头时，从 `intro_sec` 开始；
  书签、进度检查点这类显式位置不干预
- **片尾**：播放到 `total_duration_sec - outro_sec` 时自动翻到下一章（无下一章则下一轨，
  最后一章直接暂停），避免把片尾音乐/致谢听进去
- 逻辑在 `store/player.ts` 的 `open()` 与 `timeupdate` 监听里，`PlayerBar` / `PlayerStage` /
  全屏播放器共用同一份 store，因此三处行为一致

状态在 `store/player.ts` 的 `sleep*` 字段：

- **按时长**：15 / 30 / 45 / 60 / 90 分钟或自定义；可选「到点后播完本集再停」（等当前章 `end_sec` 到了才暂停）
- **按集数**：1 / 2 / 3 / 5 集或自定义；跨到下一章时计数，无章节信息的书按音轨计
- 只有**播放中**才倒计时（暂停时定时也暂停），避免「放着没听也在烧时间」
- 换书或关闭播放器自动清除定时；到点后 `clearSleep()` + `audio.pause()`，暂停事件会顺带上报进度
- 当前状态显示在面板顶部（`剩余 3:20` / `还剩 2 集` / `本集播完就停`）

## 跨设备进度（一个账号一条）

`progress` 表主键是 `(user_id, book_id)`，服务端永远只有一行，所有设备读写同一行。客户端要配合：

- **开播即写**：`<audio>` 的 `play` 事件立刻 `PUT /progress`，谁按下播放谁就「持有」进度
- **回到前台对齐**：`AppShell` 在 `visibilitychange` / `focus` / `pageshow` 以及每 60 秒调
  `syncFromServer()`（8 秒节流），逻辑在 `store/player.ts`
  - 取 `GET /progress/recent` 里**最近 2 分钟内、`device_id` 不是自己**的那一条
  - 同一本书且本机暂停 → 直接 `seekTo`，并弹 5 秒提示「已同步其他设备的进度」
  - 另一本书 → 右下角弹出「另一台设备正在听《…》」，点「接续这台」才切书（避免打断当前播放）
  - 「留在这台」会按 `book_id:updated_at` 记住，不再重复弹同一条
- **播放中不跟随**：正在播的设备不会被远端位置拽走，避免两台设备互相拉扯
- 打开书本时起点始终来自 `GET /books/{id}` 的 `progress`，不使用本地缓存

## 进度回溯点（面板「进度」页签）

播放器侧栏第三个页签，数据来自 `GET /progress/{book_id}/history`：

- 每本书最多 3 条，服务端决定何时新增（位置差异 ≥ `max(5 分钟, 总时长 3%)`，封顶 30 分钟）
- 差异不够大时刷新最近的一条（含「撤销误拖」回到原位的情况），不会刷出一堆无意义快照
- 点一条即 `seekTo`（带 `explicit_seek`），可以往回跳
- 条目标题按章节 `start_sec` 反查，时间用 `formatRelative`，最新一条标「当前」

拖动进度条（播放条或播放页）造成 ≥5 分钟的跳跃时，底部会弹「已跳到 X · 回到 Y」，
10 秒内点一下就能撤回，逻辑在 `store/player.ts::seekWithUndo` / `undoJump`。

## 书签

面板第二个 tab，数据走 `/books/{id}/bookmarks`（TanStack Query，key `["bookmarks", bookId]`）：

- 播放条上的书签按钮 = 在当前进度添加，备注默认取当前章节名，按钮短暂变勾反馈
- 面板内「在 x:xx 添加书签」按钮，移动端也能加
- 书签项显示时间、备注、所属章节；点击精确跳转
- 备注支持行内编辑（Enter 保存 / Esc 取消），删除即时生效

## 封面

`<img>` 无法携带 `Authorization`，所以封面不走 `src={cover_url}`：

```
lib/cover.ts          useCoverUrl()：fetch → blob → objectURL，按 (bookId, size) 内存缓存 + 失效通知
components/ui/Cover.tsx   统一入口：有图 <img>，无图用书名渐变 + 首字，尺寸完全一致
```

- 书籍对象 `cover_url` 为 `null` 表示没有封面，`Cover` 不发请求、直接渲染渐变兜底
- 上传/删除封面后调用 `invalidateCover(bookId)`（T10 详情页会用），所有在屏封面自动重取
- 列表/播放条用 `size="thumb"`（400 宽），详情与大封面用 `size="full"`

## 收听统计卡片（首页）

`components/stats/ListeningCard.tsx`，数据 `GET /stats`（key `["stats"]`，30 秒 stale）：

- 三格指标：今日收听 / 连续天数 / 累计收听，都用 `formatDuration`
- 最近 7 天柱状图：`title` 属性带「日期 · 时长」，柱子高度按当日峰值归一，
  没听的日子给一条 4px 的浅色底线，避免看起来像缺数据
- 只有登录用户渲染；接口出错时只显示一行「统计加载失败」，不阻塞首页
- 计入口径在服务端（拖动进度条不计、倍速折算），前端不需要额外埋点

## 书架网格与窄屏

- 主网格 `repeat(auto-fill, minmax(150px,1fr))`；卡片 `h-full flex flex-col` + 网格不设 `items-start`，
  同一行的卡片高度一致（书名折成 2 行也不会参差）
- 书名用 `line-clamp-2 text-balance`：最多两行，且尽量均分，避免「最后一个字单独一行」
- 系列展开面板的 `grid-column: span N` 里的 N 由 `Library` 实测的**实际列数**钳制
  （`getComputedStyle(grid).gridTemplateColumns` 过滤 0px 隐式轨道）。原先写死 `min(卷数, 6)`，
  手机只有 2 列时会生成隐式轨道，把面板顶出屏幕右侧（360px 视口下横向溢出 16px）

## 作者页 `/authors`

`GET /authors` 聚合的独立页面，卡片显示封面、N 本、总时长：

- 点卡片跳 `/library?author=<名字>`，书库页按作者筛选并显示横幅（可一键返回作者列表）
- 书库页右上角有「作者」入口；`?author=` 与 `?series=` 互斥，按作者筛选时不再折叠系列
- 作者没有卷号语义，因此不复用系列那种「折叠文件夹」交互

## 系列（虚拟文件夹）

有声书常按卷出版，`series_name` + `series_index` 就是天然的归组键：

- 扫描时标签 `SERIES` / `SERIES-PART` 优先；没有标签就从书名（或文件名）匹配
  「第N卷/部/册/集/季」，支持中文数字（`十`、`二十一`、`一百零三`）；书名里没有系列名时退回目录名
- 书架里同一系列**折叠成一张文件夹卡片**（背后两层纸、右上角「N 卷」）；
  展开状态存 `localStorage.echoshelf.open_series`
- 展开后不再是「文件夹卡 + 散落的卷卡」，而是**一整块带边框的面板**（`SeriesShelf`）：
  面板头是系列封面 + 名称 + 「N 卷 · 总时长」+ 收起按钮，下面按卷号排列各卷；
  面板宽度按卷数自适应（`gridColumn: span N`，最多 6 格），后面的单本卡片被推到面板之外，
  边界一眼可见，不会和系列里的卷混在一起
- 纸张是**向右错开叠放**的（背面 12px、中间 6px），只在折叠态出现；不能向上堆叠，
  否则会压住上方的「全部 / 在听……」筛选标签
- 立体感来自：每层纸张各自的**右侧投影**（`shadow-[9px_4px_16px_-8px_...]`）、上下各缩进
  （`inset-y-3.5 / inset-y-2`）、悬停时**整叠往右抽出**（背面 18px、中间 9px）
- 网格间距 20px 给右侧纸张留位：卡片宽 ~173px，纸边最多伸到 +18px，不会贴到相邻卡
- 浅色下纸是白底叠白底，靠 `border-zinc-300/400` 与落在背景上的投影保证边界可见，深色用 `white/22 ~ /58` 渐变
- 展开/收起是完整动画：展开时面板整体淡入、各卷逐张从左侧滑入
  （`.folder-card-in`：`translateX(-34px) scale(.94)` → 原位，`animation-delay` 每张 +65ms），
  收起时先播 `.folder-card-out`（0.18s 反向），300ms 后才真正从 DOM 移除并换回文件夹卡
- 单卷系列不折叠（`/series` 的 `book_count < 2` 直接平铺）；搜索或已按系列筛选时也平铺，
  避免「筛出来的书又被塞回文件夹」
- 文件夹卡片右下角箭头 → `/library?series=间客`：URL 可分享、刷新保持、改按 `sort=series_asc` 排卷号，
  顶部有「系列：间客 · 查看全部书」横幅
- 列表视图同样折叠成一行，展开后缩进显示各卷
- 详情页的系列标签可直接点回该系列列表

筛选参数走服务端 `GET /books?series=`，不额外拉全量数据；
系列汇总来自 `GET /series`（`queryKey: ["series"]`，60s staleTime）。

## 书籍详情页与资料编辑

`pages/BookDetail.tsx`（`/books/:id`）：

- 大封面（`Cover size="full"`）+ 总时长 / 音轨 / 章节 / 大小四项
- 简介、系列 / 出版 / 语言 / 章节来源标签；无简介时提示可在「编辑资料」补
- 「继续收听 · 12:34」按钮（带进度条）、正在播放时可跳 `/player`
- 章节网格：默认 8 章，可展开全部，点击直接从该章开播
- 管理员另有封面编辑（上传 / 删除，见「封面」）与「编辑资料」

`components/book/MetadataEditor.tsx`（仅 admin）：

- 表单覆盖 10 个字段：书名（必填）、副标题、作者、演播者、出版社、出版年份、语言、系列、第几部、简介
- 保存走 `PATCH /books/{id}`，成功后本地回写查询缓存并刷新书架列表
- 保存即置 `manual_override`，详情页显示「元数据已手工修改」徽标 + 「恢复自动识别」
  （`POST /books/{id}/metadata/reset`，只清标记不还原值，下次扫描才会覆盖）

## 播放页 `/player`

底部 tab 与侧栏都有入口，是一个**常规页面**而不是覆盖层：

- 桌面双栏：左侧大封面 + 信息 + 进度 + 主控（`PlayerStage`），右侧常驻章节/书签面板（`PlayerLibraryPanel`，`lg:sticky`）
- 移动端单列：上方播放主体，下方固定高度章节面板
- 播放条在本页隐藏（`.hidden` 而非卸载，`<audio>` 必须留在 DOM 里否则断音）
- 播放状态只在内存，刷新后为空态；此时读 `localStorage` 的 `echoshelf.last_book`，给出「继续收听《书名》」按钮，点击才 `open()` 并从服务端进度恢复

组件复用关系：

```
PlayerStage          封面/信息/进度/五键主控  →  FullPlayer、PlayerPage
PlayerLibraryPanel   章节 + 书签 tab          →  PlayerPanel（抽屉）、PlayerPage 右栏
```

## 全屏播放页

`components/player/FullPlayer.tsx`，点播放条左侧封面展开（桌面也适用）：

- 大封面（书名渐变 + 首字）、书名、作者、当前章名
- 大进度条 + 已播 / 剩余时间；触屏没有 hover，滑块常显（`.player-range--always`）
- 五个主控：上一章 / −15s / 播放暂停 / +15s / 下一章
- 底部：加书签、循环切倍速、关闭播放器
- 顶部分类按钮直达章节/书签面板

## 搜索页

`pages/Search.tsx` 复用 `GET /books?q=`，300ms 防抖、输入即搜（覆盖书名/作者/系列），
结果用 `BookRow` 渲染（可直接播放或进详情）。空关键词 / 无结果 / 请求失败各有独立状态；
命中超过单页 50 条时提示细化关键词。

## 设置页管理（设备 / 用户 / 书库）

`components/settings/DeviceSection.tsx`（所有登录用户）：

- 登录时由 `lib/device.ts` 解析 UA 上报浏览器/系统/形态/屏幕，列表显示「Chrome 141 · 手机 · Android 14 · 390×844」，
  可展开查看原始 UA；未上报的旧设备回退显示「旧版网页端」
- 在线状态由 `lib/presence.ts` 上报：可见时 45 秒心跳、隐藏 20 秒后离线、`pagehide` 立即离线（`keepalive`）；
  **后台播放时不降级**（音频在放就持续心跳），暂停后仍隐藏 20 秒才离线
- `GET /devices` 列表：在线 / 离线 / 最近活跃、当前设备标记、首次登录时间；被踢下线的设备灰显「已下线」
- 踢下线：`DELETE /devices/{id}` + 二次确认；踢的是当前设备时直接退出登录
- 管理员可切「全部用户」看他人设备（`?all=true`）

`components/settings/UserSection.tsx`（仅 `role=admin` 可见）：

- 新建用户（用户名 / 初始密码 / 角色）、改角色、停用启用、重置密码、删除
- 书库授权：点「分配书库」展开勾选，提交 `PATCH /users/{id}` 的 `library_ids`（整体替换）
- 保护规则：自己的角色 / 停用 / 删除按钮置灰，后端同样返回 409

`components/settings/LibrarySection.tsx`（仅 `role=admin` 可见）：

- 登记书库：名称 + 服务器绝对路径；登记成功即可触发扫描
- 每个库显示书籍数、上次扫描时间，支持启用/停用（停用后不出现在书架；管理员在设置里仍能看到该库并再次启用）
- 扫描：`POST /libraries/{id}/scan` 后轮询 `scan/status`；结果提示保留 6 秒 ——
  实际扫描常常 1 秒内就结束，不保留用户根本看不到反馈
- 删除：二次确认，仅删索引，不动硬盘文件

## 认证流程

- 首次部署 `users` 为空时，登录页可切到「初始化管理员」调用 `POST /auth/bootstrap`，成功后自动登录
- access token 只放内存；refresh token 存 `localStorage`，刷新页面时用 `POST /auth/refresh` 换回登录态
- 任意接口返回 401 → 并发合并成一次 refresh → 成功后重放原请求；refresh 也 401 则清空登录态
- 登录态清空后，`RequireAuth` 会把受保护页面重定向到 `/login`，并用 `state.from` 在登录后回跳

## 视觉规范

三层材质，避免「到处发光」：

| 层 | 用途 | 实现 |
|---|---|---|
| 光斑 | 页面底层的氛围色，给玻璃提供可模糊的内容 | `AppShell` 里三块 `fixed` 径向渐变 + `blur-[110px]`，随主题色变化 |
| 玻璃 | 顶栏、底栏、播放条、卡片、抽屉 | `.glass` / `.glass-bar` / `.glass-panel`（`backdrop-blur-2xl` + `saturate-150`） |
| 渐变 | 只用在「主动作」与「品牌标识」上 | `bg-brand-gradient`、`.btn-gradient`、`.text-gradient`、`.bg-card-fade` |

约束：

- **透明度只写 Tailwind 刻度内的值**（0/5/10/…/95/100），需要精确值写成 `bg-ink-900/[0.92]`。
  写成 `bg-ink-900/92` 这类裸值不会生成类名，元素会变成透明背景——文字与页面同色就「看不见」了
  （撤销提示条踩过这个坑）。
- 品牌渐变取自 `--brand-400/500/600`，**换主题色时渐变与阴影一起变**（`boxShadow` 也读 CSS 变量）
- 渐变不要用于正文文字与大面积背景；标题只在首页 Hero 用一次 `.text-gradient`
- 玻璃必须叠在光斑或图片上，否则看不出模糊，等于半透明白块
- `glass` 的浅色边框用 `zinc-200/60`（在白底上可见），深色用 `white/10`

动效（都在 `styles/index.css`，统一遵守 `prefers-reduced-motion`）：

| 动效 | 触发 | 参数 |
|---|---|---|
| `page-in` | 路由切换（`main` 内包裹 `key=pathname`） | 0.32s，上移 6px + 淡入 |
| `progress-shine` | 播放中且进度 >2%，叠在已播区间 | 2.6s 循环，白色高光扫过 |
| `card-sweep` | 书架卡片 hover | 0.9s 单次，-14° 斜扫 |

## 主题系统

两层偏好，都存 `localStorage`：

| 维度 | key | 取值 |
|---|---|---|
| 模式 | `echoshelf.theme` | `dark`（默认）/ `light` |
| 主题色 | `echoshelf.accent` | 任意 `#RRGGBB` |

Tailwind 的 `brand-50…900` 全部指向 CSS 变量（`rgb(var(--brand-500) / <alpha-value>)`），
`styles/accent.ts` 只接收一个主色 hex，按固定权重与黑/白混合推出 10 阶并写入 `:root` 行内样式，
因此 `bg-brand-500`、`bg-brand-500/10`、`border-brand-500/40` 这些类会整体跟随，无需逐个改。

新增预设只需往 `ACCENTS` 加一项：

```ts
{ id: "sky", label: "天蓝", hex: "#0EA5E9" }
```

主题色在 `store/ui.ts` 模块加载时立即应用（早于 React 首次渲染），所以刷新不会看到默认橙一闪而过。

## UI 基调

深色优先（听书多在夜间），默认主色暖橙 `#E8843C`（用户可在设置里换成海蓝/紫罗兰/松绿/玫红/石墨或任意色），
卡片圆角 12px，书架网格 `auto-fill minmax(150px,1fr)`。
必须是**移动优先**的响应式布局：手机上底部播放条 + 全屏播放页，桌面上左侧导航 + 右侧播放器。
