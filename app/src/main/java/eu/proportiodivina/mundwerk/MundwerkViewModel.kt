package eu.proportiodivina.mundwerk

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import eu.proportiodivina.mundwerk.audio.WavRecorder
import eu.proportiodivina.mundwerk.data.ItemDto
import eu.proportiodivina.mundwerk.data.MundwerkApi
import eu.proportiodivina.mundwerk.data.ProfileDto
import eu.proportiodivina.mundwerk.data.RecordingDto
import eu.proportiodivina.mundwerk.data.RegisterRequest
import eu.proportiodivina.mundwerk.data.TokenStore
import eu.proportiodivina.mundwerk.data.uploadWav
import kotlinx.coroutines.async
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

enum class Phase { LOADING, READY, RECORDING, ANALYZING }

data class UiState(
    val items: List<ItemDto> = emptyList(),
    val index: Int = 0,
    val speaker: String = "male",
    val phase: Phase = Phase.LOADING,
    val result: RecordingDto? = null,
    val error: String? = null,
    // Registrierung (erster App-Start ohne Token)
    val needsRegistration: Boolean = false,
    val registering: Boolean = false,
    val registerError: String? = null,
    // Verlaufs-Screen
    val showHistory: Boolean = false,
    val historyLoading: Boolean = false,
    val profile: ProfileDto? = null,
    val history: List<RecordingDto> = emptyList(),
    val historyError: String? = null,
) {
    val currentItem: ItemDto? get() = items.getOrNull(index)
}

class MundwerkViewModel(app: Application) : AndroidViewModel(app) {

    private val tokenStore = TokenStore(app)
    private val api = MundwerkApi.create(tokenProvider = { tokenStore.token })
    private val recorder = WavRecorder()

    private val _state = MutableStateFlow(UiState())
    val state = _state.asStateFlow()

    init {
        if (tokenStore.token.isNullOrEmpty()) {
            _state.update { it.copy(needsRegistration = true, phase = Phase.READY) }
        } else {
            loadItems()
        }
    }

    fun register(vorname: String, nachname: String, nickname: String,
                 muttersprache: String) {
        _state.update { it.copy(registering = true, registerError = null) }
        viewModelScope.launch {
            runCatching {
                api.register(RegisterRequest(vorname.trim(), nachname.trim(),
                                             nickname.trim(), muttersprache))
            }
                .onSuccess { response ->
                    tokenStore.save(response.token)
                    _state.update { it.copy(needsRegistration = false,
                                            registering = false) }
                    loadItems()
                }
                .onFailure { e ->
                    _state.update { it.copy(registering = false,
                                            registerError = registerErrorText(e)) }
                }
        }
    }

    private fun registerErrorText(e: Throwable): String =
        if (e is retrofit2.HttpException) {
            val body = e.response()?.errorBody()?.string().orEmpty()
            when {
                "vergeben" in body -> "Dieser Nickname ist schon vergeben."
                "ISO" in body -> "Bitte eine Muttersprache auswählen."
                e.code() == 429 -> "Zu viele Versuche — bitte später erneut."
                else -> "Registrierung fehlgeschlagen (${e.code()})."
            }
        } else "Server nicht erreichbar: ${e.message}"

    fun loadItems() {
        _state.update { it.copy(phase = Phase.LOADING, error = null) }
        viewModelScope.launch {
            runCatching { api.items() }
                .onSuccess { items ->
                    _state.update { it.copy(items = items, index = 0, phase = Phase.READY) }
                }
                .onFailure { e ->
                    _state.update {
                        it.copy(phase = Phase.READY,
                                error = "Server nicht erreichbar: ${e.message}")
                    }
                }
        }
    }

    fun selectItem(index: Int) {
        if (_state.value.phase == Phase.READY) {
            _state.update { it.copy(index = index, result = null, error = null) }
        }
    }

    fun nextItem() = selectItem((_state.value.index + 1).mod(_state.value.items.size))

    fun previousItem() = selectItem((_state.value.index - 1).mod(_state.value.items.size))

    fun setSpeaker(speaker: String) {
        _state.update { it.copy(speaker = speaker) }
    }

    fun openHistory() {
        _state.update { it.copy(showHistory = true, historyLoading = true,
                                historyError = null) }
        viewModelScope.launch {
            runCatching {
                val profile = async { api.profile() }
                val recordings = async { api.recordings() }
                profile.await() to recordings.await()
            }
                .onSuccess { (profile, recordings) ->
                    _state.update { it.copy(historyLoading = false,
                                            profile = profile,
                                            history = recordings) }
                }
                .onFailure { e ->
                    _state.update { it.copy(historyLoading = false,
                                            historyError = "Verlauf nicht ladbar: ${e.message}") }
                }
        }
    }

    fun closeHistory() {
        _state.update { it.copy(showHistory = false) }
    }

    /** Ein Button: erster Druck startet die Aufnahme, zweiter stoppt + sendet. */
    fun toggleRecording() {
        when (_state.value.phase) {
            Phase.READY -> startRecording()
            Phase.RECORDING -> stopAndAnalyze()
            else -> Unit
        }
    }

    private fun startRecording() {
        runCatching { recorder.start() }
            .onSuccess {
                _state.update { it.copy(phase = Phase.RECORDING, result = null, error = null) }
            }
            .onFailure { e ->
                _state.update { it.copy(error = e.message) }
            }
    }

    private fun stopAndAnalyze() {
        val item = _state.value.currentItem ?: return
        val speaker = _state.value.speaker
        _state.update { it.copy(phase = Phase.ANALYZING) }
        viewModelScope.launch {
            runCatching {
                withContext(Dispatchers.IO) {
                    val wav = recorder.stop(
                        File(getApplication<Application>().cacheDir, "aufnahme.wav"))
                    api.uploadWav(item.id, speaker, wav)
                }
            }
                .onSuccess { rec ->
                    _state.update { it.copy(phase = Phase.READY, result = rec) }
                }
                .onFailure { e ->
                    _state.update {
                        it.copy(phase = Phase.READY,
                                error = "Analyse fehlgeschlagen: ${e.message}")
                    }
                }
        }
    }
}
