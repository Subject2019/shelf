package com.echoshelf.app.ui

import androidx.activity.compose.BackHandler
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import com.echoshelf.app.AppGraph
import com.echoshelf.app.ui.components.PauseBars
import com.echoshelf.app.ui.components.coverBrush
import com.echoshelf.app.ui.theme.Brand500
import com.echoshelf.app.ui.theme.BrandGradient
import com.echoshelf.app.ui.theme.Ink950
import com.echoshelf.app.ui.theme.Muted

@Composable
fun PlayerScreen(graph: AppGraph, onBack: () -> Unit) {
    BackHandler { onBack() }
    val state by graph.player.state.collectAsState()
    var dragging by remember { mutableStateOf(false) }
    var dragValue by remember { mutableStateOf(0f) }

    val duration = state.durationSec.toFloat().coerceAtLeast(1f)
    val position = if (dragging) dragValue else state.positionSec.toFloat().coerceIn(0f, duration)

    Column(
        modifier = Modifier.fillMaxSize().padding(horizontal = 24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(top = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            TextButton(onClick = onBack) {
                Icon(Icons.Filled.ArrowBack, contentDescription = "收起", tint = Muted)
                Text("收起", color = Muted)
            }
        }

        Spacer(Modifier.weight(0.35f))

        Box(
            modifier = Modifier
                .size(250.dp)
                .shadow(28.dp, RoundedCornerShape(22.dp))
                .clip(RoundedCornerShape(22.dp))
                .background(coverBrush(state.subtitle.ifBlank { state.title })),
            contentAlignment = Alignment.Center,
        ) {
            if (state.coverUrl != null) {
                AuthAsyncImage(
                    url = state.coverUrl,
                    contentDescription = state.title,
                    modifier = Modifier.fillMaxSize(),
                )
            } else {
                Text(
                    state.title.take(1),
                    style = MaterialTheme.typography.displayLarge,
                    color = Color.White.copy(alpha = 0.9f),
                )
            }
        }

        Spacer(Modifier.height(28.dp))

        Text(
            state.title.ifBlank { "未在播放" },
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.SemiBold,
            textAlign = TextAlign.Center,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
        )
        Text(
            state.subtitle,
            style = MaterialTheme.typography.bodyMedium,
            color = Muted,
            textAlign = TextAlign.Center,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.padding(top = 6.dp),
        )

        Spacer(Modifier.height(24.dp))

        Slider(
            value = position,
            onValueChange = {
                dragging = true
                dragValue = it
            },
            onValueChangeFinished = {
                dragging = false
                graph.player.seekTo(dragValue.toDouble())
            },
            valueRange = 0f..duration,
            colors = SliderDefaults.colors(
                thumbColor = Brand500,
                activeTrackColor = Brand500,
                inactiveTrackColor = Color.White.copy(alpha = 0.14f),
            ),
            modifier = Modifier.fillMaxWidth(),
        )
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Text(formatClock(position.toDouble()), style = MaterialTheme.typography.bodySmall, color = Muted)
            Text(
                if (state.buffering) "缓冲中…" else formatClock(duration.toDouble()),
                style = MaterialTheme.typography.bodySmall,
                color = Muted,
            )
        }

        Spacer(Modifier.height(22.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceEvenly,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            CircleText("−30") { graph.player.skip(-30.0) }
            Box(
                modifier = Modifier
                    .size(74.dp)
                    .clip(CircleShape)
                    .background(BrandGradient)
                    .clickable { graph.player.toggle() },
                contentAlignment = Alignment.Center,
            ) {
                if (state.playing) {
                    PauseBars(color = Ink950, modifier = Modifier.size(30.dp))
                } else {
                    Icon(
                        imageVector = Icons.Filled.PlayArrow,
                        contentDescription = "播放",
                        tint = Ink950,
                        modifier = Modifier.size(34.dp),
                    )
                }
            }
            CircleText("+30") { graph.player.skip(30.0) }
        }

        Spacer(Modifier.height(18.dp))

        TextButton(onClick = {
            val rates = listOf(1f, 1.25f, 1.5f, 1.75f, 2f, 0.75f)
            val next = rates.firstOrNull { it > state.rate + 0.01f } ?: rates.first()
            graph.player.setRate(next)
        }) {
            Text("倍速 ${state.rate}×", color = Brand500)
        }

        Spacer(Modifier.weight(0.6f))
    }
}

@Composable
private fun CircleText(label: String, onClick: () -> Unit) {
    Box(
        modifier = Modifier
            .size(54.dp)
            .clip(CircleShape)
            .background(Color.White.copy(alpha = 0.06f))
            .clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Text(label, style = MaterialTheme.typography.labelMedium, color = Color.White.copy(alpha = 0.85f), fontSize = 12.sp)
    }
}

private fun formatClock(totalSec: Double): String {
    val seconds = totalSec.toLong().coerceAtLeast(0)
    val h = seconds / 3600
    val m = (seconds % 3600) / 60
    val s = seconds % 60
    return if (h > 0) "%d:%02d:%02d".format(h, m, s) else "%d:%02d".format(m, s)
}
