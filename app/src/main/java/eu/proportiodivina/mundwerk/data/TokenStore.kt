package eu.proportiodivina.mundwerk.data

import android.content.Context
import eu.proportiodivina.mundwerk.BuildConfig

/**
 * Hält den API-Token des Users. Quelle in dieser Reihenfolge:
 * 1. BuildConfig.API_TOKEN (Entwickler-Builds mit Token aus local.properties)
 * 2. bei der Registrierung erhaltener, app-privat gespeicherter Token
 * Fehlen beide, muss sich der User registrieren.
 */
class TokenStore(context: Context) {

    private val prefs = context.getSharedPreferences("mundwerk", Context.MODE_PRIVATE)

    val token: String?
        get() = BuildConfig.API_TOKEN.ifEmpty {
            prefs.getString(KEY, null)
        }

    fun save(token: String) {
        prefs.edit().putString(KEY, token).apply()
    }

    private companion object {
        const val KEY = "api_token"
    }
}
