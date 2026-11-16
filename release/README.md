# release — 正式分发包（1.0.0）

存放「可以直接分发给别人」的当前版本产物，**不存源码**。目录只保留本文件、`.gitkeep` 和 `1.0.0` 产物。

## 当前产物

| 文件 | 大小 | 是什么 | 怎么用 |
|---|---:|---|---|
| `shelf-native-1.0.0-1-fnos.fpk` | 21 MB | 飞牛 **原生 x86_64 FPK**，自带 Python venv，不使用 Docker | 飞牛应用中心手动安装 |
| `shelf-native-1.0.0-1-arm-fnos.fpk` | 20 MB | 飞牛 **原生 ARM64 FPK**，复用 ARM 版 `python312`，不使用 Docker | ARM64 飞牛应用中心手动安装 |
| `shelf-1.0.0.apk` | 3.4 MB | Android WebView 壳 **release 签名**包，含离线 WebUI | `adb install -r` 或直接安装 |
| `shelf-1.0.0-linux-amd64-bare.tar.gz` | 309 KB | 常规部署包：后端源码 + 预构建前端 + `install.sh` | 解压后 `sudo ./install.sh` |
| `shelf-1.0.0-linux-amd64-docker.tar.gz` | 92 MB | 离线 Docker 镜像包，包含 `shelf:1.0.0` 与 `shelf:latest` 标签 | `docker load -i` 后运行 |
| `*.sha256` | 约 100 B | 每个包的 SHA256 | `sha256sum -c xxx.sha256` |
| `SHA256SUMS` | 约 500 B | 本版本全部产物的统一校验清单 | `sha256sum -c SHA256SUMS` |

> `release/` 只保留当前最新版本；旧版本产物不在该目录堆积。
>
> 两个飞牛原生 FPK 的应用名都是 `shelfnative`，版本号都是 `1.0.0-1`，按 CPU 架构区分，**同时保留**：
>
> - `shelf-native-1.0.0-1-fnos.fpk`：仅 x86_64，自带 venv，默认端口 `18081`；
> - `shelf-native-1.0.0-1-arm-fnos.fpk`：仅 ARM64，复用飞牛 ARM 版 `python312`，默认端口 `18081`。
>
> 1.0.0 起飞牛端不发布 Docker FPK；Docker 部署使用上面的 Docker 镜像包或 `ghcr.io/subject2019/shelf:1.0.0`。

## 1.0.0 主要变化

- Android 内置 WebUI 和本机离线 API；断网后进入本机 `127.0.0.1` 书库。
- 离线书库只显示已下载书籍；可显示章节、播放进度和书签。
- 支持整本下载，也支持按章节选择下载。
- 只要下载任意章节，书籍就出现在离线书架；未下载章节灰色不可播。
- 离线首页、搜索、书库、设置、详情页和播放页统一为 1.0.0 版 UI。
- 服务端、WebUI、Android、飞牛原生 FPK 版本统一为 `1.0.0`。

## 飞牛 FPK 安装

### 原生 x86_64

1. 飞牛应用中心选择「手动安装」；
2. 上传 `shelf-native-1.0.0-1-fnos.fpk`；
3. 安装向导填写端口、管理员账号密码和可选媒体目录；
4. 「设置 → 书库」填安装时选择的实际目录。

### 原生 ARM64

1. 确认 `uname -m` 为 `aarch64`；
2. 飞牛应用中心选择「手动安装」，上传 `shelf-native-1.0.0-1-arm-fnos.fpk`；
3. 安装向导填写端口、管理员账号密码和可选媒体目录；
4. ARM 包复用飞牛 ARM 版 `python312`，不需要 Docker。

## Android APK

```bash
sha256sum -c shelf-1.0.0.apk.sha256
adb install -r shelf-1.0.0.apk
# 或把 APK 传到手机直接安装
```

> 这是 **release 签名**包。安装过 debug 版或不同签名的旧包，需要先卸载旧 App。
>
> 该 APK 已内置离线 WebUI 和本机离线服务。联网时连接远程 shelf；断网或服务器不可达时自动进入离线书库。

## Docker 离线包

```bash
docker load -i shelf-1.0.0-linux-amd64-docker.tar.gz
docker run -d --name shelf \
  -p 8080:8080 \
  -v /path/to/audiobooks:/audiobooks:ro \
  -v /path/to/data:/data \
  shelf:1.0.0
```

镜像内同时带有 `shelf:1.0.0` 和 `shelf:latest` 两个标签。正式发布也可以直接：

```bash
docker pull ghcr.io/subject2019/shelf:1.0.0
```

## 校验

```bash
cd release
sha256sum -c *.sha256
```

## 构建说明

```bash
# WebUI + bare 包 + 同步 APK
deploy/build-release.sh --skip-web

# 原生 FPK 使用独立构建目录，构建后复制到 release/
# Docker 离线包使用当前源码构建为 shelf:1.0.0 后 docker save
```

版本号来自 `backend/app/core/config.py` 的 `APP_VERSION`。APK 版本号来自 `android-pwa/app/build.gradle`，当前为 `versionName 1.0.0`、`versionCode 20`。
