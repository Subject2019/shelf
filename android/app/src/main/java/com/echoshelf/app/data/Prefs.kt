package com.echoshelf.app.data

import android.content.Context
import android.content.SharedPreferences
import com.echoshelf.app.ShelfApp

/**
 * 本地偏好（主题、播放偏好）。用 SharedPreferences，键名与 Web 端 localStorage 对齐，
 * 方便将来统一行为。
 */
object Prefs {
    private val prefs: SharedPreferences
        get() = ShelfApp.instance.getSharedPreferences("shelf_prefs", Context.MODE_PRIVATE)

    // —— 外观：明暗 + 主题色（0..5） ——
    var themeMode: String
        get() = prefs.getString("theme_mode", "dark") ?: "dark"
        set(v) = prefs.edit().putString("theme_mode", v).apply()

    var brandIndex: Int
        get() = prefs.getInt("brand_index", 0).coerceIn(0, 5)
        set(v) = prefs.edit().putInt("brand_index", v.coerceIn(0, 5)).apply()

    // —— 播放偏好（与 Web player.ts 对齐） ——
    var skipIntro: Boolean
        get() = prefs.getBoolean("skip_intro", true)
        set(v) = prefs.edit().putBoolean("skip_intro", v).apply()

    var skipOutro: Boolean
        get() = prefs.getBoolean("skip_outro", true)
        set(v) = prefs.edit().putBoolean("skip_outro", v).apply()

    var autoNext: Boolean
        get() = prefs.getBoolean("auto_next", true)
        set(v) = prefs.edit().putBoolean("auto_next", v).apply()

    var defaultRate: Float
        get() = prefs.getFloat("default_rate", 1f)
        set(v) = prefs.edit().putFloat("default_rate", v).apply()
}
