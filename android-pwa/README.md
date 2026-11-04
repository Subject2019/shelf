# android-pwa — Android WebView 壳

**状态：0.2.10（2026-11-05，本地修复版）**。包名 `com.shelf.pwa`，minSdk 24 / targetSdk 35，AGP 8.5.2 + Gradle 8.7 + Media3 1.3.1 + Java 17。

不内置 WebUI：启动后加载服务器上的 shelf 网页，界面、登录、书库全部复用 WebUI。音频播放由原生 Media3 前台服务接管，因此支持后台播放、状态栏/锁屏媒体控制和息屏续播。

原生层负责两个不依赖 WebView 前台状态的能力：

- 定时关闭在 `PlaybackService` 中计时并渐隐/暂停，熄屏或 WebView 被冻结时仍然生效；WebUI 只负责设置和显示倒计时。
- 通过 `MediaButtonReceiver` 和 `MediaSession.Callback.onMediaButtonEvent` 接收蓝牙/车机的 `MEDIA_NEXT` / `MEDIA_PREVIOUS`；通知栏、系统媒体卡片、车机和网页统一收敛到章节感知的切集逻辑，单文件多章节按章节边界跳转，多文件无章节才切 MediaItem。
- 通知栏媒体按钮只保留“上一集 / 播放暂停 / 下一集”三个，快退/快进 15 秒不再显示；系统媒体卡片的 `COMMAND_SEEK_BACK/FORWARD` 也从可用命令中移除。

## 结构

```
app/src/main/java/com/shelf/pwa/
├── SetupActivity.java        首次启动填写并校验服务器地址（/api/v1/health）
├── MainActivity.java         WebView、状态栏安全区、ShelfPlayer JS 桥、通知权限
└── player/
    ├── PlaybackService.java  MediaSessionService + ExoPlayer + 媒体通知
    ├── NativePlayer.java     MediaController：播放列表、片头片尾、状态回传
    ├── ProgressReporter.java 原生 15s 进度上报 + 暂停/划掉补报 + token 更新
    └── ProgressStore.java    上报失败时的本地待补传进度
```

网页侧配合：

- `web/src/lib/nativePlayer.ts`：检测 `window.ShelfPlayer`，定义桥和状态类型。
- `web/src/store/player.ts`：有原生桥时把整本书播放列表交给原生；播放态每 500ms 回传，进度由原生 `PlaybackService` 直接上报。

## 构建

要求 JDK 17+、Android SDK 35。`local.properties` 由 Android Studio 生成（`sdk.dir=...`），不要提交。

```bash
cd android-pwa
./gradlew assembleRelease
# 产物：app/build/outputs/apk/release/app-release.apk
```

首次构建需要联网下载 Gradle 8.7、AGP 与 Media3；之后可离线构建。release 签名读取本地 `keystore.properties` + `release.keystore`（均在 `.gitignore` 中），缺失时输出未签名包。**签名密钥务必备份，丢失后无法覆盖升级已安装的 App。**

## 安装与连接

1. 安装 APK，允许未知来源。
2. 首次启动填写服务器地址，例如 `http://192.168.1.10:8080`；开发环境可填 Vite：`http://192.168.1.10:5173`。
   - 设置页会请求 `/api/v1/health` 校验，必须是 shelf 服务端。
3. Android 13+ 首次启动会申请 `POST_NOTIFICATIONS`，必须允许；否则前台服务仍在播放，但状态栏/锁屏不会出现媒体卡片。
4. 进入后长按页面 →「更改服务器」可重新配置。

## 播放与通知

- 整本书的播放列表一次性交给原生；ExoPlayer 按「每个音频文件」用 `ClippingConfiguration` 跳片头/片尾。
- 媒体通知/锁屏按钮顺序：上一集、快退 15 秒、播放/暂停、快进 15 秒、下一集。
  - 五个动作都使用标准 `playerCommand`，由系统媒体卡片排布；具体间距和分组因 ROM 而异。
  - 播放/暂停图标随播放态更新。
