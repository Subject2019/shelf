package com.echoshelf.app.player

import androidx.media3.datasource.DefaultHttpDataSource
import androidx.media3.datasource.HttpDataSource
import com.echoshelf.app.data.AuthStore

/**
 * 给 Media3 的流请求动态注入 Authorization 头。
 * 后端以 Bearer 鉴权（无独立 play-token 接口），每次创建数据源时读取最新 token。
 */
class BearerHttpDataSourceFactory(private val auth: AuthStore) : HttpDataSource.Factory {
    private val base = DefaultHttpDataSource.Factory()

    override fun createDataSource(): HttpDataSource {
        val token = auth.accessToken
        if (!token.isNullOrBlank()) {
            base.setDefaultRequestProperties(mapOf("Authorization" to "Bearer $token"))
        }
        return base.createDataSource()
    }

    override fun setDefaultRequestProperties(
        defaultRequestProperties: Map<String, String>,
    ): HttpDataSource.Factory {
        base.setDefaultRequestProperties(defaultRequestProperties)
        return this
    }
}
