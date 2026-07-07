package eu.proportiodivina.mundwerk.audio

import android.annotation.SuppressLint
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import java.io.ByteArrayOutputStream
import java.io.File
import kotlin.concurrent.thread

/**
 * Nimmt vom Mikrofon auf und schreibt WAV: 16 kHz, mono, 16 bit PCM —
 * unkomprimiert, weil die Formantanalyse auf dem Server keine
 * Lossy-Artefakte verträgt.
 */
class WavRecorder(private val sampleRate: Int = 16_000) {

    private var recorder: AudioRecord? = null
    private var readerThread: Thread? = null
    @Volatile private var recording = false
    private var pcm = ByteArrayOutputStream()

    val isRecording: Boolean get() = recording

    /** Aufnahme starten. RECORD_AUDIO-Berechtigung muss bereits erteilt sein. */
    @SuppressLint("MissingPermission")
    fun start() {
        check(!recording) { "Aufnahme läuft bereits" }
        val minBuf = AudioRecord.getMinBufferSize(
            sampleRate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        val rec = AudioRecord(
            MediaRecorder.AudioSource.MIC, sampleRate,
            AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, minBuf * 4)
        check(rec.state == AudioRecord.STATE_INITIALIZED) {
            "Mikrofon nicht verfügbar"
        }
        pcm = ByteArrayOutputStream()
        recorder = rec
        recording = true
        rec.startRecording()
        readerThread = thread(name = "WavRecorder") {
            val buf = ByteArray(minBuf)
            while (recording) {
                val n = rec.read(buf, 0, buf.size)
                if (n > 0) pcm.write(buf, 0, n)
            }
        }
    }

    /** Aufnahme beenden und als WAV-Datei schreiben. */
    fun stop(outFile: File): File {
        recording = false
        readerThread?.join()
        readerThread = null
        recorder?.run { stop(); release() }
        recorder = null
        writeWav(outFile, pcm.toByteArray())
        return outFile
    }

    private fun writeWav(file: File, data: ByteArray) {
        val byteRate = sampleRate * 2          // mono, 16 bit
        file.outputStream().use { out ->
            out.write("RIFF".toByteArray())
            out.writeIntLE(36 + data.size)
            out.write("WAVE".toByteArray())
            out.write("fmt ".toByteArray())
            out.writeIntLE(16)                 // fmt-Chunk-Größe
            out.writeShortLE(1)                // PCM
            out.writeShortLE(1)                // mono
            out.writeIntLE(sampleRate)
            out.writeIntLE(byteRate)
            out.writeShortLE(2)                // Block-Align
            out.writeShortLE(16)               // Bits pro Sample
            out.write("data".toByteArray())
            out.writeIntLE(data.size)
            out.write(data)
        }
    }
}

private fun java.io.OutputStream.writeIntLE(v: Int) =
    write(byteArrayOf(v.toByte(), (v shr 8).toByte(), (v shr 16).toByte(), (v shr 24).toByte()))

private fun java.io.OutputStream.writeShortLE(v: Int) =
    write(byteArrayOf(v.toByte(), (v shr 8).toByte()))
