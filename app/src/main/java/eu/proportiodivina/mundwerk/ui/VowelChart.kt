package eu.proportiodivina.mundwerk.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.dp
import eu.proportiodivina.mundwerk.data.TargetDto

/**
 * Vokalviereck: F1/F2-Raum in phonetischer Konvention — Zunge vorn =
 * links (hohes F2), Mund geschlossen = oben (niedriges F1). Zeigt alle
 * Referenzvokale, hebt den Ziellaut samt 1-SD-Zielzone hervor und
 * markiert die eigene Produktion mit Verbindungslinie zum Ziel.
 */
@Composable
fun VowelChart(
    targets: List<TargetDto>,
    focusPhone: String,
    measuredF1: Double?,
    measuredF2: Double?,
    measuredColor: Color,
    modifier: Modifier = Modifier,
) {
    if (targets.isEmpty()) return
    val textMeasurer = rememberTextMeasurer()
    val labelStyle: TextStyle = MaterialTheme.typography.labelSmall
        .copy(color = MaterialTheme.colorScheme.onSurfaceVariant)
    val focusStyle = labelStyle.copy(fontWeight = FontWeight.Bold,
                                     color = MaterialTheme.colorScheme.primary)
    val frameColor = MaterialTheme.colorScheme.outlineVariant
    val refColor = MaterialTheme.colorScheme.onSurfaceVariant
    val focusColor = MaterialTheme.colorScheme.primary

    Column(modifier = modifier.fillMaxWidth(),
           verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Canvas(Modifier.fillMaxWidth().height(240.dp)) {
            val f1all = targets.map { it.f1_mean } + listOfNotNull(measuredF1)
            val f2all = targets.map { it.f2_mean } + listOfNotNull(measuredF2)
            val f1pad = (f1all.max() - f1all.min()) * 0.18 + 1
            val f2pad = (f2all.max() - f2all.min()) * 0.12 + 1
            val f1min = f1all.min() - f1pad
            val f1max = f1all.max() + f1pad
            val f2min = f2all.min() - f2pad
            val f2max = f2all.max() + f2pad

            fun x(f2: Double) = ((f2max - f2) / (f2max - f2min) * size.width).toFloat()
            fun y(f1: Double) = ((f1 - f1min) / (f1max - f1min) * size.height).toFloat()
            val sx = size.width / (f2max - f2min).toFloat()   // px pro Hz (F2)
            val sy = size.height / (f1max - f1min).toFloat()  // px pro Hz (F1)

            drawRect(frameColor, style = Stroke(1.dp.toPx()))

            val focus = targets.firstOrNull { it.phone == focusPhone }

            targets.forEach { t ->
                val c = Offset(x(t.f2_mean), y(t.f1_mean))
                if (t.phone == focusPhone) {
                    // 1-SD-Zielzone als Ellipse
                    val rw = (t.f2_sd * sx).toFloat()
                    val rh = (t.f1_sd * sy).toFloat()
                    drawOval(focusColor.copy(alpha = 0.15f),
                             topLeft = Offset(c.x - rw, c.y - rh),
                             size = Size(rw * 2, rh * 2))
                    drawCircle(focusColor, 5.dp.toPx(), c,
                               style = Stroke(2.dp.toPx()))
                } else {
                    drawCircle(refColor, 3.dp.toPx(), c)
                }
                drawText(textMeasurer, t.phone,
                         topLeft = c + Offset(5.dp.toPx(), -18.dp.toPx()),
                         style = if (t.phone == focusPhone) focusStyle else labelStyle)
            }

            if (measuredF1 != null && measuredF2 != null) {
                val m = Offset(x(measuredF2), y(measuredF1))
                focus?.let {
                    drawLine(measuredColor, m,
                             Offset(x(it.f2_mean), y(it.f1_mean)),
                             strokeWidth = 2.dp.toPx(),
                             pathEffect = PathEffect.dashPathEffect(
                                 floatArrayOf(8f, 8f)))
                }
                drawCircle(measuredColor, 7.dp.toPx(), m)
                drawCircle(Color.White, 3.dp.toPx(), m)
            }
        }
        Row(Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween) {
            Text("← Zunge vorn", style = labelStyle)
            Text("oben = Mund geschlossen", style = labelStyle)
            Text("Zunge hinten →", style = labelStyle)
        }
    }
}
