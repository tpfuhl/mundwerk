package eu.proportiodivina.mundwerk

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.IconButton
import androidx.compose.material3.TextButton
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuAnchorType
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.viewmodel.compose.viewModel
import eu.proportiodivina.mundwerk.data.SegmentResultDto
import eu.proportiodivina.mundwerk.data.TargetDto
import eu.proportiodivina.mundwerk.ui.HistoryScreen
import eu.proportiodivina.mundwerk.ui.ProfilDialog
import eu.proportiodivina.mundwerk.ui.VowelChart
import eu.proportiodivina.mundwerk.ui.RegistrationScreen
import eu.proportiodivina.mundwerk.ui.ratingColor
import eu.proportiodivina.mundwerk.ui.theme.MundwerkTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            MundwerkTheme {
                Scaffold(modifier = Modifier.fillMaxSize()) { innerPadding ->
                    PracticeScreen(modifier = Modifier.padding(innerPadding))
                }
            }
        }
    }
}

@Composable
fun PracticeScreen(modifier: Modifier = Modifier, vm: MundwerkViewModel = viewModel()) {
    val state by vm.state.collectAsState()
    val context = LocalContext.current
    val micPermission = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted -> if (granted) vm.toggleRecording() }
    var dialog by remember { mutableStateOf<String?>(null) }

    when (dialog) {
        "hilfe" -> HilfeDialog(onClose = { dialog = null })
        "ueber" -> UeberDialog(onClose = { dialog = null })
    }

    state.profileEditor?.let { profile ->
        ProfilDialog(
            profile = profile,
            saving = state.profileSaving,
            error = state.profileEditorError,
            onSave = vm::saveProfile,
            onClose = vm::closeProfileEditor,
        )
    }

    if (state.needsRegistration) {
        RegistrationScreen(
            registering = state.registering,
            error = state.registerError,
            onRegister = vm::register,
            modifier = modifier,
        )
        return
    }

    if (state.showHistory) {
        HistoryScreen(
            loading = state.historyLoading,
            profile = state.profile,
            history = state.history,
            error = state.historyError,
            onBack = vm::closeHistory,
            modifier = modifier,
        )
        return
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        TopBar(onProfile = vm::openProfileEditor,
               onHelp = { dialog = "hilfe" }, onAbout = { dialog = "ueber" })

        if (state.phase == Phase.LOADING) {
            CircularProgressIndicator()
            return@Column
        }

        if (state.items.isEmpty()) {
            Text(state.error ?: "Keine Übungswörter gefunden.",
                 color = MaterialTheme.colorScheme.error, textAlign = TextAlign.Center)
            Button(onClick = { vm.loadItems() }) { Text("Erneut versuchen") }
            return@Column
        }

        ItemDropdown(
            items = state.items.map { "${it.text}  [${it.ipa}]" },
            selectedIndex = state.index,
            enabled = state.phase == Phase.READY,
            onSelect = vm::selectItem,
        )

        SpeakerChips(state.speaker, enabled = state.phase == Phase.READY, vm::setSpeaker)

        state.currentItem?.let { item ->
            Spacer(Modifier.height(8.dp))
            Text(item.text, style = MaterialTheme.typography.displayMedium,
                 fontWeight = FontWeight.Bold)
            Text("[${item.ipa}]", style = MaterialTheme.typography.titleLarge,
                 color = MaterialTheme.colorScheme.secondary)
        }

        RecordButton(
            phase = state.phase,
            onClick = {
                val granted = ContextCompat.checkSelfPermission(
                    context, Manifest.permission.RECORD_AUDIO
                ) == PackageManager.PERMISSION_GRANTED
                if (granted) vm.toggleRecording()
                else micPermission.launch(Manifest.permission.RECORD_AUDIO)
            },
        )

        state.error?.let {
            Text(it, color = MaterialTheme.colorScheme.error, textAlign = TextAlign.Center)
        }

        state.result?.result?.let { result ->
            result.error?.let {
                Text(it, color = MaterialTheme.colorScheme.error, textAlign = TextAlign.Center)
            }
            result.segments?.forEach { SegmentResultCard(it, state.targets) }
        }

        Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
            OutlinedButton(onClick = vm::previousItem,
                           enabled = state.phase == Phase.READY) { Text("← Zurück") }
            OutlinedButton(onClick = vm::nextItem,
                           enabled = state.phase == Phase.READY) { Text("Weiter →") }
        }

        OutlinedButton(onClick = vm::openHistory,
                       enabled = state.phase == Phase.READY) { Text("📈  Verlauf") }

        Text("Version ${BuildConfig.VERSION_NAME}",
             style = MaterialTheme.typography.labelSmall,
             color = MaterialTheme.colorScheme.outline)
    }
}

@Composable
private fun TopBar(onProfile: () -> Unit, onHelp: () -> Unit, onAbout: () -> Unit) {
    var menuOpen by remember { mutableStateOf(false) }
    Box(Modifier.fillMaxWidth()) {
        Box(Modifier.align(Alignment.CenterStart)) {
            IconButton(onClick = { menuOpen = true }) {
                Text("☰", style = MaterialTheme.typography.titleLarge)
            }
            DropdownMenu(expanded = menuOpen,
                         onDismissRequest = { menuOpen = false }) {
                DropdownMenuItem(text = { Text(stringResource(R.string.menu_profil)) },
                                 onClick = { menuOpen = false; onProfile() })
                DropdownMenuItem(text = { Text(stringResource(R.string.menu_hilfe)) },
                                 onClick = { menuOpen = false; onHelp() })
                DropdownMenuItem(text = { Text(stringResource(R.string.menu_ueber)) },
                                 onClick = { menuOpen = false; onAbout() })
            }
        }
        Row(modifier = Modifier.align(Alignment.Center),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Image(painterResource(R.drawable.logo_mark), contentDescription = null,
                  modifier = Modifier.height(34.dp))
            Text(stringResource(R.string.app_name),
                 style = MaterialTheme.typography.headlineMedium)
        }
    }
}

