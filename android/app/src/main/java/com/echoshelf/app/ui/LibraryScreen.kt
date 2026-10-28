package com.echoshelf.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.echoshelf.app.AppGraph
import com.echoshelf.app.data.Book
import com.echoshelf.app.ui.components.BookCard
import com.echoshelf.app.ui.components.ScreenHeader
import com.echoshelf.app.ui.theme.Ink900
import com.echoshelf.app.ui.theme.Muted
import com.echoshelf.app.ui.theme.TextMain

private enum class SortMode(val label: String) {
    Recent("最近"), Title("书名"), Author("作者"), Duration("时长")
}
private enum class StatusFilter(val label: String) {
    All("全部"), Progress("在听"), Finished("已听完"), Unstarted("未开始")
}

@Composable
fun LibraryScreen(
    graph: AppGraph,
    onOpenBook: (Int) -> Unit,
) {
    var all by remember { mutableStateOf<List<Book>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var query by remember { mutableStateOf("") }
    var sort by remember { mutableStateOf(SortMode.Recent) }
    var status by remember { mutableStateOf(StatusFilter.All) }

    LaunchedEffect(Unit) {
        runCatching { graph.books(force = true) }.onSuccess { all = it }
        loading = false
    }

    val q = query.trim().lowercase()
    val filtered = all
        .filter { b ->
            q.isBlank() ||
                b.title.lowercase().contains(q) ||
                (b.author ?: "").lowercase().contains(q) ||
                (b.seriesName ?: "").lowercase().contains(q)
        }
        .filter { b ->
            when (status) {
                StatusFilter.All -> true
                StatusFilter.Finished -> b.progress?.isFinished == true
                StatusFilter.Progress -> (b.progress?.percent ?: 0.0) > 0 && b.progress?.isFinished != true
                StatusFilter.Unstarted -> (b.progress?.percent ?: 0.0) == 0.0
            }
        }
        .let { list ->
            when (sort) {
                SortMode.Title -> list.sortedBy { it.title }
                SortMode.Author -> list.sortedBy { it.author }
                SortMode.Duration -> list.sortedByDescending { it.totalDurationSec }
                SortMode.Recent -> list
            }
        }

    Column(Modifier.fillMaxSize()) {
        ScreenHeader("书库", subtitle = if (loading) "加载中…" else "${all.size} 本")
        Spacer(Modifier.height(8.dp))

        // 搜索框
        TextField(
            value = query,
            onValueChange = { query = it },
            placeholder = { Text("搜索书名 / 作者 / 系列", color = Muted) },
            singleLine = true,
            leadingIcon = { Icon(Icons.Filled.Search, contentDescription = null, tint = Muted) },
            modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp).clip(RoundedCornerShape(14.dp)),
            colors = TextFieldDefaults.colors(
                unfocusedContainerColor = Ink900, focusedContainerColor = Ink900,
                unfocusedTextColor = TextMain, focusedTextColor = TextMain,
                unfocusedIndicatorColor = Color.Transparent, focusedIndicatorColor = Color.Transparent,
                cursorColor = Muted,
            ),
        )
        Spacer(Modifier.height(8.dp))

        // 状态筛选
        Row(
            Modifier.fillMaxWidth().padding(horizontal = 16.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            StatusFilter.entries.forEach { s ->
                Pill(text = s.label, active = status == s) { status = s }
            }
        }
        Spacer(Modifier.height(8.dp))

        // 排序
        Row(
            Modifier.fillMaxWidth().padding(horizontal = 16.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            SortMode.entries.forEach { m ->
                Pill(text = m.label, active = sort == m) { sort = m }
            }
        }
        Spacer(Modifier.height(10.dp))

        LazyVerticalGrid(
            columns = GridCells.Fixed(2),
            modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp),
            contentPadding = PaddingValues(bottom = 16.dp),
        ) {
            items(filtered, key = { it.id }) { book ->
                val cover = graph.auth.absoluteUrl(book.coverUrl)
                BookCard(book = book, coverUrl = cover, onClick = { onOpenBook(book.id) }, modifier = Modifier.padding(6.dp))
            }
        }
    }
}

@Composable
private fun Pill(text: String, active: Boolean, onClick: () -> Unit) {
    Box(
        modifier = Modifier
            .clip(RoundedCornerShape(50))
            .background(if (active) com.echoshelf.app.ui.theme.Brand500 else Ink900)
            .clickable(onClick = onClick)
            .padding(horizontal = 14.dp, vertical = 6.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text,
            color = if (active) com.echoshelf.app.ui.theme.Ink950 else Muted,
            style = MaterialTheme.typography.labelSmall,
        )
    }
}
