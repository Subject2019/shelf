package com.echoshelf.app

import android.content.Context
import androidx.media3.datasource.HttpDataSource
import com.echoshelf.app.data.ApiErrorBody
import com.echoshelf.app.data.AuthStore
import com.echoshelf.app.data.Book
import com.echoshelf.app.data.BookDetail
import com.echoshelf.app.data.EchoShelfApi
import com.echoshelf.app.data.LoginRequest
import com.echoshelf.app.data.ProgressPut
import com.echoshelf.app.data.ProgressResult
import com.echoshelf.app.data.RefreshRequest
import com.echoshelf.app.data.TokenResponse
import com.echoshelf.app.player.BearerHttpDataSourceFactory
import com.echoshelf.app.player.PlayerController
import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import okhttp3.Authenticator
import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import okhttp3.Route
import retrofit2.HttpException
import retrofit2.Retrofit
import java.util.concurrent.TimeUnit

class ApiException(message: String) : Exception(message)

/** 手写依赖图：M5 第一版先不引入 Hilt/Room，减少构建变量；后续可平滑替换。 */
class AppGraph(context: Context) {
    private val appContext = context.applicationContext
    val auth = AuthStore(appContext)
    val json = Json { ignoreUnknownKeys = true }

    private val bareClient = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()

    private val client: OkHttpClient = bareClient.newBuilder()
        .addInterceptor(AuthInterceptor(auth))
        .authenticator(TokenAuthenticator(auth, bareClient, json))
        .build()

    /** 流媒体数据源：动态注入 Authorization 头（后端以 Bearer 鉴权，无独立 play-token 接口）。 */
    val httpDataSourceFactory: HttpDataSource.Factory = BearerHttpDataSourceFactory(auth)

    @Volatile
    private var api: EchoShelfApi = createApi()

    val player = PlayerController(appContext, this)

    private fun createApi(): EchoShelfApi = Retrofit.Builder()
        .baseUrl(auth.apiBaseUrl())
        .client(client)
        .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
        .build()
        .create(EchoShelfApi::class.java)

    private fun currentApi(): EchoShelfApi = api

    private fun rebuildApi(): EchoShelfApi {
        val built = createApi()
        api = built
        return built
    }

    private suspend fun <T> call(block: suspend (EchoShelfApi) -> T): T {
        try {
            return block(currentApi())
        } catch (error: HttpException) {
            throw ApiException(parseError(error))
        }
    }

    private fun parseError(error: HttpException): String {
        val raw = runCatching { error.response()?.errorBody()?.string() }.getOrNull()
        val parsed = raw?.let { runCatching { json.decodeFromString<ApiErrorBody>(it) }.getOrNull() }
        return parsed?.error?.message?.takeIf { it.isNotBlank() }
            ?: "请求失败（HTTP ${error.code()}）"
    }

    suspend fun login(server: String, username: String, password: String): TokenResponse {
        auth.serverUrl = server
        rebuildApi()
        val response = call { api ->
            api.login(LoginRequest(username, password, auth.deviceInfo()))
        }
        auth.saveSession(response)
        return response
    }

    suspend fun logout() {
        val refresh = auth.refreshToken
        if (refresh != null) {
            runCatching { call { it.logout(RefreshRequest(refresh)) } }
        }
        auth.clear()
    }

    private var booksCache: List<Book>? = null

    /** 书库列表（带内存缓存，首页/书架/搜索共用）。 */
    suspend fun books(force: Boolean = false): List<Book> {
        if (!force && booksCache != null) return booksCache!!
        val list = call { it.books() }.items
        booksCache = list
        return list
    }

    suspend fun book(id: Int): BookDetail = call { it.book(id) }

    suspend fun putProgress(
        bookId: Int,
        positionSec: Double,
        rate: Double,
        finished: Boolean = false,
        explicitSeek: Boolean = false,
        trackId: Int? = null,
    ): ProgressResult = call { api ->
        api.putProgress(
            bookId,
            ProgressPut(
                positionSec = positionSec,
                playbackRate = rate,
                deviceId = auth.deviceId,
                clientUpdatedAt = System.currentTimeMillis() / 1000,
                explicitSeek = explicitSeek,
                finished = finished,
                trackId = trackId,
            ),
        )
    }
}

private class AuthInterceptor(private val auth: AuthStore) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val token = auth.accessToken
        val request = if (token.isNullOrBlank()) {
            chain.request()
        } else {
            chain.request().newBuilder().header("Authorization", "Bearer $token").build()
        }
        return chain.proceed(request)
    }
}

private class TokenAuthenticator(
    private val auth: AuthStore,
    private val bareClient: OkHttpClient,
    private val json: Json,
) : Authenticator {
    override fun authenticate(route: Route?, response: Response): Request? {
        if (response.request.header("Authorization") == null) return null
        synchronized(this) {
            val failedToken = response.request.header("Authorization")?.removePrefix("Bearer ")
            val latest = auth.accessToken
            if (!latest.isNullOrBlank() && latest != failedToken) {
                return response.request.newBuilder()
                    .header("Authorization", "Bearer $latest")
                    .build()
            }
            val refresh = auth.refreshToken ?: return null
            val body = json.encodeToString(RefreshRequest(refresh))
                .toRequestBody("application/json".toMediaType())
            val request = Request.Builder()
                .url(auth.apiBaseUrl() + "auth/refresh")
                .post(body)
                .build()
            val token = runCatching {
                bareClient.newCall(request).execute().use { refreshResponse ->
                    if (!refreshResponse.isSuccessful) return null
                    val parsed = json.decodeFromString<TokenResponse>(refreshResponse.body!!.string())
                    auth.saveSession(parsed)
                    parsed.accessToken
                }
            }.getOrNull() ?: run {
                auth.clear()
                null
            } ?: return null
            return response.request.newBuilder()
                .header("Authorization", "Bearer $token")
                .build()
        }
    }
}
