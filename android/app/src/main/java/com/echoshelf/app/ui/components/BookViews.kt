package com.echoshelf.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.echoshelf.app.data.Book
import com.echoshelf.app.ui.AuthAsyncImage
import com.echoshelf.app.ui.theme.Brand500
import com.echoshelf.app.ui.theme.Ink900
import com.echoshelf.app.ui.theme.Muted
import com.echoshelf.app.ui.theme.TextMain

/** 书架/首页/搜索共用的书卡：1:1 封面 + 不透明信息层 + 进度条 + 状态角标。 */
@Composable
fun BookCard(
    book: Book,
    coverUrl: String?,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val percent = book.progress?.percent ?: 0.0
    val finished = book.progress?.isFinished == true

    Column(
        modifier = modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .aspectRatio(1f)
                .clip(RoundedCornerShape(12.dp))
                .background(coverBrush(book.title)),
        ) {
            if (coverUrl != null) {
                AuthAsyncImage(
                    url = coverUrl,
                    contentDescription = book.title,
                    modifier = Modifier.fillMaxSize(),
                )
            } else {
                Text(
                    text = book.title.take(1),
                    color = TextMain,
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.headlineMedium,
                    modifier = Modifier.align(Alignment.Center),
                )
            }

            // 底部压暗渐变，保证标题可读
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(
                        Brush.verticalGradient(
                            0f to Color.Transparent,
                            1f to Ink900.copy(alpha = 0.78f),
                        ),
                    ),
            )

            Column(
                Modifier
                    .align(Alignment.BottomStart)
                    .fillMaxWidth()
                    .padding(8.dp),
            ) {
                Text(
                    text = book.title,
                    color = TextMain,
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    Text(
                        text = (book.author ?: "").ifBlank { "未知作者" },
                        color = Muted,
                        style = MaterialTheme.typography.labelSmall,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.weight(1f, fill = false),
                    )
                    if (book.trackCount > 0) {
                        Text(
                            text = "${book.trackCount} 轨",
                            color = Muted,
                            style = MaterialTheme.typography.labelSmall,
                        )
                    }
                }
            }

            if (finished) {
                StatusBadge("已听完")
            } else if (percent > 0) {
                StatusBadge("在听")
            }
        }

        Box(
            Modifier
                .padding(top = 6.dp)
                .fillMaxWidth()
                .height(3.dp)
                .clip(RoundedCornerShape(2.dp))
                .background(Ink900),
        ) {
            Box(
                Modifier
                    .fillMaxWidth(fraction = percent.toFloat().coerceIn(0f, 1f))
                    .height(3.dp)
                    .background(Brand500),
            )
        }
    }
}

@Composable
private fun BoxScope.StatusBadge(text: String) {
    Box(
        Modifier
            .align(Alignment.TopEnd)
            .padding(6.dp)
            .clip(RoundedCornerShape(6.dp))
            .background(Brand500)
            .padding(horizontal = 6.dp, vertical = 2.dp),
    ) {
        Text(
            text = text,
            color = Ink900,
            style = MaterialTheme.typography.labelSmall,
            fontWeight = FontWeight.SemiBold,
        )
    }
}
