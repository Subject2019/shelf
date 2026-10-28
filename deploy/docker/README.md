# Docker 部署

| 文件 | 用途 |
|---|---|
| `Dockerfile` | 多阶段镜像：node 构建前端 → python 运行时（含 ffmpeg） |
| `docker-entrypoint.sh` | 入口：按 PUID/PGID 降权 → 迁移 → 启动 |
| `docker-compose.yml` | 生产部署模板（单容器，媒体只读挂载） |
| `.env.example` | 环境变量模板，复制为 `.env` 后修改 |
| `nginx.conf` | 反向代理模板（HTTPS + 音频流不缓冲） |

完整步骤见 [`../../docs/DEPLOY_NAS.md`](../../docs/DEPLOY_NAS.md)；两种部署方式的取舍见 [`../README.md`](../README.md)。

## 快速开始

```bash
cd deploy/docker
cp .env.example .env
vi .env                     # 至少改 AUDIOBOOKS_PATH
docker compose up -d --build   # 镜像约 363 MB，首次 3-5 分钟
docker compose logs -f
docker compose logs -f
curl -s localhost:8080/api/v1/health
```

镜像结构：`node:20-alpine` 构建 `web/dist` → `python:3.11-alpine` 运行时（apt 装不了就 `apk add ffmpeg`），
前端由 FastAPI 直接托管，启动时由 `docker-entrypoint.sh` 先跑 `alembic upgrade head`。
只用 `docker` 不用 compose 时：

```bash
# 在仓库根目录执行（context 是仓库根，Dockerfile 在 deploy/docker/）
docker build -f deploy/docker/Dockerfile -t shelf:latest .
docker run -d --name shelf -p 8080:8080 \
  -v /volume1/media/audiobooks:/audiobooks:ro \
  -v /volume1/docker/shelf:/data \
  -e ECHOSHELF_ADMIN_PASSWORD=你的密码 \
  shelf:latest
```

## 变量速查

| 变量 | 默认 | 说明 |
|---|---|---|
| `AUDIOBOOKS_PATH` | `/volume1/media/audiobooks` | 宿主机媒体目录，**必改** |
| `ECHOSHELF_DATA_PATH` | `./data` | 数据库与缓存，必须本地盘 |
| `ECHOSHELF_PORT` | `8080` | 对外端口 |
| `ECHOSHELF_ADMIN_USERNAME` | `admin` | 初始管理员用户名（仅首次启动生效） |
| `ECHOSHELF_ADMIN_PASSWORD` | 空 | 初始管理员密码；空则用 CLI 创建 |
| `ECHOSHELF_ADMIN_PASSWORD_FILE` | 空 | 从文件读密码（Docker secret），优先于明文 |
| `ECHOSHELF_ADMIN_SYNC_PASSWORD` | `false` | 开启后每次启动都把环境变量密码同步到管理员 |
| `ECHOSHELF_ALLOW_REGISTRATION` | `false` | 自助注册开关 |
| `ECHOSHELF_ENABLE_TRANSCODE` | `true` | 弱 NAS 建议关 |
| `PUID` / `PGID` | `1000` | 运行身份，需对媒体有读权限 |
| `ECHOSHELF_CPUS` / `ECHOSHELF_MEMORY` | `2.0` / `1g` | 资源上限 |

## 管理员（只能带外创建）

网页端没有初始化入口，也不会把谁提升成管理员。两种方式二选一：

```bash
# 1) 启动时就建好（推荐）：.env 里设置
ECHOSHELF_ADMIN_PASSWORD=ChangeMe_至少8位
# 或
ECHOSHELF_ADMIN_PASSWORD_FILE=/run/secrets/echoshelf_admin

# 2) 启动后交互创建 / 重置
docker exec -it shelf python -m app.cli admin create
docker exec -it shelf python -m app.cli admin reset-password
docker exec -it shelf python -m app.cli admin list
```

- 默认只有库为空时才会自动创建；已有管理员时不会覆盖密码
- 想让「改环境变量 + 重启」就生效：设 `ECHOSHELF_ADMIN_SYNC_PASSWORD=true`（开启后网页改密会被下次重启覆盖）
- `admin demote-others` 可把历史遗留的多个管理员收敛成一个
- 恢复只需 `docker exec` 权限，不依赖登录态

## 注意

- 镜像地址为 `ghcr.io/subject2019/shelf`；`docker compose build` 会用
  `deploy/docker/Dockerfile` 构建同名 tag，无需联网拉镜像。
- 容器按 `PUID` / `PGID` 降权运行（入口脚本建用户 + `su-exec`），首次启动会把数据目录
  `chown -R` 成该属主；`docker compose exec shelf id` 可确认实际身份。
- 媒体目录是只读挂载，`PUID` 需要有读权限；无权限时扫描会报 `Permission denied`。
- 多书库：在 compose 里追加只读挂载（如 `/volume2/books:/audiobooks/english:ro`），
  然后在网页端「设置 → 书库」按容器内路径登记。
- 升级：`docker compose pull && docker compose up -d`，启动时自动跑数据库迁移。
- 卸载：`docker compose down`，数据留在 `ECHOSHELF_DATA_PATH`，删除即彻底清理。
