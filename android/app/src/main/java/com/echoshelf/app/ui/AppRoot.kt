package com.echoshelf.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.echoshelf.app.AppGraph
import com.echoshelf.app.data.Prefs
import com.echoshelf.app.ui.components.BottomNav
import com.echoshelf.app.ui.components.GlowBackground
import com.echoshelf.app.ui.components.MiniPlayer
import com.echoshelf.app.ui.theme.Ink950
import com.echoshelf.app.ui.theme.ShelfTheme

sealed interface Screen {
    data object Login : Screen
    data object Home : Screen
    data object Library : Screen
    data object Search : Screen
    data object Settings : Screen
    data class Detail(val bookId: Int) : Screen
    data object Player : Screen
}

@Composable
fun AppRoot(graph: AppGraph) {
    val playerState by graph.player.state.collectAsState()

    var screen by remember { mutableStateOf<Screen>(if (graph.auth.isLoggedIn) Screen.Home else Screen.Login) }
    var returnScreen by remember { mutableStateOf<Screen>(Screen.Library) }
    var themeNonce by remember { mutableStateOf(0) }

    val mode = remember(themeNonce) { Prefs.themeMode }
    val brand = remember(themeNonce) { Prefs.brandIndex }

    ShelfTheme(mode, brand) {
        Box(Modifier.fillMaxSize().background(Ink950)) {
            GlowBackground()

            Column(Modifier.fillMaxSize()) {
                Box(Modifier.weight(1f).fillMaxWidth()) {
                    when (val s = screen) {
                        is Screen.Login -> LoginScreen(
                            graph = graph,
                            onLoggedIn = { screen = Screen.Home },
                        )
                        is Screen.Home -> HomeScreen(
                            graph = graph,
                            onOpenBook = { id -> returnScreen = Screen.Home; screen = Screen.Detail(id) },
                            onOpenPlayer = { screen = Screen.Player },
                            onBrowseLibrary = { screen = Screen.Library },
                        )
                        is Screen.Library -> LibraryScreen(
                            graph = graph,
                            onOpenBook = { id -> returnScreen = Screen.Library; screen = Screen.Detail(id) },
                        )
                        is Screen.Search -> SearchScreen(
                            graph = graph,
                            onOpenBook = { id -> returnScreen = Screen.Search; screen = Screen.Detail(id) },
                        )
                        is Screen.Detail -> DetailScreen(
                            graph = graph,
                            bookId = s.bookId,
                            onBack = { screen = returnScreen },
                            onOpenPlayer = { screen = Screen.Player },
                        )
                        is Screen.Player -> PlayerScreen(
                            graph = graph,
                            onBack = { screen = returnScreen },
                        )
                        is Screen.Settings -> SettingsScreen(
                            graph = graph,
                            onLogout = { screen = Screen.Login },
                            onAppearanceChanged = { themeNonce++ },
                        )
                    }
                }

                // 悬浮迷你播放条（全屏播放时不显示）
                if (playerState.bookId != null && screen !is Screen.Player) {
                    MiniPlayer(graph = graph, onOpenPlayer = { screen = Screen.Player })
                }

                // 底部 5 项导航（仅主界面显示）
                if (screen is Screen.Home || screen is Screen.Library ||
                    screen is Screen.Search || screen is Screen.Settings
                ) {
                    val current = when (screen) {
                        Screen.Home -> "home"
                        Screen.Library -> "library"
                        Screen.Search -> "search"
                        else -> "settings"
                    }
                    BottomNav(
                        current = current,
                        hasPlayer = playerState.bookId != null,
                        onHome = { screen = Screen.Home },
                        onLibrary = { screen = Screen.Library },
                        onPlayer = { screen = Screen.Player },
                        onSearch = { screen = Screen.Search },
                        onSettings = { screen = Screen.Settings },
                    )
                }
            }
        }
    }
}
