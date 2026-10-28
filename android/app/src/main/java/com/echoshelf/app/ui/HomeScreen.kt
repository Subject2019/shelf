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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.echoshelf.app.AppGraph
import com.echoshelf.app.data.Book
import com.echoshelf.app.ui.components.BookCard
import com.echoshelf.app.ui.components.BrandButton
import com.echoshelf.app.ui.components.GlassCard
import com.echoshelf.app.ui.theme.Brand500
import com.echoshelf.app.ui.theme.Muted
import com.echoshelf.app.ui.theme.TextMain

@Composable
fun HomeScreen(
    graph: AppGraph,
    onOpenBook: (Int) -> Unit,
    onOpenPlayer: () -> Unit,
    onBrowseLibrary: () -> Unit,
) {
    var books by remember { mutableStateOf<List<Book>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }

    LaunchedEffect(Unit) {
        runCatching { graph.books() }.onSuccess { books = it }
        loading = false
    }

    val recent = books.take(12)

    LazyVerticalGrid(
        columns = GridCells.Fixed(2),
        modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp),
    ) {
        item(span = { GridItemSpan(2) }) {
            Spacer(Modifier.height(16.dp))
            GlassCard(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(20.dp)) {
                    Text(
                        "shelf",
                        style = MaterialTheme.typography.headlineLarge,
                        color = TextMain,
                        fontWeight = FontWeight.Bold,
                    )
                    Text("你的私人有声书库 · 手机移动版", style = MaterialTheme.typography.bodyMedium, color = Muted)
                    Spacer(Modifier.height(16.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        BrandButton("浏览书库", onClick = onBrowseLibrary, modifier = Modifier.weight(1f))
                        Box(
                            Modifier
                                .weight(1f)
                                .height(48.dp)
                                .clip(RoundedCornerShape(14.dp))
                                .background(Brand500.copy(alpha = 0.16f))
                                .clickable(onClick = onOpenPlayer),
                            contentAlignment = Alignment.Center,
                        ) {
                            Text("继续收听", color = Brand500, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.SemiBold)
                        }
                    }
                }
            }
        }

        item(span = { GridItemSpan(2) }) {
            Spacer(Modifier.height(14.dp))
            GlassCard(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp)) {
                    Text("服务状态", style = MaterialTheme.typography.titleMedium, color = TextMain, fontWeight = FontWeight.SemiBold)
                    Spacer(Modifier.height(8.dp))
                    StatusRow("连接", graph.auth.serverUrl)
                    StatusRow("书库", if (loading) "加载中…" else "${books.size} 本")
                    StatusRow("版本", "0.1.0")
                }
            }
        }

        item(span = { GridItemSpan(2) }) {
            Spacer(Modifier.height(22.dp))
            Text("最近添加", style = MaterialTheme.typography.titleLarge, color = TextMain, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(10.dp))
        }

        items(recent, key = { it.id }) { book ->
            val cover = graph.auth.absoluteUrl(book.coverUrl)
            BookCard(book = book, coverUrl = cover, onClick = { onOpenBook(book.id) }, modifier = Modifier.padding(6.dp))
        }

        item(span = { GridItemSpan(2) }) { Spacer(Modifier.height(24.dp)) }
    }
}

@Composable
private fun StatusRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 3.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(label, color = Muted, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.width(64.dp))
        Text(value, color = TextMain, style = MaterialTheme.typography.bodyMedium)
    }
}
