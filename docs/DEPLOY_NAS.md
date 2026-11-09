# NAS 部署手册

目标：在群晖 / 威联通 / unRAID / TrueNAS / 任意 Linux 上，用一条 compose 命令跑起来。

> 状态：**M3 已完成（2026-10-26）**。镜像、compose、备份恢复、分发包与实机验收均已跑通；
> 实机基线：Debian 13 / 4 核 / 3.8 GB，1000 本扫描 175.9s。
> Docker：`docker build -f deploy/docker/Dockerfile -t shelf:latest .`（Alpine 多阶段，约 363 MB）。
> 常规部署：`deploy/build-release.sh` 产出分发包，`deploy/bare/install.sh` 安装（systemd）。
> 本手册以 Docker 为主线，常规部署的细节见 [`deploy/bare/README.md`](../deploy/bare/README.md)。

## 0. 选择部署方式

| 方式 | 前提 | 入口 |
|---|---|---|
| Docker（本手册主线） | Docker ≥ 24 + compose v2 | [`deploy/docker/`](../deploy/docker/README.md) |
| 常规部署（无容器） | Python ≥ 3.10、ffmpeg | [`deploy/bare/`](../deploy/bare/README.md) |

两种方式使用同一套 `data/` 结构，可以互相迁移。分发包构建见
[`deploy/build-release.sh`](../deploy/build-release.sh)，产物在 `release/`。

## 1. 前置条件

| 项 | 要求 |
|---|---|
| Docker | ≥ 24，含 compose v2 |
| 架构 | AMD64（x86_64）；实机为 AMD64，ARM64 暂不提供镜像 |
| 内存 | ≥ 512 MB 空闲（扫描 10 万文件峰值约 300 MB） |
| 磁盘 | 媒体目录 + 数据库约 100 MB |
| 端口 | 默认 8080（可改） |

## 2. 目录约定（宿主侧）

```text
/volume1/docker/echoshelf/        # 配置目录（备份它）
├── .env
├── docker-compose.yml
└── data/                         # 容器 /data
    ├── config/echoshelf.db
    ├── config/secret.key
    └── cache/covers/

/volume1/media/audiobooks/        # 媒体目录（只读挂载）
├── 中文小说/
└── English/
```

## 3. 部署步骤

```bash
# 1. 建目录
mkdir -p /volume1/docker/echoshelf/data
cd /volume1/docker/echoshelf

# 2. 取部署模板（或从仓库复制 deploy/docker/ 下的两个文件）
cp /path/to/echoshelf/deploy/docker/docker-compose.yml .
cp /path/to/echoshelf/deploy/docker/.env.example .env

# 3. 编辑 .env（必改 AUDIOBOOKS_PATH）
vi .env

# 4. 启动（有本地 Dockerfile 时加 --build）
docker compose up -d --build

# 5. 创建管理员（网页端已不提供初始化入口，二选一）
#    a) 在 .env 里设置 ECHOSHELF_ADMIN_PASSWORD(_FILE) → 首次启动自动创建
#    b) 启动后执行：
#       docker exec -it shelf python -m app.cli admin create
```

`.env` 关键项：

```ini
ECHOSHELF_PORT=8080
AUDIOBOOKS_PATH=/volume1/media/audiobooks   # ← 必改
ECHOSHELF_ADMIN_USERNAME=admin
ECHOSHELF_ADMIN_PASSWORD=ChangeMe_至少8位     # 首次启动生效；也可留空后用 CLI
# ECHOSHELF_ADMIN_PASSWORD_FILE=/run/secrets/echoshelf_admin   # Docker secret（推荐）
# ECHOSHELF_ADMIN_SYNC_PASSWORD=true   # 开启后每次启动都用上面的密码覆盖管理员
TZ=Asia/Shanghai
PUID=1000
PGID=1000
```

### 通用 Linux（Debian / Ubuntu / 飞牛 fnOS 等）

EchoShelf 就是普通 Docker 应用，不依赖任何 NAS 专有接口。宿主机装好 Docker ≥ 24 + compose v2 后：

```bash
mkdir -p ~/echoshelf/data ~/audiobooks
cd ~/echoshelf
cp <仓库>/deploy/docker/docker-compose.yml .
cp <仓库>/deploy/docker/.env.example .env      # 改 AUDIOBOOKS_PATH / ECHOSHELF_DATA_PATH
docker compose up -d --build
curl -s localhost:8080/api/v1/health
```

