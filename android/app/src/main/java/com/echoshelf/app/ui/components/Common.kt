package com.echoshelf.app.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.echoshelf.app.ui.theme.Brand400
import com.echoshelf.app.ui.theme.Brand500
import com.echoshelf.app.ui.theme.Brand600
import com.echoshelf.app.ui.theme.BrandGradient
import com.echoshelf.app.ui.theme.Ink950

/** 固定背景光晕，和 Web 的三团光斑同色系。 */
@Composable
fun GlowBackground() {
    Canvas(modifier = Modifier.fillMaxSize()) {
        val w = size.width
        val h = size.height
        fun blob(cx: Float, cy: Float, radius: Float, color: Color, alpha: Float) {
            drawCircle(
                brush = Brush.radialGradient(
                    0f to color.copy(alpha = alpha),
                    0.55f to color.copy(alpha = alpha * 0.32f),
                    1f to Color.Transparent,
                    center = Offset(cx, cy),
                    radius = radius,
                ),
                radius = radius,
                center = Offset(cx, cy),
            )
        }
        blob(-w * 0.1f, -h * 0.02f, w * 1.0f, Brand500, 0.34f)
        blob(w * 1.05f, h * 0.16f, w * 0.8f, Color(0xFF6366F1), 0.18f)
        blob(w * 0.3f, h * 1.02f, w * 0.9f, Color(0xFFEC4899), 0.12f)
    }
}

@Composable
fun GlassCard(
    modifier: Modifier = Modifier,
    shape: RoundedCornerShape = RoundedCornerShape(16.dp),
    content: @Composable () -> Unit,
) {
    Surface(
        modifier = modifier,
        shape = shape,
        color = Color.White.copy(alpha = 0.055f),
        border = BorderStroke(1.dp, Color.White.copy(alpha = 0.10f)),
        content = content,
    )
}

@Composable
fun BrandButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
) {
    Box(
        modifier = modifier
            .height(48.dp)
            .clip(RoundedCornerShape(14.dp))
            .background(
                if (enabled) {
                    BrandGradient
                } else {
                    Brush.linearGradient(
                        listOf(
                            Brand400.copy(alpha = 0.35f),
                            Brand500.copy(alpha = 0.35f),
                            Brand600.copy(alpha = 0.35f),
                        ),
                    )
                },
            )
            .clickable(enabled = enabled, onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text,
            color = Ink950,
            style = MaterialTheme.typography.labelLarge,
            fontWeight = FontWeight.SemiBold,
        )
    }
}

/** 无封面时按书名生成稳定渐变，和 Web 的 Cover 组件思路一致。 */
fun coverBrush(title: String): Brush {
    val hue = ((title.hashCode() % 360) + 360) % 360
    val a = Color.hsl(hue.toFloat(), 0.42f, 0.42f)
    val b = Color.hsl(((hue + 38) % 360).toFloat(), 0.55f, 0.28f)
    return Brush.linearGradient(listOf(a, b))
}

val SoftDivider = Color(0x14FFFFFF)
val CardBorder = Color(0x1AFFFFFF)
val ChipBg = Color(0x14FFFFFF)


/** material-icons-core 里没有 Pause，画两根圆角竖条。 */
@Composable
fun PauseBars(color: Color, modifier: Modifier = Modifier) {
    Row(modifier = modifier, horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(4.dp)) {
        Box(Modifier.width(4.dp).height(18.dp).clip(CircleShape).background(color))
        Box(Modifier.width(4.dp).height(18.dp).clip(CircleShape).background(color))
    }
}
