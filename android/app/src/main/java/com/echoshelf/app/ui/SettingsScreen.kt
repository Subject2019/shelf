package com.echoshelf.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.echoshelf.app.AppGraph
import kotlinx.coroutines.launch
import com.echoshelf.app.data.Prefs
import com.echoshelf.app.ui.components.BrandButton
import com.echoshelf.app.ui.components.GlassCard
import com.echoshelf.app.ui.components.ScreenHeader
import com.echoshelf.app.ui.theme.BRAND_PALETTES
import com.echoshelf.app.ui.theme.Brand500
import com.echoshelf.app.ui.theme.Ink950
import com.echoshelf.app.ui.theme.Muted
import com.echoshelf.app.ui.theme.TextMain

private val SPEEDS = listOf(0.75f, 1f, 1.25f, 1.5f, 2f)

@Composable
fun SettingsScreen(
    graph: AppGraph,
    onLogout: () -> Unit,
    onAppearanceChanged: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    Column(
        Modifier
            .fillMaxSize()
            .padding(horizontal = 16.dp)
            .padding(bottom = 16.dp),
    ) {
        ScreenHeader("设置")
        Spacer(Modifier.height(12.dp))

        // —— 外观 ——
        SectionTitle("外观")
        GlassCard(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp)) {
                Text("深浅模式", color = TextMain, style = MaterialTheme.typography.bodyMedium)
                Spacer(Modifier.height(10.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Pill("深色", Prefs.themeMode != "light") { Prefs.themeMode = "dark"; onAppearanceChanged() }
                    Pill("浅色", Prefs.themeMode == "light") { Prefs.themeMode = "light"; onAppearanceChanged() }
                }
                Spacer(Modifier.height(16.dp))
                Text("主题色", color = TextMain, style = MaterialTheme.typography.bodyMedium)
                Spacer(Modifier.height(10.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                    BRAND_PALETTES.forEachIndexed { i, palette ->
                        Box(
                            Modifier
                                .size(34.dp)
                                .clip(CircleShape)
                                .background(palette.second)
                                .then(
                                    if (Prefs.brandIndex == i) {
                                        Modifier.border(2.dp, TextMain, CircleShape)
                                    } else {
                                        Modifier
                                    },
                                )
                                .clickable {
                                    Prefs.brandIndex = i
                                    onAppearanceChanged()
                                },
                        )
                    }
                }
            }
        }

        Spacer(Modifier.height(16.dp))

        // —— 播放偏好 ——
        SectionTitle("播放偏好")
        GlassCard(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp)) {
                Text("默认倍速", color = TextMain, style = MaterialTheme.typography.bodyMedium)
                Spacer(Modifier.height(10.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    SPEEDS.forEach { r ->
                        Pill("${if (r == 1f) "1.0" else r}×", Prefs.defaultRate == r) {
                            Prefs.defaultRate = r
                        }
                    }
                }
                Spacer(Modifier.height(16.dp))
                ToggleRow("跳过片头", Prefs.skipIntro) { Prefs.skipIntro = it }
                ToggleRow("跳过片尾", Prefs.skipOutro) { Prefs.skipOutro = it }
                ToggleRow("自动连播", Prefs.autoNext) { Prefs.autoNext = it }
            }
        }

        Spacer(Modifier.height(16.dp))

        // —— 账号 ——
        SectionTitle("账号")
        GlassCard(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp)) {
                InfoRow("服务器", graph.auth.serverUrl)
                InfoRow("用户名", graph.auth.username ?: "-")
                InfoRow("设备 ID", graph.auth.deviceId)
            }
        }

        Spacer(Modifier.height(16.dp))

        // —— 服务 ——
        SectionTitle("服务")
        GlassCard(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp)) {
                InfoRow("版本", "0.1.0")
                InfoRow("状态", "已连接")
            }
        }

        Spacer(Modifier.height(20.dp))
        BrandButton("退出登录", onClick = { scope.launch { graph.logout() } }, modifier = Modifier.fillMaxWidth())
    }
}

@Composable
private fun SectionTitle(text: String) {
    Text(
        text,
        color = Muted,
        style = MaterialTheme.typography.labelLarge,
        fontWeight = FontWeight.SemiBold,
        modifier = Modifier.padding(horizontal = 4.dp, vertical = 4.dp),
    )
}

@Composable
private fun ToggleRow(label: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(
        Modifier.fillMaxWidth().padding(vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(label, color = TextMain, style = MaterialTheme.typography.bodyMedium)
        Switch(checked = checked, onCheckedChange = onChange)
    }
}

@Composable
private fun InfoRow(label: String, value: String) {
    Row(
        Modifier.fillMaxWidth().padding(vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(label, color = Muted, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
        Text(value, color = TextMain, style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
private fun Pill(text: String, active: Boolean, onClick: () -> Unit) {
    Box(
        modifier = Modifier
            .clip(CircleShape)
            .background(if (active) Brand500 else Color.White.copy(alpha = 0.06f))
            .clickable(onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 8.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text,
            color = if (active) Ink950 else Muted,
            style = MaterialTheme.typography.labelMedium,
            fontWeight = FontWeight.SemiBold,
        )
    }
}