宿主路径按发行版习惯放即可，容器内固定是 `/audiobooks`（只读）与 `/data`（可写）。
`PUID/PGID` 填媒体目录的属主（`id -u` / `id -g`），入口脚本会 `chown -R /data` 后降权运行。

### 飞牛 fnOS（已实机部署）

飞牛基于 Debian 12，Docker 与 Compose 在**应用中心**安装，操作与通用流程一致。

本项目的实际部署（2026-10-26，fnOS `192.168.31.103`）：

```bash
# 目录
/vol5/1000/docker2/shelf/
├── docker-compose.yml
└── data/                 # DB + 密钥 + 封面/转码缓存

# compose 关键项（完整文件见该机器上的 docker-compose.yml）
ports:      "8090:8080"                 # 8080 被开发服务占用，故用 8090
environment: PUID=1000 PGID=1001        # 媒体目录属主 subject:Users
volumes:
  - "/vol5/1000/音频/有声书:/audiobooks:ro"
  - "/vol5/1000/docker2/shelf/data:/data"
```

```bash
cd /vol5/1000/docker2/shelf
docker compose up -d          # 首次会自动迁移并在设置了 ADMIN_PASSWORD 时建管理员
docker compose ps             # Up (healthy)
docker compose logs -f --tail=50
```

实测结果：9 本书 / 990 个音频（27 GB 媒体库），扫描约 3 分钟（串行 ffprobe），
跨机访问 `http://192.168.31.103:8090` 首页 200、未登录接口 401。

fnOS 注意事项：

1. 存储卷是 `/vol1`…`/volN`，用户目录形如 `/vol5/1000/<用户名>/`（**没有** `/volume1`）
2. 飞牛的文件权限用 ACL 表现，`ls -ld` 可能显示 `drwx------`，但同 uid 仍可读；
   容器用 `PUID/PGID` 对齐媒体目录属主即可
3. 端口避开飞牛自身服务（8090 实测可用，8080 常被开发服务占用）
4. 媒体目录不要挂载可写：`/audiobooks:ro` 足够，扫描不会写媒体盘

### 群晖 / 威联通 / unRAID

同样适用上面的通用流程，差异只在宿主路径：

| 平台 | 项目目录 | 媒体目录 |
|---|---|---|
| 群晖 DSM 7 | `/volume1/docker/echoshelf` | `/volume1/media/audiobooks` |
| 威联通 | `/share/Container/echoshelf` | `/share/Media/audiobooks` |
| unRAID | `/mnt/user/appdata/echoshelf` | `/mnt/user/media/audiobooks` |

群晖注意给 `docker` 组媒体目录的只读权限，并关闭「自动封锁」以免反代探测被误封。

## 4. 反向代理与 HTTPS

局域网可以直连 `http://NAS:8080`。需要远程访问时**必须**上 HTTPS（App 与浏览器都更安全）。

### Caddy（推荐，自动证书）

```caddyfile
books.example.com {
    encode zstd gzip
    # 大文件流式，关闭缓冲
    reverse_proxy 127.0.0.1:8080 {
        flush_interval -1
    }
    request_body {
        max_size 10GB
    }
}
```

### Nginx

```nginx
server {
    listen 443 ssl http2;
    server_name books.example.com;
    ssl_certificate     /etc/ssl/fullchain.pem;
    ssl_certificate_key /etc/ssl/privkey.pem;

    client_max_body_size 10G;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_buffering off;          # 关键：音频流不缓冲
        proxy_request_buffering off;
        proxy_read_timeout 3600s;
        # Range 透传（Nginx 默认支持，勿加 proxy_set_header Range ""）
    }
}
```

> 反代要点：`proxy_buffering off`、足够长的 `proxy_read_timeout`、不要改写 `Range`/`If-Range` 头。

## 5. 资源限制与性能

compose 中默认：

```yaml
deploy:
  resources:
    limits:   { cpus: "2.0", memory: 1G }
    reservations: { memory: 128M }
```

- 扫描是单线程串行，`cpus` 无需给多；瓶颈在磁盘 IO。
- 转码需要 CPU：ARM 低端 NAS（如 J4125 尚可，ARMv8 四核）建议在设置里关闭转码。
- SQLite 走 WAL，建议把 `data/` 放在 **SSD 或 NAS 本地盘**，不要放网络共享（SMB/NFS 上 SQLite 锁不可靠）。

