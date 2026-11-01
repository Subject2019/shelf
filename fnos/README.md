# 声架 · 飞牛 fnOS 应用

声架（shelf）是面向飞牛 NAS 的自托管有声书服务器：自动扫描书库，支持 M4B/MP3 等多格式与章节播放、多端进度同步、收藏和收听统计，并可通过 Android App 原生后台播放。

本目录基于现有镜像 `ghcr.io/subject2019/shelf:0.2.8` 构建飞牛 fnOS 应用包。

- 应用名：`shelf`
- 显示名称：**声架**
- 应用包版本：`0.2.8-1`（运行镜像为 `0.2.8`）
- 架构：`x86`（当前镜像只有 `linux/amd64`）
- 容器名：`shelf-fnos`
- 默认端口：`8080`，安装时可修改

> 前置条件：飞牛设备需要能访问 GHCR，并且 `ghcr.io/subject2019/shelf:0.2.8` 必须为 Public；如果仍为 Private，请先在设备上执行 `docker login ghcr.io`。

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

1. **访问端口**：默认 `8080`，可改成 `8090`、`18080` 等；
2. **有声书目录（可选）**：留空使用共享目录 `shelf/media`，也可以填写已有目录的绝对路径；
3. 管理员用户名；
4. 管理员密码（至少 8 位）；
5. 是否启用服务端转码。

安装完成后打开「声架」入口，飞牛会按安装时填写的端口代理到容器 `8080`。

如果安装仍然失败，先查看：

```text
${TRIM_PKGVAR}/install.log
```

或飞牛应用中心对应应用的安装日志。`0.2.7-2` 起已把安装阶段可能失败的凭据检查移出 `install_init`。

## 媒体目录

安装向导提供两种方式：

### 方式一：使用声架共享目录（留空即可）

```text
应用文件 → shelf → media
```

把有声书放入该目录后，声架会扫描 `/audiobooks`。

### 方式二：使用已有目录

在「有声书目录」中填写飞牛上的绝对路径，例如：

```text
/vol1/1000/媒体/有声书
```

该目录会以只读方式挂载到容器 `/audiobooks`。

> 当前飞牛向导只提供文本路径输入，不是原生的文件夹选择器。请确认目录已经存在，并且应用用户有读取权限；如有需要，也可以在安装后的应用设置里给声架授权该目录。对应 Compose 表达式为：

```text
${wizard_media_path:-${TRIM_DATA_SHARE_PATHS:-${TRIM_PKGVAR}/media}}:/audiobooks:ro
```

媒体目录以只读方式挂载，声架不会修改原始音频文件。

> 安装完成后在应用内「设置 → 书库」登记时，路径要填**容器内路径**：`/audiobooks` 或其子目录（如 `/audiobooks/小说`），不要填上面的宿主机路径。应用默认已填好 `/audiobooks`。

## 访问端口

安装向导中的 `wizard_port` 同时用于 Compose 端口映射和飞牛桌面入口：

```text
宿主机端口（wizard_port） → 容器 8080
```

Compose：

```text
${wizard_port:-${TRIM_SERVICE_PORT:-8080}}:8080
```

飞牛入口：

```text
"port": "${wizard_port}"
```

默认 `8080`。如果 `8080` 已被其他服务占用，安装时改成 `8090`、`18080` 等即可；无需修改 manifest。

`manifest` 保留 `service_port = 8080` 作为默认元数据，并设置 `checkport = false`，因为实际端口由安装向导决定。

## 数据与凭据

| 内容 | 位置 |
|---|---|
| SQLite 数据库、缓存 | `${TRIM_PKGVAR}/data` |
| 安装日志 | `${TRIM_PKGVAR}/install.log` |

管理员用户名和密码由安装向导的 `wizard_admin_username` / `wizard_admin_password` 直接注入 Compose 环境变量。密码不会写入安装目录文件，但会存在于容器环境变量中，请自行评估宿主权限。

## 与现有 Docker 部署的关系

这个 fpk 使用的容器名是 `shelf-fnos`，不会覆盖现有的 `shelf` 容器；默认端口 `8080` 与现有 `8090` 部署互不影响。如果安装时改成其他端口，容器内部仍然监听 `8080`。

如果已有 `shelf` 容器，可以同时运行，但两边数据库和媒体目录是独立的。

## 已知限制

- 当前镜像为 `linux/amd64`，因此 `manifest` 只声明 `platform=x86`；ARM 飞牛设备需要先构建多架构镜像。
- 访问端口由安装向导决定；如果填写的端口已被占用，容器会启动失败，需要换一个端口重装。
- 安装向导的媒体目录是文本路径，不是原生目录选择器；路径不存在时不会阻止安装，但会导致书库为空。
- 升级时会保留 `${TRIM_PKGVAR}`；卸载时默认不删除数据，具体以飞牛应用中心提示为准。
- 应用内的管理员密码修改仍通过声架 WebUI 完成；安装向导只负责首次管理员创建。
- `0.2.7-2` 起安装脚本不再在 `install_init` 阶段读取密码，避免部分 fnOS 版本下因拿不到向导变量而报“执行脚本出错且原因未知”。

## 版本同步

发布新镜像时，修改：

```text
fnos/app/docker/docker-compose.yaml
```

如果应用包本身也有变更，再修改：

```text
fnos/manifest
```

`manifest.version` 是 fpk 版本，可以和运行镜像版本不同（当前 fpk 为 `0.2.8-1`，镜像为 `0.2.8`）。
