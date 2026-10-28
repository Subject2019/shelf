package com.echoshelf.app.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class DeviceInfo(
    val id: String,
    val name: String,
    val platform: String = "android",
    @SerialName("app_version") val appVersion: String = "0.1.0",
    val os: String = "Android",
    @SerialName("form_factor") val formFactor: String = "phone",
    val screen: String? = null,
    @SerialName("user_agent") val userAgent: String? = null,
)

@Serializable
data class LoginRequest(
    val username: String,
    val password: String,
    val device: DeviceInfo? = null,
)

@Serializable
data class RefreshRequest(@SerialName("refresh_token") val refreshToken: String)

@Serializable
data class UserDto(
    val id: Int,
    val username: String,
    @SerialName("display_name") val displayName: String? = null,
    val role: String,
    val libraries: List<Int> = emptyList(),
)

@Serializable
data class TokenResponse(
    @SerialName("access_token") val accessToken: String,
    @SerialName("refresh_token") val refreshToken: String,
    @SerialName("expires_in") val expiresIn: Int = 1800,
    val user: UserDto,
)

@Serializable
data class ProgressDto(
    @SerialName("position_sec") val positionSec: Double = 0.0,
    val percent: Double = 0.0,
    @SerialName("is_finished") val isFinished: Boolean = false,
)

@Serializable
data class Book(
    val id: Int,
    val title: String,
    val author: String? = null,
    @SerialName("series_name") val seriesName: String? = null,
    @SerialName("series_index") val seriesIndex: Double? = null,
    @SerialName("cover_url") val coverUrl: String? = null,
    @SerialName("total_duration_sec") val totalDurationSec: Double = 0.0,
    @SerialName("track_count") val trackCount: Int = 0,
    val progress: ProgressDto? = null,
)

@Serializable
data class BookList(
    val items: List<Book> = emptyList(),
    val total: Int = 0,
    val page: Int = 1,
    @SerialName("page_size") val pageSize: Int = 50,
)

@Serializable
data class Track(
    val id: Int,
    @SerialName("track_no") val trackNo: Int = 1,
    val title: String = "",
    @SerialName("duration_sec") val durationSec: Double = 0.0,
    val format: String? = null,
    @SerialName("stream_url") val streamUrl: String = "",
)

@Serializable
data class Chapter(
    val id: Int,
    val idx: Int,
    val title: String = "",
    @SerialName("start_sec") val startSec: Double = 0.0,
    @SerialName("end_sec") val endSec: Double = 0.0,
    @SerialName("track_id") val trackId: Int = 0,
)

@Serializable
data class BookDetail(
    val id: Int,
    val title: String,
    val author: String? = null,
    @SerialName("series_name") val seriesName: String? = null,
    @SerialName("series_index") val seriesIndex: Double? = null,
    val description: String? = null,
    @SerialName("cover_url") val coverUrl: String? = null,
    @SerialName("total_duration_sec") val totalDurationSec: Double = 0.0,
    @SerialName("intro_sec") val introSec: Double = 0.0,
    @SerialName("outro_sec") val outroSec: Double = 0.0,
    @SerialName("track_count") val trackCount: Int = 0,
    val tracks: List<Track> = emptyList(),
    val chapters: List<Chapter> = emptyList(),
    val progress: ProgressDto? = null,
)

@Serializable
data class PlayToken(
    val token: String,
    @SerialName("expires_in") val expiresIn: Int = 21600,
    @SerialName("expires_at") val expiresAt: Long = 0,
)

@Serializable
data class ProgressPut(
    @SerialName("position_sec") val positionSec: Double,
    @SerialName("playback_rate") val playbackRate: Double = 1.0,
    @SerialName("device_id") val deviceId: String,
    @SerialName("client_updated_at") val clientUpdatedAt: Long,
    @SerialName("explicit_seek") val explicitSeek: Boolean = false,
    val finished: Boolean = false,
    @SerialName("track_id") val trackId: Int? = null,
)

@Serializable
data class ProgressResult(
    @SerialName("book_id") val bookId: Int,
    @SerialName("position_sec") val positionSec: Double,
    @SerialName("track_id") val trackId: Int? = null,
    val accepted: Boolean = true,
    @SerialName("is_finished") val isFinished: Boolean = false,
    @SerialName("updated_at") val updatedAt: Long = 0,
)

@Serializable
data class ApiErrorBody(val error: ApiErrorDetail? = null)

@Serializable
data class ApiErrorDetail(val code: String = "", val message: String = "")