> ⚠️ 重要：`/data` **不要**挂载到 SMB/NFS 网络盘，否则数据库可能损坏。媒体目录放网络盘没问题（只读顺序读）。

## 6. 备份与恢复

仓库自带两个脚本，**不需要停服**：

```bash
# 备份（SQLite 用 backup API，在线一致快照；默认保留最近 7 份）
deploy/scripts/backup.sh /path/to/backups

# 恢复（自动停容器 → 留底当前库 → 解包 → 起服 → 等健康检查）
deploy/scripts/restore.sh /path/to/backups/echoshelf-20261026-021500.tar.gz
```

`restore.sh` 的行为与安全约束：

| 行为 | 说明 |
|---|---|
| 归档校验 | 拒绝绝对路径与 `..`，必须含 `echoshelf.db`；缺 `secret.key` 只告警（需重新登录） |
| 留底 | 覆盖前把当前库复制为 `echoshelf.db.before-restore-<时间>`，可手工回滚 |
| 容器定位 | 通过 `docker inspect` 自动找 `/data` 挂载点，也可 `--data-dir` 指定 |
| 验证 | 起服后等 40s 健康检查，并打印 users/books/progress 等行数 |

实测（2026-10-26，4 本真实书 + 3 条进度 + 5 条回溯点）：

```
备份 → 删除 echoshelf.db → 重启后 users=0 books=0
恢复 → users=1 libraries=1 books=4 progress=3 progress_history=5，原密码可登录
重跑恢复（幂等）→ 行数不变
非法归档（含 ../、无 echoshelf.db）→ 退出码 1，容器不受影响
```

媒体文件无需备份（用户自有），重扫即可恢复索引。

## 7. 升级

```bash
# 有 Registry：拉新镜像
cd ~/echoshelf && docker compose pull && docker compose up -d

# 无网络 / 离线包：先 load 再起来
docker load -i shelf-0.2.5-linux-amd64-docker.tar.gz
docker compose up -d          # 启动时自动 alembic upgrade head
docker image prune -f
```

镜像有两个 tag：`shelf:<版本>`（如 `0.2.12`，固定用）与 `shelf:latest`（跟最新构建）。

迁移失败会拒绝启动（日志 `migration failed`），此时回滚镜像 tag 并用备份恢复数据库。

## 8. 健康检查与排障

```bash
docker compose ps                          # STATUS 应为 healthy
docker compose logs -f --tail=200 echoshelf
curl -s localhost:8080/api/v1/health | jq
```

| 现象 | 排查 |
|---|---|
| 容器 unhealthy | `curl` 容器内 `/api/v1/health`，看 `db` 字段 |
| 书库扫描 0 本 | 路径填的是**容器内**路径（`/audiobooks/xxx`），不是宿主路径 |
| 扫描报权限错误 | `PUID/PGID` 与媒体目录属主不一致；`docker compose exec echoshelf id` 对照 |
| 播放卡顿/拖动失败 | 反代是否关闭 buffering、是否改写 Range；`curl -I -H 'Range: bytes=0-1' URL` 应返回 206 |
| 中文文件名乱码 | 宿主 locale；容器内统一 UTF-8，检查 `LANG=C.UTF-8` |
| 数据库 locked | `/data` 是否在网络盘；确认 WAL 已启用 |
| 内存持续增长 | 扫描大库时的正常波动；若 OOM 调低并发或加内存上限 |

## 9. 安全清单

- [ ] 修改默认管理员密码，禁用注册（`ECHOSHELF_ALLOW_REGISTRATION=false`）
- [ ] 远程访问走 HTTPS，端口不直接暴露公网
- [ ] `/audiobooks` 只读挂载
- [ ] 定期备份 `data/config/`（含 `secret.key`）
- [ ] 不在 `.env` 提交到公开仓库

## 10. 无 Docker 的裸机方式（备选）

```bash
python3.12 -m venv /opt/echoshelf/.venv
/opt/echoshelf/.venv/bin/pip install -r backend/requirements.txt
ECHOSHELF_DATA_DIR=/var/lib/echoshelf \
ECHOSHELF_LIBRARIES='[{"name":"默认","root_path":"/mnt/audiobooks"}]' \
/opt/echoshelf/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080
```
配 systemd unit（`Restart=always`）。仅推荐给不用 Docker 的 Linux 用户。
