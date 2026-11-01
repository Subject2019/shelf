# 声架 · 飞牛 fnOS 应用

基于现有镜像 `ghcr.io/subject2019/shelf:0.2.7` 的飞牛 fnOS 应用工程。

- 应用名：`shelf`
- 显示名称：**声架**
- 版本：`0.2.7`
- 架构：`x86`（当前镜像只有 `linux/amd64`）
- 容器名：`shelf-fnos`
- 默认端口：`8080`

> 前置条件：飞牛设备需要能访问 GHCR，并且 `ghcr.io/subject2019/shelf:0.2.7` 必须为 Public；如果仍为 Private，请先在设备上执行 `docker login ghcr.io`。

## 目录结构

```text
fnos/
├── manifest                 # fpk 元数据
├── ICON.PNG / ICON_256.PNG  # 应用中心图标
├── app/
│   ├── docker/
│   │   └── docker-compose.yaml
│   └── ui/
│       ├── config           # 桌面入口
│       └── images/          # 64/256 图标
├── cmd/                     # 安装、升级、卸载、状态脚本
├── config/
│   ├── resource             # Docker 项目 + 媒体共享目录
│   └── privilege            # 运行用户
├── wizard/
│   └── install              # 安装向导
└── README.md
```

## 构建

需要飞牛官方 `fnpack`：

```bash
cd fnos
fnpack build
```

构建产物默认是当前目录下的 `shelf.fpk`。

## 安装

在飞牛应用中心手动安装 `shelf.fpk`，安装向导会要求填写：

1. 管理员用户名；
2. 管理员密码（至少 8 位）；
3. 是否启用服务端转码。

安装完成后打开「声架」入口，地址由飞牛应用入口代理到容器 `8080` 端口。

## 媒体目录

本工程使用飞牛的数据共享目录，而不是让用户直接填写任意宿主机路径：

```text
应用文件 → shelf → media
```

在飞牛文件管理器中把有声书放入该目录后，声架会扫描 `/audiobooks`。

对应容器挂载：

```text
${TRIM_DATA_SHARE_PATHS}:/audiobooks:ro
```

媒体目录以只读方式挂载，声架不会修改原始音频文件。

## 数据与凭据

| 内容 | 位置 |
|---|---|
| SQLite 数据库、缓存 | `${TRIM_PKGVAR}/data` |
| 管理员密码 | `${TRIM_PKGETC}/admin_password` |
| 运行配置 | `${TRIM_PKGETC}/shelf.env` |

管理员密码通过 Docker secret 方式以文件挂载进容器，不写入 Compose 环境变量。

## 与现有 Docker 部署的关系

这个 fpk 使用的容器名是 `shelf-fnos`，不会覆盖现有的 `shelf` 容器；默认端口 `8080` 也与现有 `8090` 部署互不影响。

如果已有 `shelf` 容器，可以同时运行，但两边数据库和媒体目录是独立的。

## 已知限制

- 当前镜像为 `linux/amd64`，因此 `manifest` 只声明 `platform=x86`；ARM 飞牛设备需要先构建多架构镜像。
- 如果飞牛设备上 `8080` 已被占用，需要在 `manifest`、`app/ui/config` 和 Compose 中同步修改端口。
- 首个版本固定使用飞牛数据共享目录 `shelf/media`，暂不支持在安装向导里直接选择任意宿主机目录。
- 升级时会保留 `${TRIM_PKGVAR}` 和 `${TRIM_PKGETC}`；卸载时默认不删除数据，具体以飞牛应用中心提示为准。
- 应用内的管理员密码修改仍通过声架 WebUI 完成；重新安装向导只负责首次管理员创建。

## 版本同步

发布新镜像时，需要同时修改：

```text
fnos/manifest
fnos/app/docker/docker-compose.yaml
```

确保 `manifest.version`、Compose 镜像 tag 和服务端版本一致。
