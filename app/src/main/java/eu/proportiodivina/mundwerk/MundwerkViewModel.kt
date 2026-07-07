package eu.proportiodivina.mundwerk

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import eu.proportiodivina.mundwerk.audio.WavRecorder
import eu.proportiodivina.mundwerk.data.ItemDto
import eu.proportiodivina.mundwerk.data.MundwerkApi
import eu.proportiodivina.mundwerk.data.RecordingDto
import eu.proportiodivina.mundwerk.data.uploadWav
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
) {
    val currentItem: ItemDto? get() = items.getOrNull(index)
}

class MundwerkViewModel(app: Application) : AndroidViewModel(app) {

    private val api = MundwerkApi.create()
    private val recorder = WavRecorder()

    private val _state = MutableStateFlow(UiState())
    val state = _state.asStateFlow()

    init {
        loadItems()
    }

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
