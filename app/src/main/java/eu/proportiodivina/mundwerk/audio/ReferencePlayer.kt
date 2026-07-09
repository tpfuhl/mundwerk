package eu.proportiodivina.mundwerk.audio

import android.media.MediaPlayer
import java.io.File

/** Spielt eine WAV-Datei (das Referenz-Audio zum Nachsprechen) ab.
 *  Immer nur eine Wiedergabe gleichzeitig; onDone läuft auf dem Thread,
 *  der play() aufgerufen hat (im ViewModel der Main-Thread). */
class ReferencePlayer {
    private var player: MediaPlayer? = null

    fun play(file: File, onDone: () -> Unit) {
        stop()
        player = MediaPlayer().apply {
            setDataSource(file.absolutePath)
            setOnCompletionListener { onDone(); stop() }
            prepare()
            start()
        }
    }

    fun stop() {
        player?.release()
        player = null
    }
}
