# android — 安卓 App

**状态：首版可编译（2026-10-26）**。技术栈 Kotlin + Jetpack Compose + Media3 + Retrofit + kotlinx.serialization。
首版为了先跑通，**暂未引入 Hilt / Room**（手写 `AppGraph` + SharedPreferences），离线下载落地时再补 Room。

## 工程参数（M5-T01 按此创建）

| 项 | 值 |
|---|---|
| Gradle | 8.7+，Kotlin DSL（`build.gradle.kts`） |
| AGP / Kotlin | 8.5+ / 2.0+（K2） |
| compileSdk / targetSdk / minSdk | 35 / 35 / 26（Android 8.0，覆盖 98%+） |
| JDK | 17 |
| 包名 | `com.echoshelf.app` |

核心依赖：`androidx.media3:media3-exoplayer`、`media3-session`、`media3-ui-compose`、
`compose-bom`、`hilt-android` + `hilt-navigation-compose`、`retrofit2` + `okhttp` + `kotlinx-serialization`、
`androidx.room`、`coil-compose`、`androidx.datastore`、`androidx.work`。

## 包结构

```
app/src/main/java/com/echoshelf/app/
├── EchoShelfApp.kt          @HiltAndroidApp
├── MainActivity.kt          @AndroidEntryPoint，setContent { AppNavHost() }
├── data/
│   ├── api/                 EchoShelfApi（Retrofit 接口）、AuthInterceptor、TokenAuthenticator
│   ├── dto/                 与 docs/API.md 对齐
│   ├── repo/                BookRepository、ProgressRepository、DownloadRepository
│   └── prefs/               EncryptedSharedPreferences（token）、DataStore（设置）
├── database/                Room：DownloadedTrackEntity、PendingProgressEntity、BookCacheEntity + DAO
├── player/
│   ├── PlaybackService.kt   MediaSessionService + ExoPlayer，前台通知
│   ├── PlaybackController.kt 句柄封装，供 Compose 观察状态
│   └── ProgressSyncer.kt    15s 节流上报 + 离线队列冲刷
├── di/                      NetworkModule、DatabaseModule、PlayerModule
└── ui/
    ├── login/  library/  detail/  player/  downloads/  settings/
    └── theme/               Material3 深色主题
```

## 关键实现约束

1. **后台播放必须用 `MediaSessionService`**，不要用 Activity 持有 ExoPlayer。前台服务通知渠道
   `playback`（低优先级、常驻），`onTaskRemoved` 不要 stopSelf。
2. **播放数据源优先级**：本地下载文件 → 服务端 `/stream`（带 Range）。使用 `DefaultHttpDataSource`
   并透传 `Authorization` 头（`MediaItem` 无法直接带自定义头时用 `ResolvingDataSource`）。
3. **进度**：本地先写 Room（`PendingProgressEntity`，含 `clientUpdatedAt`、`explicitSeek`），
   `ProgressSyncer` 每 15s 或网络恢复时批量 `PUT`，**以响应值回写本地**（ADR-0002）。
4. **离线下载**：WorkManager 唯一任务队列（`uniqueName = "book-$id"`），支持断点续传（OkHttp Range），
   文件存 `filesDir/books/{bookId}/{trackId}.{ext}`，Room 记录状态，删除时同步清文件。
5. **明文 HTTP**：`res/xml/network_security_config.xml` 仅允许私网段明文，公网域名强制 HTTPS：
   ```xml
   <domain-config cleartextTrafficPermitted="true">
     <domain includeSubdomains="false">192.168.0.0/16</domain>  <!-- 只能写具体域名/IP，见实现说明 -->
   </domain-config>
   ```
   实际写法：`<base-config cleartextTrafficPermitted="true">` 仅用于 debug 变体；
   release 变体要求用户填 HTTPS 地址，或在设置里显式打开「允许局域网明文」。
6. **国产 ROM 保活**：设置页提供「后台运行指引」（自启动、电池优化白名单）。

## 首版已实现（2026-10-26）

| 模块 | 内容 |
|---|---|
| 登录 | 服务器地址 + 账号密码；token 存 SharedPreferences；401 自动用 refresh token 换新并重放 |
| 书架 | 网格 + 封面（Coil）+ 作者 + 阅读进度条 |
| 详情 | 封面/简介/系列卷号/音频文件列表；「继续收听」按服务端进度 + `intro_sec` 起播 |
| 播放 | Media3 `MediaSessionService` 后台播放、通知栏控制、倍速、±30s、拖动进度 |
| 进度 | 播放中每 15s 上报、暂停/拖动立即上报；`PUT /progress/{id}` 带 `device_id` |
| 设置 | 服务器/账号/设备 ID、退出登录、国产 ROM 保活提示 |

未做（下一步）：按章节离线下载（`docs/CLIENT_DOWNLOAD.md`）、Room 队列、系列/作者聚合页、
播放偏好持久化、release 签名与 AAB、真机验证。

## 构建（本机已验证）

> 所有工具（Android SDK / Gradle / pip / npm / 模型缓存）统一放在仓库外的 `/vol5/1000/vscode_server/workspace/toolchain/`：`android/`（sdk、gradle-8.7、gradle-home、avd）、`pip/`、`npm/`、`models/`。`source ../toolchain-env.sh` 可一次性导出所有环境变量。

工具链**不在仓库里**，统一放在工作区同级目录：

```
/vol5/1000/vscode_server/workspace/toolchain/android/
├── sdk/              # Android SDK（platform 35 / build-tools 35.0.0 / platform-tools）
├── gradle-8.7/       # Gradle 发行版
├── gradle-home/      # GRADLE_USER_HOME（依赖缓存，可随时删）
├── avd/              # 模拟器 AVD（需要时再建）
└── downloads/        # 安装包（可删）
```

```bash
export JAVA_HOME=/vol1/@appcenter/java-21-openjdk
export GRADLE_USER_HOME=/vol5/1000/vscode_server/workspace/toolchain/android/gradle-home
export ANDROID_AVD_HOME=/vol5/1000/vscode_server/workspace/toolchain/android/avd
cd android
/vol5/1000/vscode_server/workspace/toolchain/android/gradle-8.7/bin/gradle --no-daemon assembleDebug
# 产物 app/build/outputs/apk/debug/app-debug.apk（13 MB，debug 签名）
```

`local.properties` 已指向 `toolchain/android/sdk`（该文件被 gitignore）。

## 构建

```bash
cd android
./gradlew assembleDebug        # app/build/outputs/apk/debug/app-debug.apk
./gradlew bundleRelease        # AAB（需配置 signingConfigs，密钥不入库）
```

服务器地址在登录页输入（`https://books.example.com` 或 `http://192.168.1.10:8080`），
不做硬编码，便于一套 APK 服务多台 NAS。
