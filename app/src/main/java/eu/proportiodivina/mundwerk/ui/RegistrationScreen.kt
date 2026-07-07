package eu.proportiodivina.mundwerk.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuAnchorType
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp

// Muttersprachen zur Auswahl: ISO-639-1-Code → Anzeigename.
// Bewusst kuratierte Liste der häufigsten Ausgangssprachen; erweiterbar.
private val LANGUAGES = listOf(
    "en" to "Englisch", "fr" to "Französisch", "it" to "Italienisch",
    "es" to "Spanisch", "pt" to "Portugiesisch", "pl" to "Polnisch",
    "ru" to "Russisch", "uk" to "Ukrainisch", "tr" to "Türkisch",
    "ar" to "Arabisch", "fa" to "Persisch", "zh" to "Chinesisch",
    "ja" to "Japanisch", "ko" to "Koreanisch", "vi" to "Vietnamesisch",
    "hi" to "Hindi", "nl" to "Niederländisch", "el" to "Griechisch",
    "cs" to "Tschechisch", "hu" to "Ungarisch", "ro" to "Rumänisch",
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RegistrationScreen(
    registering: Boolean,
    error: String?,
    onRegister: (vorname: String, nachname: String, nickname: String,
                 muttersprache: String) -> Unit,
    modifier: Modifier = Modifier,
) {
    var vorname by rememberSaveable { mutableStateOf("") }
    var nachname by rememberSaveable { mutableStateOf("") }
    var nickname by rememberSaveable { mutableStateOf("") }
    var sprache by rememberSaveable { mutableStateOf("") }
    var dropdownOpen by remember { mutableStateOf(false) }

    val complete = vorname.isNotBlank() && nachname.isNotBlank() &&
            nickname.isNotBlank() && sprache.isNotBlank()

    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text("Mundwerk", style = MaterialTheme.typography.headlineMedium)
        Text("Willkommen! Leg dein Profil an, um loszulegen.",
             style = MaterialTheme.typography.bodyLarge,
             textAlign = TextAlign.Center)
        Spacer(Modifier.height(8.dp))

        OutlinedTextField(vorname, { vorname = it }, Modifier.fillMaxWidth(),
                          label = { Text("Vorname") }, singleLine = true)
        OutlinedTextField(nachname, { nachname = it }, Modifier.fillMaxWidth(),
                          label = { Text("Nachname") }, singleLine = true)
        OutlinedTextField(nickname, { nickname = it }, Modifier.fillMaxWidth(),
                          label = { Text("Nickname (Anmeldename)") }, singleLine = true)

        ExposedDropdownMenuBox(dropdownOpen, { dropdownOpen = it }) {
            OutlinedTextField(
                value = LANGUAGES.firstOrNull { it.first == sprache }
                    ?.let { "${it.second} (${it.first})" } ?: "",
                onValueChange = {},
                readOnly = true,
                label = { Text("Muttersprache") },
                trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(dropdownOpen) },
                modifier = Modifier
                    .menuAnchor(ExposedDropdownMenuAnchorType.PrimaryNotEditable)
                    .fillMaxWidth(),
            )
            ExposedDropdownMenu(dropdownOpen, { dropdownOpen = false }) {
                LANGUAGES.forEach { (code, name) ->
                    DropdownMenuItem(
                        text = { Text("$name ($code)") },
                        onClick = { sprache = code; dropdownOpen = false },
                    )
                }
            }
        }

        error?.let {
            Text(it, color = MaterialTheme.colorScheme.error, textAlign = TextAlign.Center)
        }

        Button(
            onClick = { onRegister(vorname, nachname, nickname, sprache) },
            enabled = complete && !registering,
            modifier = Modifier.fillMaxWidth().height(56.dp),
        ) {
            if (registering) {
                CircularProgressIndicator(Modifier.size(24.dp))
                Spacer(Modifier.size(12.dp))
                Text("Registriere …")
            } else {
                Text("Profil anlegen")
            }
        }
    }
}
