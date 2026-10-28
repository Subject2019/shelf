package com.echoshelf.app.data

import android.content.Context
import android.os.Build
import java.util.UUID

/**
 * 会话与服务器地址。用 SharedPreferences 是为了拦截器/播放器能同步读取；
 * 后续可平滑换成 EncryptedSharedPreferences（键名不变）。
 */
class AuthStore(context: Context) {
    private val prefs = context.getSharedPreferences("shelf_session", Context.MODE_PRIVATE)

    var serverUrl: String
        get() = prefs.getString(KEY_SERVER, DEFAULT_SERVER)?.trimEnd('/') ?: DEFAULT_SERVER
        set(value) {
            prefs.edit().putString(KEY_SERVER, value.trim().trimEnd('/')).apply()
        }

    val accessToken: String? get() = prefs.getString(KEY_ACCESS, null)
    val refreshToken: String? get() = prefs.getString(KEY_REFRESH, null)
    val username: String? get() = prefs.getString(KEY_USERNAME, null)
    val isLoggedIn: Boolean get() = !refreshToken.isNullOrBlank()

    val deviceId: String
        get() = prefs.getString(KEY_DEVICE, null) ?: run {
            val id = "android-" + UUID.randomUUID().toString().replace("-", "").take(12)
            prefs.edit().putString(KEY_DEVICE, id).apply()
            id
        }

    fun deviceInfo(): DeviceInfo = DeviceInfo(
        id = deviceId,
        name = "${Build.MANUFACTURER} ${Build.MODEL}".trim(),
        os = "Android ${Build.VERSION.RELEASE}",
        screen = null,
    )

    fun saveSession(response: TokenResponse) {
        prefs.edit()
            .putString(KEY_ACCESS, response.accessToken)
            .putString(KEY_REFRESH, response.refreshToken)
            .putString(KEY_USERNAME, response.user.username)
            .apply()
    }

    fun clear() {
        prefs.edit().remove(KEY_ACCESS).remove(KEY_REFRESH).remove(KEY_USERNAME).apply()
    }

    /** https://host/ → https://host/api/v1/ */
    fun apiBaseUrl(): String = serverUrl.trimEnd('/') + "/api/v1/"

    fun absoluteUrl(path: String?): String? {
        if (path.isNullOrBlank()) return null
        if (path.startsWith("http://") || path.startsWith("https://")) return path
        return serverUrl.trimEnd('/') + "/" + path.trimStart('/')
    }

    companion object {
        const val DEFAULT_SERVER = "http://192.168.31.103:8090"
        private const val KEY_SERVER = "server_url"
        private const val KEY_ACCESS = "access_token"
        private const val KEY_REFRESH = "refresh_token"
        private const val KEY_USERNAME = "username"
        private const val KEY_DEVICE = "device_id"
    }
}