@Composable
private fun HilfeDialog(onClose: () -> Unit) {
    AlertDialog(
        onDismissRequest = onClose,
        confirmButton = {
            TextButton(onClick = onClose) { Text(stringResource(R.string.dialog_schliessen)) }
        },
        title = { Text(stringResource(R.string.hilfe_titel)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(stringResource(R.string.hilfe_schritt_1))
                Text(stringResource(R.string.hilfe_schritt_2))
                Text(stringResource(R.string.hilfe_schritt_3))
                Text(stringResource(R.string.hilfe_schritt_4))
                Text(stringResource(R.string.hilfe_tipp))
            }
        })
}

@Composable
private fun UeberDialog(onClose: () -> Unit) {
    val uriHandler = LocalUriHandler.current
    val url = stringResource(R.string.ueber_link_url)
    AlertDialog(
        onDismissRequest = onClose,
        confirmButton = {
            TextButton(onClick = onClose) { Text(stringResource(R.string.dialog_schliessen)) }
        },
        title = { Text(stringResource(R.string.ueber_titel)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(stringResource(R.string.ueber_beschreibung))
                Text(stringResource(R.string.ueber_team))
                Text(stringResource(R.string.ueber_link_text),
                     color = MaterialTheme.colorScheme.primary,
                     modifier = Modifier.clickable { uriHandler.openUri(url) })
                Text("Version ${BuildConfig.VERSION_NAME}",
                     style = MaterialTheme.typography.labelSmall)
            }
        })
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ItemDropdown(
    items: List<String>,
    selectedIndex: Int,
    enabled: Boolean,
    onSelect: (Int) -> Unit,
) {
    var expanded by remember { mutableStateOf(false) }
    ExposedDropdownMenuBox(
        expanded = expanded,
        onExpandedChange = { if (enabled) expanded = it },
    ) {
        OutlinedTextField(
            value = items.getOrElse(selectedIndex) { "" },
            onValueChange = {},
            readOnly = true,
            label = { Text("Übungswort") },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded) },
            modifier = Modifier
                .menuAnchor(ExposedDropdownMenuAnchorType.PrimaryNotEditable)
                .fillMaxWidth(),
        )
        ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            items.forEachIndexed { i, label ->
                DropdownMenuItem(
                    text = { Text(label) },
                    onClick = { onSelect(i); expanded = false },
                )
            }
        }
    }
}

@Composable
private fun SpeakerChips(selected: String, enabled: Boolean, onSelect: (String) -> Unit) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        listOf("male" to "tiefe Stimme", "female" to "hohe Stimme").forEach { (key, label) ->
            FilterChip(
                selected = selected == key,
                onClick = { onSelect(key) },
                enabled = enabled,
                label = { Text(label) },
            )
        }
    }
}

@Composable
private fun RecordButton(phase: Phase, onClick: () -> Unit) {
    Button(
        onClick = onClick,
        enabled = phase == Phase.READY || phase == Phase.RECORDING,
        modifier = Modifier.fillMaxWidth().height(64.dp),
    ) {
        when (phase) {
            Phase.RECORDING -> Text("⏹  Stopp & auswerten")
            Phase.ANALYZING -> {
                CircularProgressIndicator(modifier = Modifier.size(24.dp))
                Spacer(Modifier.size(12.dp))
                Text("Analysiere …")
            }
            else -> Text("🎤  Aufnehmen")
        }
    }
}

@Composable
private fun SegmentResultCard(seg: SegmentResultDto, targets: List<TargetDto>) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp),
               verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Spacer(
                    modifier = Modifier
                        .size(20.dp)
                        .background(ratingColor(seg.rating), CircleShape),
                )
                Text("/${seg.phone}/", style = MaterialTheme.typography.titleLarge,
                     fontWeight = FontWeight.Bold)
                seg.rating?.let {
                    Text(it.uppercase(), color = ratingColor(seg.rating),
                         fontWeight = FontWeight.Bold)
                }
            }
            if (seg.f1 != null && seg.f2 != null) {
                Text("Gemessen: F1 ${seg.f1} Hz · F2 ${seg.f2} Hz",
                     style = MaterialTheme.typography.bodyMedium)
            }
            if (seg.target_f1 != null && seg.target_f2 != null) {
                Text("Ziel: F1 ${seg.target_f1.toInt()} Hz · F2 ${seg.target_f2.toInt()} Hz",
                     style = MaterialTheme.typography.bodyMedium,
                     color = MaterialTheme.colorScheme.secondary)
            }
            seg.note?.let { Text(it, style = MaterialTheme.typography.bodyMedium) }
            seg.feedback?.forEach {
                Text("→ $it", style = MaterialTheme.typography.bodyLarge)
            }
            if (targets.any { it.phone == seg.phone }) {
                VowelChart(
                    targets = targets,
                    focusPhone = seg.phone,
                    measuredF1 = seg.f1?.toDouble(),
                    measuredF2 = seg.f2?.toDouble(),
                    measuredColor = ratingColor(seg.rating),
                )
            }
        }
    }
}
