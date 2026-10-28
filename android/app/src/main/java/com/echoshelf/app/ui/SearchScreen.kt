package com.echoshelf.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
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
import com.echoshelf.app.ui.theme.Ink900
import com.echoshelf.app.ui.theme.Muted
import com.echoshelf.app.ui.theme.TextMain

@Composable
fun SearchScreen(
    graph: AppGraph,
    onOpenBook: (Int) -> Unit,
) {
    var all by remember { mutableStateOf<List<Book>>(emptyList()) }
    var query by remember { mutableStateOf("") }

    LaunchedEffect(Unit) {
        runCatching { graph.books() }.onSuccess { all = it }
    }

    val q = query.trim().lowercase()
    val results = if (q.isBlank()) {
        all
    } else {
        all.filter {
            it.title.lowercase().contains(q) ||
                (it.author ?: "").lowercase().contains(q) ||
                (it.seriesName ?: "").lowercase().contains(q)
        }
    }

    Column(Modifier.fillMaxSize().padding(horizontal = 16.dp)) {
        Spacer(Modifier.fillMaxWidth().padding(top = 16.dp))
        TextField(
            value = query,
            onValueChange = { query = it },
            placeholder = { Text("搜索书名、作者、系列…", color = Muted) },
            singleLine = true,
            leadingIcon = { Icon(Icons.Filled.Search, contentDescription = null, tint = Muted) },
            modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)),
            colors = TextFieldDefaults.colors(
                unfocusedContainerColor = Ink900,
                focusedContainerColor = Ink900,
                unfocusedTextColor = TextMain,
                focusedTextColor = TextMain,
                unfocusedIndicatorColor = Color.Transparent,
                focusedIndicatorColor = Color.Transparent,
                cursorColor = Muted,
            ),
        )

        Spacer(Modifier.height(12.dp))
        Text(
            if (q.isBlank()) "全部 ${all.size} 本" else "找到 ${results.size} 本",
            color = Muted,
            style = MaterialTheme.typography.bodySmall,
        )
        Spacer(Modifier.height(8.dp))

        LazyVerticalGrid(
            columns = GridCells.Fixed(2),
            modifier = Modifier.fillMaxSize(),
        ) {
            items(results, key = { it.id }) { book ->
                val cover = graph.auth.absoluteUrl(book.coverUrl)
                BookCard(book = book, coverUrl = cover, onClick = { onOpenBook(book.id) }, modifier = Modifier.padding(6.dp))
            }
            item { Box(Modifier.fillMaxWidth().padding(vertical = 16.dp)) { Text("", modifier = Modifier) } }
        }
    }
}
