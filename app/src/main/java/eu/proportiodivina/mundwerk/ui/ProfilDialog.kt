package eu.proportiodivina.mundwerk.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuAnchorType
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import eu.proportiodivina.mundwerk.R
import eu.proportiodivina.mundwerk.data.ProfileDto

/**
 * Profil bearbeiten (Menü → Profil): Vorname, Nachname, Muttersprache.
 * Der Nickname ist der feste Anmeldename und wird nur angezeigt —
 * Token und Konto bleiben beim Speichern unverändert.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ProfilDialog(
    profile: ProfileDto,
    saving: Boolean,
    error: String?,
    onSave: (vorname: String, nachname: String, muttersprache: String) -> Unit,
    onClose: () -> Unit,
) {
    var vorname by remember(profile) { mutableStateOf(profile.vorname ?: "") }
    var nachname by remember(profile) { mutableStateOf(profile.nachname ?: "") }
    var sprache by remember(profile) { mutableStateOf(profile.muttersprache ?: "") }
    var dropdownOpen by remember { mutableStateOf(false) }
    val complete = vorname.isNotBlank() && nachname.isNotBlank() && sprache.isNotBlank()

    AlertDialog(
        onDismissRequest = onClose,
        confirmButton = {
            TextButton(onClick = { onSave(vorname, nachname, sprache) },
                       enabled = complete && !saving) {
                Text(stringResource(
                    if (saving) R.string.profil_speichert else R.string.profil_speichern))
            }
        },
        dismissButton = {
            TextButton(onClick = onClose) {
                Text(stringResource(R.string.profil_abbrechen))
            }
        },
        title = { Text(stringResource(R.string.profil_titel)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(stringResource(R.string.profil_nickname, profile.username),
                     style = MaterialTheme.typography.bodyMedium,
                     color = MaterialTheme.colorScheme.secondary)
                OutlinedTextField(vorname, { vorname = it }, Modifier.fillMaxWidth(),
                                  label = { Text(stringResource(R.string.profil_vorname)) },
                                  singleLine = true)
                OutlinedTextField(nachname, { nachname = it }, Modifier.fillMaxWidth(),
                                  label = { Text(stringResource(R.string.profil_nachname)) },
                                  singleLine = true)
                ExposedDropdownMenuBox(dropdownOpen, { dropdownOpen = it }) {
                    OutlinedTextField(
                        value = LANGUAGES.firstOrNull { it.first == sprache }
                            ?.let { "${it.second} (${it.first})" } ?: sprache,
                        onValueChange = {},
                        readOnly = true,
                        label = { Text(stringResource(R.string.profil_muttersprache)) },
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
                    Text(it, color = MaterialTheme.colorScheme.error)
                }
            }
        })
}