- 封面：网页抓取封面后以 base64 传给原生，写入 `MediaMetadata.artworkData`，避免系统加载 HTTP 封面失败。
- 进度条：对系统暴露当前音轨的真实 `duration` 与当前项 seek 命令，状态栏/锁屏媒体卡片显示可拖动的单集进度条；具体样式和位置由 ROM 决定。
- 音量：系统媒体卡片不支持滑杆，使用 App 内音量条或手机音量键；音量变化会回传网页同步。
- 进度：播放中每 15 秒由原生服务直接 `PUT /progress`；暂停、seek、切轨、播放结束、从最近任务划掉、服务销毁时都会补报。不再依赖 WebView 的 15 秒定时器，因此划掉 App 后继续播放也会持续同步。
- token：网页把当前 access token 注入原生服务；token 只保存在服务内存里，不落盘。上报失败时最新位置写入本地 `ProgressStore`，下次打开同一本书会自动补传，并在恢复播放时优先采用本地较新的位置。
- 媒体通知点击可回到 App；从最近任务划掉不会停止播放，进度会由前台播放服务继续上报。

## 前端耦合（重要）

壳只提供 `window.ShelfPlayer` 桥，**网页必须调用它才会走原生播放**。如果服务器上的 `web/dist` 是旧版本（不含 `nativePlayer.ts` 适配层），网页仍使用 `<audio>`，不会出现媒体卡片。

更新顺序：

1. 构建/部署最新 `web/`（Docker 镜像或静态 `dist`）；
2. 安装最新 APK；
3. 打开 App 确认加载的是新前端。

开发时用 Vite `5173` 最方便；生产环境必须重建镜像，不能只替换 APK。

## 桥接口

`ShelfPlayer`（由 `MainActivity.PlayerBridge` 注入）：

| 方法 | 说明 |
|---|---|
| `play(payloadJson)` | 整本书播放列表、起始位置、倍速、封面 |
| `pause()` / `resume()` | 暂停 / 继续 |
| `seekTo(absoluteSec)` | 按全书绝对秒数定位 |
| `seekToTrack(index, positionInTrackSec)` | 按轨内秒数定位 |
| `setRate(rate)` | 倍速 |
| `setVolume(0..1)` | App 播放音量 |
| `next()` / `previous()` | 上下集（标准媒体命令） |
| `stop()` | 停止并清空 |

原生 → 网页：`window.__shelfPlayer.onState(json)`，每 500ms 回传 `playing / buffering / trackIndex / positionSec / rate / volume / error`。

## 排查

- **没有媒体卡片/封面**：检查通知权限；确认 App 版本 0.2.10；确认前端包含 `ShelfPlayer` 适配层和进度上下文（开发 5173 或重建后的生产镜像）。
- **状态栏有播放但按钮少**：Android 通知栏收起时最多显示 3 个动作，展开后才是完整 5 个；锁屏卡片由系统渲染，部分 ROM 会重排。
- **图标被裁切**：自适应图标前景已限制在安全区；卸载重装或重启启动器/清除启动器缓存。
- **播放失败**：看 logcat 标签 `ShelfNativePlayer`；确认 `stream_url` 可访问、token 未过期。
- **进度不上报/划掉后台后少一段**：看 logcat 标签 `ShelfProgress`；确认服务端网页已包含进度上下文（新 `web/dist`），旧前端不会调用 `setAuth`/发送 `bookId/baseUrl`。HTTP 401 表示 access token 过期，重开 App 注入新 token 后会补传本地 pending。
- **改了 IP/端口**：长按页面 →「更改服务器」；设置页会重新校验 `/api/v1/health`。

## 已知限制

- 原生播放列表默认自动连播；网页的「自动连播」开关目前不会阻止原生队列继续下一集。
- 流令牌有效期 6 小时；超长单集跨令牌过期需要重新打开/刷新。
- 系统媒体卡片的布局、进度条样式、按钮分组由 ROM 决定；App 已暴露当前音轨时长和 seek 命令，但部分 ROM 仍可能不渲染进度条。
- access token 有效期为 30 分钟。若 WebView 已被销毁、token 又已过期，原生服务无法自行续期；此时进度会先保存在本地，等重新打开 App 注入新 token 后补传。跨设备立即看到最后一段进度仍受这个限制。
- 未内置离线下载；未打包 WebUI。
