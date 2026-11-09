# release — 分发包输出目录

存放「可以直接分发给别人」的最新构建产物，**不存源码**。目录本身只保留本文件、`.gitkeep` 和当前版本产物。

## 当前产物

| 文件 | 当前大小 | 是什么 | 怎么用 |
|---|---|---|---|
| `shelf-native-0.2.12-1-fnos.fpk` | 21 MB | 飞牛 **原生部署版（x86_64）** fpk，自带 Python venv，不使用 Docker | 飞牛应用中心手动安装 |
| `shelf-native-0.2.12-1-arm-fnos.fpk` | 20 MB | 飞牛 **原生部署版（ARM64）** fpk，复用 ARM 版 `python312`，不使用 Docker | ARM64 飞牛应用中心手动安装 |
| `shelf-0.2.12.apk` | 3.1 MB | Android WebView 壳 **release 签名**包 | `adb install -r` 或直接安装 |
| `shelf-0.2.12-linux-amd64-bare.tar.gz` | 304 KB | 常规部署包：后端源码 + 预构建前端 + `install.sh` | 解压后 `sudo ./install.sh` |
| `*.sha256` | 约 100 B | 上面每个包的校验值 | `sha256sum -c xxx.sha256` |

> `release/` 只保留当前最新版本；旧版本 fpk/APK 不在这里堆积。
>
> 两个飞牛原生 fpk 使用同一个版本号 `0.2.12-1`，按 CPU 架构区分，**同时保留**：
>
> - `shelf-native-0.2.12-1-fnos.fpk`：应用名 `shelfnative`，依赖 `python312`，复用系统 `ffmpeg`，默认端口 `18081`，仅 x86_64；
> - `shelf-native-0.2.12-1-arm-fnos.fpk`：应用名 `shelfnative`，依赖 ARM 版 `python312`，复用系统 `ffmpeg`，默认端口 `18081`，仅 ARM64。
>
> 0.2.12 起飞牛端不再发布 Docker FPK；Docker 部署请直接使用镜像 `ghcr.io/subject2019/shelf:0.2.12`。

## 飞牛 fpk 安装

原生 x86_64 版：

1. 飞牛应用中心选择「手动安装」；
2. 上传 `shelf-native-0.2.12-1-fnos.fpk`；
3. 安装向导填写端口、管理员账号密码和可选媒体目录；
4. 「设置 → 书库」填安装时选择的实际目录，例如 `/vol1/@appshare/shelfnative/media`，不要填 `/audiobooks`。

原生 ARM64 版：

1. 确认 `uname -m` 为 `aarch64`；
2. 飞牛应用中心选择「手动安装」，上传 `shelf-native-0.2.12-1-arm-fnos.fpk`；
3. 安装向导填写端口、管理员账号密码和可选媒体目录；
4. ARM 包复用飞牛 ARM 版 `python312`，不需要 Docker，也不要使用 Docker 版 fpk。

## Android APK 怎么用

```bash
sha256sum -c shelf-0.2.12.apk.sha256
adb install -r shelf-0.2.12.apk
# 或把 APK 传到手机直接安装
```

> 这是 **release 签名**包。之前安装过 debug 版的设备签名不一致，需要先卸载旧 App 再安装。

## 怎么生成

```bash
# 常规部署包（会先构建前端）
deploy/build-release.sh

# 只打包、复用已有 web/dist
deploy/build-release.sh --skip-web

# 原生版 fpk 使用独立构建目录，产物复制到 release/
# 0.2.12 起飞牛 Release 不再发布 Docker FPK；Docker 部署直接使用镜像
```

脚本会自动把 `android-pwa/app/build/outputs/apk/release/app-release.apk` 复制为 `shelf-<版本>.apk` 并生成校验；如果 APK 不存在则跳过。release 签名读取本地 `android-pwa/keystore.properties` 与 `release.keystore`（均不提交），请务必备份密钥。

版本号来自 `backend/app/core/config.py` 的 `APP_VERSION`，架构取 `uname -m`（amd64 / arm64）。

## 常规包结构

```text
shelf-0.2.12-linux-amd64/
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
