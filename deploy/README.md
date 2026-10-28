# deploy — 部署与运维

部署文件按「部署方式」分目录摆放，每种方式都可以独立分发；构建好的分发包统一输出到
[`../release/`](../release/)。

```
deploy/
├── docker/                  # 方式一：Docker（推荐）
│   ├── Dockerfile
│   ├── docker-entrypoint.sh
│   ├── docker-compose.yml
│   ├── .env.example
│   └── README.md
├── bare/                    # 方式二：常规部署（systemd / 前台运行）
│   ├── install.sh
│   ├── uninstall.sh
│   ├── echoshelf.service.in
│   ├── echoshelf.env.example
│   └── README.md
├── build-release.sh         # 打分发包（输出到 ../release）
├── nginx.conf               # 反向代理模板（两种方式通用）
└── scripts/
    ├── backup.sh            # 在线备份（SQLite backup API）
    └── healthcheck.sh       # 手动健康检查与诊断
```

## 选哪种

| 方式 | 适合 | 优点 | 代价 |
|---|---|---|---|
| Docker | 群晖 / 威联通 / unRAID / 有 Docker 的 Linux | 一条命令、依赖隔离、升级换镜像 | 需要 Docker；镜像约 365 MB |
| 常规部署 | 没有 Docker、想复用系统 Python、或要自己控制进程 | 不依赖容器运行时，体积小（960 KB） | 需要系统有 Python 3.10+ 与 ffmpeg |

两种方式的数据目录结构完全一致（`config/echoshelf.db`、`cache/`、`logs/`），
可以从一种迁到另一种，直接拷 `data/` 即可。

## 快速开始

### Docker

```bash
cd deploy/docker
cp .env.example .env        # 至少改 AUDIOBOOKS_PATH
docker compose up -d --build
curl -s localhost:8080/api/v1/health
```

### 常规部署

```bash
# 先打一个分发包（或直接用别人给的同名 tar.gz）
deploy/build-release.sh

tar xzf release/shelf-0.2.5-linux-amd64-bare.tar.gz
cd shelf-0.2.5-linux-amd64
sudo ./install.sh --audiobooks /volume1/media/audiobooks
systemctl status echoshelf
```

## 打分发版

```bash
deploy/build-release.sh                 # 常规部署包（含前端构建）
deploy/build-release.sh --skip-web      # 复用已有 web/dist
deploy/build-release.sh --with-wheels   # 额外带 wheels/，可 --offline 安装
deploy/build-release.sh --docker        # 再导出离线镜像（最慢，建议最后跑）
```

产物与校验值都在 `release/`，命名规则见 [`../release/README.md`](../release/README.md)。

当前实测产物：

| 文件 | 大小 | 用途 |
|---|---|---|
| `shelf-0.2.5-linux-amd64-bare.tar.gz` | 294 KB | 解压后 `sudo ./install.sh` |
| `shelf-0.2.5-linux-amd64-docker.tar.gz` | 90 MB | `docker load -i` 后离线运行（tag `0.2.5` 与 `latest`） |
| `shelf-0.2.5-debug.apk` | 4.0 MB | Android WebView 壳 debug 包 |

## 备份与检查

```bash
# 在线备份（不停服）
deploy/scripts/backup.sh /path/to/backups

# 恢复（自动停容器、当前库留底、起服后等健康检查）
deploy/scripts/restore.sh /path/to/backups/echoshelf-20261026-021500.tar.gz

# 健康检查 + 诊断
deploy/scripts/healthcheck.sh http://127.0.0.1:8080
```

备份实测：删掉 `echoshelf.db` 后恢复，4 本书 / 3 条进度 / 5 条回溯点全部回来，原密码可登录；
含 `../` 或缺少 `echoshelf.db` 的归档会被拒绝，容器不受影响。

完整 NAS 步骤见 [`../docs/DEPLOY_NAS.md`](../docs/DEPLOY_NAS.md)。
