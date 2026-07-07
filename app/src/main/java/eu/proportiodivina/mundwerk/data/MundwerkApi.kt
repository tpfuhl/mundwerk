package eu.proportiodivina.mundwerk.data

import java.io.File
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part
import retrofit2.http.Query

// DTOs — Feldnamen entsprechen exakt dem JSON der Django-API.

data class ItemDto(
    val id: Int,
    val text: String,
    val ipa: String,
    val level: String,
    val focus_segments: List<String>,
)

data class SegmentResultDto(
    val phone: String,
    val f1: Int?,
    val f2: Int?,
    val target_f1: Double?,
    val target_f2: Double?,
    val z_f1: Double?,
    val z_f2: Double?,
    val distanz: Double?,
    val rating: String?,       // "grün" | "gelb" | "rot" | null
    val feedback: List<String>?,
    val note: String?,
)

data class AnalysisResultDto(
    val segments: List<SegmentResultDto>?,
    val error: String?,
)

data class RecordingDto(
    val id: Int,
    val status: String,        // "pending" | "done" | "error"
    val result: AnalysisResultDto?,
)

interface MundwerkApi {

    @GET("api/items/")
    suspend fun items(@Query("level") level: String? = null): List<ItemDto>

    @Multipart
    @POST("api/recordings/")
    suspend fun uploadRecording(
        @Part("item_id") itemId: RequestBody,
        @Part("speaker") speaker: RequestBody,
        @Part audio: MultipartBody.Part,
    ): RecordingDto

    companion object {
        const val BASE_URL = "https://mundwerk.proportiodivina.eu/"
        // Für lokale Entwicklung gegen "manage.py runserver" stattdessen:
        // const val BASE_URL = "http://10.0.2.2:8000/"   // Emulator → Host
        // (Cleartext-Freigabe dafür liegt in res/xml/network_security_config.xml)

        fun create(baseUrl: String = BASE_URL): MundwerkApi =
            Retrofit.Builder()
                .baseUrl(baseUrl)
                .addConverterFactory(GsonConverterFactory.create())
                .build()
                .create(MundwerkApi::class.java)
    }
}

private val TEXT = "text/plain".toMediaType()
private val WAV = "audio/wav".toMediaType()

suspend fun MundwerkApi.uploadWav(itemId: Int, speaker: String, file: File): RecordingDto =
    uploadRecording(
        itemId = itemId.toString().toRequestBody(TEXT),
        speaker = speaker.toRequestBody(TEXT),
        audio = MultipartBody.Part.createFormData("audio", file.name, file.asRequestBody(WAV)),
    )
