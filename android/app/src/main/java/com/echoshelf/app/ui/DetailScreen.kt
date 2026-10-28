package com.echoshelf.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import com.echoshelf.app.AppGraph
import com.echoshelf.app.data.BookDetail
import com.echoshelf.app.ui.components.BrandButton
import com.echoshelf.app.ui.components.GlassCard
import com.echoshelf.app.ui.components.SoftDivider
import com.echoshelf.app.ui.components.coverBrush
import com.echoshelf.app.ui.theme.Brand500
import com.echoshelf.app.ui.theme.Muted
import kotlinx.coroutines.launch

@Composable
fun DetailScreen(
    graph: AppGraph,
    bookId: Int,
    onBack: () -> Unit,
    onOpenPlayer: () -> Unit,
) {
    var book by remember { mutableStateOf<BookDetail?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var playing by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(bookId) {
        runCatching { graph.book(bookId) }
            .onSuccess { book = it }
            .onFailure { error = it.message ?: "加载失败" }
    }

    fun play(fromBeginning: Boolean, position: Double? = null) {
        val detail = book ?: return
        if (playing) return
        playing = true
        error = null
        scope.launch {
            val saved = detail.progress?.positionSec ?: 0.0
            val start = position ?: when {
                fromBeginning -> 0.0
                saved > 1.0 -> saved
                else -> detail.introSec
            }
            runCatching { graph.player.play(detail, start, fromBeginning) }
                .onSuccess { onOpenPlayer() }
                .onFailure { error = it.message ?: "播放失败" }
            playing = false
        }
    }

    val detail = book
    val tracks = remember(detail) {
        var sum = 0.0
        detail?.tracks?.sortedBy { it.trackNo }?.map { track ->
            val start = sum
            sum += track.durationSec
            track to start
        } ?: emptyList()
    }

    LazyColumn(modifier = Modifier.fillMaxSize()) {
        item {
            Row(
                modifier = Modifier.fillMaxWidth().padding(start = 6.dp, top = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                TextButton(onClick = onBack) {
                    Icon(Icons.Filled.ArrowBack, contentDescription = "返回", tint = Muted)
                    Text("返回", color = Muted)
                }
            }
        }

        if (detail == null) {
            item {
                Box(Modifier.fillMaxWidth().height(360.dp), contentAlignment = Alignment.Center) {
                    if (error != null) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text(error!!, color = MaterialTheme.colorScheme.error)
                            TextButton(onClick = onBack) { Text("返回") }
                        }
                    } else {
                        CircularProgressIndicator(color = Brand500, strokeWidth = 2.dp)
                    }
                }
            }
            return@LazyColumn
        }

        item {
            Box(
                modifier = Modifier.fillMaxWidth().height(300.dp),
                contentAlignment = Alignment.Center,
            ) {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .background(
                            Brush.radialGradient(
                                listOf(Brand500.copy(alpha = 0.30f), Color.Transparent),
                            ),
                        ),
                )
                Box(
                    modifier = Modifier
                        .size(200.dp)
                        .clip(RoundedCornerShape(18.dp))
                        .background(coverBrush(detail.title)),
                ) {
                    val cover = graph.auth.absoluteUrl(detail.coverUrl)
                    if (cover != null) {
                        AuthAsyncImage(
                            url = cover,
                            contentDescription = detail.title,
                            modifier = Modifier.fillMaxSize(),
                        )
                    } else {
                        Text(
                            detail.title.take(1),
                            color = Color.White.copy(alpha = 0.9f),
                            style = MaterialTheme.typography.displayMedium,
                            modifier = Modifier.align(Alignment.Center),
                        )
                    }
                }
            }
        }

        item {
            Column(modifier = Modifier.padding(horizontal = 20.dp)) {
                Text(
                    detail.title,
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    detail.author ?: "未知作者",
                    style = MaterialTheme.typography.bodyMedium,
                    color = Muted,
                    modifier = Modifier.padding(top = 6.dp),
                )
                val series = detail.seriesName?.let { name ->
                    if (detail.seriesIndex != null) "$name · 第 ${detail.seriesIndex.toInt()} 卷" else name
                }
                if (series != null) {
                    Text(
                        series,
                        style = MaterialTheme.typography.bodySmall,
                        color = Muted,
                        modifier = Modifier.padding(top = 4.dp),
                    )
                }
                Text(
                    "${formatDuration(detail.totalDurationSec)} · ${detail.trackCount} 个音频文件",
                    style = MaterialTheme.typography.bodySmall,
                    color = Muted,
                    modifier = Modifier.padding(top = 8.dp),
                )

                val percent = detail.progress?.percent ?: 0.0
                if (percent > 0) {
                    Text(
                        "已听 ${percent.toInt()}%",
                        style = MaterialTheme.typography.bodySmall,
                        color = Brand500,
                        modifier = Modifier.padding(top = 6.dp),
                    )
                }
            }
        }

        item {
            Row(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 18.dp),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                BrandButton(
                    text = if (playing) "准备中…" else "继续收听",
                    onClick = { play(false) },
                    enabled = !playing,
                    modifier = Modifier.weight(1f),
                )
                OutlinedButton(
                    onClick = { play(true) },
                    enabled = !playing,
                    shape = RoundedCornerShape(14.dp),
                    modifier = Modifier.weight(1f).height(48.dp),
                ) {
                    Text("从头播放", color = MaterialTheme.colorScheme.onSurface, fontSize = 14.sp)
                }
            }
        }

        if (error != null) {
            item {
                Text(
                    error!!,
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(horizontal = 20.dp, vertical = 4.dp),
                )
            }
        }

        if (!detail.description.isNullOrBlank()) {
            item {
                GlassCard(modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp)) {
                    Text(
                        detail.description,
                        style = MaterialTheme.typography.bodySmall,
                        color = Muted,
                        maxLines = 5,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.padding(14.dp),
                    )
                }
            }
        }

        item {
            Text(
                "音频文件",
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.padding(start = 20.dp, top = 22.dp, bottom = 8.dp),
            )
        }

        items(tracks, key = { it.first.id }) { (track, startAt) ->
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable(enabled = !playing) { play(false, startAt) }
                    .padding(horizontal = 20.dp, vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(
                    Icons.Filled.PlayArrow,
                    contentDescription = null,
                    tint = Brand500.copy(alpha = 0.8f),
                    modifier = Modifier.size(16.dp),
                )
                Spacer(Modifier.width(10.dp))
                Text(
                    track.title.ifBlank { "第 ${track.trackNo} 段" },
                    style = MaterialTheme.typography.bodySmall,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f).padding(end = 12.dp),
                )
                Text(
                    formatDuration(track.durationSec),
                    style = MaterialTheme.typography.bodySmall,
                    color = Muted,
                )
            }
            Box(Modifier.fillMaxWidth().padding(start = 20.dp).height(1.dp).background(SoftDivider))
        }

        item { Spacer(Modifier.height(24.dp)) }
    }
}

fun formatDuration(totalSec: Double): String {
    val seconds = totalSec.toLong().coerceAtLeast(0)
    val h = seconds / 3600
    val m = (seconds % 3600) / 60
    return if (h > 0) "${h} 小时 ${m} 分" else "${m} 分"
}
