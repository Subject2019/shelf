# release — 分发包输出目录

存放「可以直接分发给别人」的构建产物，**不存源码**。所有内容由脚本生成，目录本身只保留本文件与 `.gitkeep`。

## 产物命名

| 文件 | 当前大小 | 是什么 | 怎么用 |
|---|---|---|---|
| `echoshelf-<版本>-linux-<架构>-bare.tar.gz` | 206 KB | 常规部署包：后端源码 + 预构建前端 + `install.sh` | 解压后 `sudo ./install.sh` |
| `echoshelf-<版本>-linux-<架构>-docker.tar.gz` | 90 MB | **Docker 镜像本体**（`docker save` 的归档，gzip 压缩；解压后 364 MB） | `docker load -i` 后 `docker compose up -d` |
| `*.sha256` | 106 B | 上面两个包的校验值 | `sha256sum -c xxx.sha256` |

示例：`shelf-0.1.0-linux-amd64-docker.tar.gz`

> ⚠️ `-docker.tar.gz` 里是 `blobs/` + `manifest.json`，这是 Docker 的镜像归档格式，
> **不是**源码目录，也**不需要** Dockerfile。`docker load` 后镜像里已含前端静态资源与 ffmpeg。

### 离线镜像怎么用

```bash
sha256sum -c shelf-0.1.0-linux-amd64-docker.tar.gz.sha256
docker load -i shelf-0.1.0-linux-amd64-docker.tar.gz
docker images shelf            # 0.1.0 与 latest 两个 tag

# 方式一：compose（推荐，仓库里的 compose 已指向该镜像）
docker compose up -d

# 方式二：直接跑
docker run -d --name shelf -p 8080:8080 \
  -v /path/to/audiobooks:/audiobooks:ro -v /path/to/data:/data \
  shelf:0.1.0
```

## 怎么生成

```bash
# 常规部署包（会先构建前端）
deploy/build-release.sh

# 只打包、复用已有 web/dist
deploy/build-release.sh --skip-web

# 连 Docker 镜像一起打（构建较慢，放在最后做）
deploy/build-release.sh --docker
```

版本号来自 `backend/app/core/config.py` 的 `APP_VERSION`，架构取 `uname -m`（amd64 / arm64）。

## 常规包结构

```
shelf-0.1.0-linux-amd64/
├── VERSION
├── MANIFEST.txt          # 文件清单 + sha256
├── install.sh            # 安装到 /opt/echoshelf + systemd
├── uninstall.sh
├── README.md
├── app/                  # 后端源码（不含 tests / venv）
│   ├── app/
│   ├── alembic/
│   ├── alembic.ini
│   └── requirements-prod.txt
├── web/dist/             # 预构建前端，后端直接托管
├── echoshelf.service.in  # systemd 模板
└── echoshelf.env.example
```

## 注意

- 本目录在 `.gitignore` 里（只保留 README 与 `.gitkeep`），发布物不进版本库
- 打包脚本不会带上 `data/`、`.env`、测试样本音频
- 每个包都要有 `.sha256`，分发时一起给，安装前可 `sha256sum -c` 校验
