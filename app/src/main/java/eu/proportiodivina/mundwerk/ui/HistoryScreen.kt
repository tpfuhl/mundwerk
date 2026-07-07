package eu.proportiodivina.mundwerk.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import eu.proportiodivina.mundwerk.data.ProfileDto
import eu.proportiodivina.mundwerk.data.RecordingDto
import java.time.OffsetDateTime
import java.time.format.DateTimeFormatter

private val dateFormat = DateTimeFormatter.ofPattern("dd.MM. HH:mm")

fun ratingColor(rating: String?): Color = when (rating) {
    "grün" -> Color(0xFF2E7D32)
    "gelb" -> Color(0xFFF9A825)
    "rot" -> Color(0xFFC62828)
    else -> Color.Gray
}

@Composable
fun HistoryScreen(
    loading: Boolean,
    profile: ProfileDto?,
    history: List<RecordingDto>,
    error: String?,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            OutlinedButton(onClick = onBack) { Text("← Üben") }
            Spacer(Modifier.weight(1f))
            Text("Dein Verlauf", style = MaterialTheme.typography.headlineSmall)
        }

        if (loading) {
            CircularProgressIndicator(Modifier.align(Alignment.CenterHorizontally))
            return@Column
        }
        error?.let {
            Text(it, color = MaterialTheme.colorScheme.error, textAlign = TextAlign.Center)
            return@Column
        }

        profile?.let { p ->
            Text("${p.uebungen_gesamt} Übungen insgesamt",
                 style = MaterialTheme.typography.titleMedium)
            if (p.phones.isNotEmpty()) {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp),
                           verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Row {
                            Text("Laut", Modifier.weight(1f), fontWeight = FontWeight.Bold)
                            Text("Versuche", Modifier.weight(1f), fontWeight = FontWeight.Bold)
                            Text("Ø Abstand", Modifier.weight(1f), fontWeight = FontWeight.Bold)
                            Text("Beste", Modifier.weight(1f), fontWeight = FontWeight.Bold)
                            Text("Zuletzt", Modifier.weight(1f), fontWeight = FontWeight.Bold)
                        }
                        HorizontalDivider()
                        p.phones.forEach { s ->
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text("/${s.phone}/", Modifier.weight(1f))
                                Text("${s.versuche}", Modifier.weight(1f))
                                Text("${s.mittlere_distanz}", Modifier.weight(1f))
                                Text("${s.beste_distanz}", Modifier.weight(1f))
                                Row(Modifier.weight(1f),
                                    verticalAlignment = Alignment.CenterVertically) {
                                    Spacer(Modifier
                                        .size(14.dp)
                                        .background(ratingColor(s.letztes_rating), CircleShape))
                                }
                            }
                        }
                    }
                }
            }
        }

        if (history.isNotEmpty()) {
            Text("Letzte Aufnahmen", style = MaterialTheme.typography.titleMedium)
            history.forEach { HistoryEntry(it) }
        } else if (profile != null) {
            Text("Noch keine Aufnahmen — leg los!",
                 style = MaterialTheme.typography.bodyLarge)
        }
    }
}

@Composable
private fun HistoryEntry(rec: RecordingDto) {
    val segments = rec.result?.segments.orEmpty()
    Card(Modifier.fillMaxWidth()) {
        Row(Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Spacer(Modifier
                .size(16.dp)
                .background(ratingColor(segments.firstOrNull()?.rating), CircleShape))
            Column(Modifier.weight(1f)) {
                Text(rec.item?.text ?: "?", fontWeight = FontWeight.Bold)
                segments.firstOrNull()?.let { s ->
                    Text("/${s.phone}/ · Abstand ${s.distanz ?: "–"}",
                         style = MaterialTheme.typography.bodySmall)
                }
            }
            Text(formatDate(rec.created_at),
                 style = MaterialTheme.typography.bodySmall,
                 color = MaterialTheme.colorScheme.secondary)
        }
    }
}

private fun formatDate(iso: String?): String = try {
    OffsetDateTime.parse(iso).format(dateFormat)
} catch (_: Exception) {
    ""
}
