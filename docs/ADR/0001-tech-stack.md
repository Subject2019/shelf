# ADR-0001 技术栈与整体形态

- 状态：已采纳
- 日期：2026-10-23
- 决策者：项目初始化（CodeBuddy）

## 背景

要在 NAS 上自托管有声书服务，需求是：Docker 单点部署、完整网页播放端、安卓 App、广泛音频格式支持、多端进度同步。使用者是个人/家庭，通常不熟悉运维，机器资源有限（2–8 GB 内存，ARM 或低功耗 x86）。

## 决策

1. **后端 Python 3.12 + FastAPI**
2. **数据库 SQLite（WAL 模式）**
3. **前端 React 18 + TypeScript + Vite + Tailwind**，构建产物打进后端镜像
4. **安卓 Kotlin + Jetpack Compose + Media3**
5. **音频元数据用 mutagen，章节/流信息用 ffprobe**
6. **传输策略：原文件 Range 直出优先，ffmpeg 转码兜底**
7. **单容器单进程，不引入 Postgres / Redis / Nginx（反代交给用户可选）**

## 理由

| 决策 | 理由 |
|---|---|
| FastAPI | 异步流式响应天然适合音频；Pydantic 契约清晰；与 SQLAlchemy/mutagen 生态成熟；代码量小，AI agent 易维护 |
| SQLite | 单机读多写少；WAL 下并发读不阻塞；零运维、单文件备份；10 万级元数据完全够用。引入 Postgres 会让 NAS 用户多维护一个容器，收益为零 |
| React | 播放器状态复杂（队列、速率、定时、章节），React + Zustand 的可预测状态管理优于模板方案；生态里音频/虚拟列表组件多 |
| Compose + Media3 | Media3 是官方播放栈，`MediaSessionService` 一次性解决后台播放、锁屏、通知、蓝牙耳机按键 |
| mutagen + ffprobe | mutagen 纯 Python、读标签快且无进程开销；章节解析（m4b chpl / ID3 CHAP / CUE）统一交给 ffprobe，避免为每种容器各写解析器 |
| Range 直出优先 | 听书是长时低码率顺序读，直出零 CPU、零延迟、可任意 seek。转码只作为格式不兼容时的兜底，避免弱 NAS 被转码压垮 |
| 单容器 | 用户心智负担最小；前端静态文件体积仅几 MB，没必要单独 Web 容器 |

## 后果

**正面**
- 部署只需一个 compose 文件、一个数据目录、一个端口。
- 备份 = 拷 `echoshelf.db` + `secret.key`。
- 开发链路短：改后端不需要重建前端容器。

**负面 / 需承担**
- SQLite 只允许单写者：扫描与进度上报写入必须串行化（已用单写者队列 + `busy_timeout` 缓解）。若未来做多实例水平扩展，需迁移 Postgres（ADR 另议）。
- 单进程意味着扫描是后台线程而非独立 worker；扫描大库时可能影响 API 延迟（用 `run_in_threadpool` 与让出 GIL 的 IO 缓解）。
- 前端打包进镜像 → 改前端需重建镜像（开发用 `vite dev` + 代理规避）。
- ARM NAS 上 ffmpeg 转码可能实时性不足 → 默认关闭，作为可选项。

## 备选方案（已否决）

| 方案 | 否决原因 |
|---|---|
| Node.js (NestJS) 全栈 | 音频元数据/CUE/ffprobe 生态弱于 Python；TS 全栈听起来优雅但无实质收益 |
| Go 单二进制 | 部署最优雅，但元数据解析库少（CUE/ID3 章节需手写），迭代速度慢 |
| Plex/Jellyfin + 插件 | 无法满足有声书特有的章节/进度/系列语义；插件受宿主限制 |
| Postgres + Redis + Celery | 对 NAS 单机是过度设计，运维成本转嫁给用户 |
| 纯 PWA 代替安卓 App | 后台播放与离线下载在 iOS/部分安卓上不可靠；用户明确要求原生 App |
| 先做 App 再做 Web | Web 是验证 API 契约最便宜的途径，顺序颠倒会返工 |

## 复审触发条件

- 单库文件数 > 50 万且扫描成为瓶颈 → 评估独立 worker 进程
- 出现多实例/多用户量级 > 50 → 评估 Postgres
- 移动端需求转向 iOS → 评估 KMP 或 Flutter 重写，而非双原生
