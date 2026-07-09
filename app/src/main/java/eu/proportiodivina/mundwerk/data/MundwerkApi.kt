package eu.proportiodivina.mundwerk.data

import eu.proportiodivina.mundwerk.BuildConfig
import java.io.File
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.ResponseBody
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Part
import retrofit2.http.Path
import retrofit2.http.Query
import retrofit2.http.Streaming

// DTOs — Feldnamen entsprechen exakt dem JSON der Django-API.

data class ItemDto(
    val id: Int,
    val text: String,
    val ipa: String,
    val level: String,
    val kind: String = "wort",         // laut | wort | satz
    val gruppe: String = "",           // Vokaltrapez-Gruppe (nur laut)
    val beschreibung: String = "",     // Artikulationserklärung
    val has_audio: Boolean = false,    // Referenz-Audio vorhanden?
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
    val item: ItemDto?,
    val status: String,        // "pending" | "done" | "error"
    val result: AnalysisResultDto?,
    val ist_referenz: Boolean?,
    val created_at: String?,   // ISO-8601
)

data class ReferenzRequest(val ist_referenz: Boolean)

data class PhoneStatDto(
    val phone: String,
    val versuche: Int,
    val mittlere_distanz: Double,
    val beste_distanz: Double,
    val letztes_rating: String?,
)

data class ProfileDto(
    val username: String,
    val vorname: String?,
    val nachname: String?,
    val muttersprache: String?,
    val korpus: Boolean?,      // darf Referenzaufnahmen markieren
    val uebungen_gesamt: Int,
    val phones: List<PhoneStatDto>,
)

data class RegisterRequest(
    val vorname: String,
    val nachname: String,
    val nickname: String,
    val muttersprache: String,   // ISO 639-1, z. B. "fr"
)

data class RegisterResponse(
    val token: String,
    val nickname: String,
)

data class ProfileUpdateRequest(
    val vorname: String,
    val nachname: String,
    val muttersprache: String,
)

data class TargetDto(
    val phone: String,
    val speaker: String,
    val f1_mean: Double,
    val f1_sd: Double,
    val f2_mean: Double,
    val f2_sd: Double,
)

interface MundwerkApi {

    @POST("api/register/")
    suspend fun register(@Body body: RegisterRequest): RegisterResponse

    @GET("api/items/")
    suspend fun items(
        @Query("level") level: String? = null,
        @Query("kind") kind: String? = null,
        @Query("gruppe") gruppe: String? = null,
    ): List<ItemDto>

    @Streaming
    @GET("api/items/{id}/audio/")
    suspend fun itemAudio(@Path("id") id: Int): ResponseBody

    @GET("api/targets/")
    suspend fun targets(@Query("speaker") speaker: String): List<TargetDto>

    @GET("api/profile/")
    suspend fun profile(): ProfileDto

    @PUT("api/profile/")
    suspend fun updateProfile(@Body body: ProfileUpdateRequest): ProfileDto

    @GET("api/recordings/")
    suspend fun recordings(): List<RecordingDto>

    @POST("api/recordings/{id}/referenz/")
    suspend fun setReferenz(@Path("id") id: Int,
                            @Body body: ReferenzRequest): RecordingDto

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

        fun create(baseUrl: String = BASE_URL,
                   tokenProvider: () -> String? = { BuildConfig.API_TOKEN }): MundwerkApi {
            // Der Token kommt pro Request vom tokenProvider (TokenStore:
            // BuildConfig-Token für Entwickler-Builds, sonst der bei der
            // Registrierung gespeicherte). Ohne Token — z. B. beim
            // Registrierungs-Request selbst — geht der Request ohne
            // Authorization-Header raus.
            val client = OkHttpClient.Builder()
                .addInterceptor { chain ->
                    val token = tokenProvider()
                    val request = if (!token.isNullOrEmpty()) {
                        chain.request().newBuilder()
                            .header("Authorization", "Token $token")
                            .build()
                    } else chain.request()
                    chain.proceed(request)
                }
                .build()
            return Retrofit.Builder()
                .baseUrl(baseUrl)
                .client(client)
                .addConverterFactory(GsonConverterFactory.create())
                .build()
                .create(MundwerkApi::class.java)
        }
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
