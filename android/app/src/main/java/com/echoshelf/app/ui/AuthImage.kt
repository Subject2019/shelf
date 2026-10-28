package com.echoshelf.app.ui

import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import coil.compose.AsyncImage
import coil.request.ImageRequest
import com.echoshelf.app.ShelfApp

/**
 * 带鉴权头的封面图：后端封面接口需要 Bearer，Coil 默认请求不带，
 * 因此在 ImageRequest 上附加 Authorization 头（URL 仍作为缓存键）。
 */
@Composable
fun AuthAsyncImage(
    url: String?,
    contentDescription: String?,
    modifier: Modifier = Modifier.fillMaxSize(),
    contentScale: ContentScale = ContentScale.Crop,
) {
    if (url == null) return
    val context = LocalContext.current
    val token = (context.applicationContext as? ShelfApp)?.graph?.auth?.accessToken
    val request = ImageRequest.Builder(context).data(url)
    if (!token.isNullOrBlank()) {
        request.setHeader("Authorization", "Bearer $token")
    }
    AsyncImage(
        model = request.crossfade(true).build(),
        contentDescription = contentDescription,
        contentScale = contentScale,
        modifier = modifier,
    )
}
