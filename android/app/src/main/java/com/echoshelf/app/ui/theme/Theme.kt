package com.echoshelf.app.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color

/** 与 Web 端 accent.ts 的 6 套主题色对齐（400/500/600 用于渐变）。 */
val BRAND_PALETTES = listOf(
    Triple(Color(0xFFF0A964), Color(0xFFE8843C), Color(0xFFC9661F)), // 暖橙
    Triple(Color(0xFF60A5FA), Color(0xFF3B82F6), Color(0xFF2563EB)), // 科技蓝
    Triple(Color(0xFFA78BFA), Color(0xFF8B5CF6), Color(0xFF6D28D9)), // 灵动手紫
    Triple(Color(0xFF34D399), Color(0xFF10B981), Color(0xFF059669)), // 翡翠绿
    Triple(Color(0xFFFB7185), Color(0xFFF43F5E), Color(0xFFE11D48)), // 玫瑰红
    Triple(Color(0xFF94A3B8), Color(0xFF64748B), Color(0xFF475569)), // 高级灰
)

/**
 * 这些颜色在 ShelfTheme 里按「主题色 / 明暗」重新赋值，全站引用处自动跟随，
 * 避免逐个改硬编码。
 */
var Brand400 = BRAND_PALETTES[0].first
var Brand500 = BRAND_PALETTES[0].second
var Brand600 = BRAND_PALETTES[0].third
var BrandGradient = Brush.linearGradient(listOf(Brand400, Brand500, Brand600))

var Ink950 = Color(0xFF0B0D10)
var Ink900 = Color(0xFF111418)
var Ink850 = Color(0xFF161A20)
var Ink800 = Color(0xFF1C2129)
var Muted = Color(0xFFA1A1AA)
var TextMain = Color(0xFFE7E5E4)

private val DarkScheme = darkColorScheme(
    primary = Brand500, onPrimary = Ink950,
    secondary = Brand400, background = Ink950, onBackground = TextMain,
    surface = Ink900, onSurface = TextMain,
    surfaceVariant = Ink850, onSurfaceVariant = Muted,
    outline = Color(0x1AFFFFFF), error = Color(0xFFF87171),
)

private val LightScheme = lightColorScheme(
    primary = Brand500, onPrimary = Color.White,
    background = Color(0xFFF7F7F8), onBackground = Color(0xFF1C2129),
    surface = Color(0xFFFFFFFF), onSurface = Color(0xFF1C2129),
    surfaceVariant = Color(0xFFEDEEF1), onSurfaceVariant = Color(0xFF64748B),
    outline = Color(0x1A000000), error = Color(0xFFDC2626),
)

@Composable
fun ShelfTheme(
    mode: String = "dark",
    brandIndex: Int = 0,
    content: @Composable () -> Unit,
) {
    val p = BRAND_PALETTES[brandIndex.coerceIn(0, BRAND_PALETTES.lastIndex)]
    Brand400 = p.first; Brand500 = p.second; Brand600 = p.third
    BrandGradient = Brush.linearGradient(listOf(Brand400, Brand500, Brand600))

    val dark = mode != "light"
    if (dark) {
        Ink950 = Color(0xFF0B0D10); Ink900 = Color(0xFF111418); Ink850 = Color(0xFF161A20)
        Ink800 = Color(0xFF1C2129); Muted = Color(0xFFA1A1AA); TextMain = Color(0xFFE7E5E4)
    } else {
        Ink950 = Color(0xFFF7F7F8); Ink900 = Color(0xFFFFFFFF); Ink850 = Color(0xFFEDEEF1)
        Ink800 = Color(0xFFE4E7EC); Muted = Color(0xFF64748B); TextMain = Color(0xFF1C2129)
    }

    MaterialTheme(
        colorScheme = if (dark) DarkScheme else LightScheme,
        typography = Typography(),
        content = content,
    )
}
