import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
}

// Version aus Git ableiten: versionCode = Commit-Anzahl (monoton steigend),
// versionName = 1.0.<Anzahl>+<Kurzhash> — so ist jeder Build eindeutig
// einem Commit zuzuordnen (wird unten im Übungsscreen angezeigt).
// providers.exec ist configuration-cache-kompatibel.
val gitCommitCount = providers.exec {
    commandLine("git", "rev-list", "--count", "HEAD")
}.standardOutput.asText.map { it.trim().toIntOrNull() ?: 1 }

val gitShortHash = providers.exec {
    commandLine("git", "rev-parse", "--short", "HEAD")
}.standardOutput.asText.map { it.trim().ifEmpty { "nogit" } }

android {
    namespace = "eu.proportiodivina.mundwerk"
    compileSdk {
        version = release(36) {
            minorApiLevel = 1
        }
    }

    defaultConfig {
        applicationId = "eu.proportiodivina.mundwerk"
        minSdk = 34
        targetSdk = 36
        versionCode = gitCommitCount.get()
        versionName = "1.0.${gitCommitCount.get()}+${gitShortHash.get()}"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"

        // API-Token aus local.properties (gitignored, nicht im Repo):
        //   mundwerk.apiToken=<Token aus Django-Admin bzw. drf_create_token>
        val props = Properties()
        rootProject.file("local.properties").takeIf { it.exists() }
            ?.inputStream()?.use { props.load(it) }
        buildConfigField("String", "API_TOKEN",
            "\"${props.getProperty("mundwerk.apiToken") ?: ""}\"")
    }

    // Zwei Varianten: "dev" mit einkompiliertem Token aus local.properties
    // (Registrierung erscheint nie), "learner" ohne Token — verhält sich
    // wie bei einem echten Lerner (Registrierung beim ersten Start).
    // Eigene applicationId, damit beide parallel installierbar sind.
    flavorDimensions += "distribution"
    productFlavors {
        create("dev") {
            dimension = "distribution"
        }
        create("learner") {
            dimension = "distribution"
            applicationIdSuffix = ".learner"
            versionNameSuffix = "-learner"
            buildConfigField("String", "API_TOKEN", "\"\"")
        }
    }

    buildTypes {
        release {
            optimization {
                enable = false
            }
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
}

dependencies {
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.graphics)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.retrofit)
    implementation(libs.retrofit.converter.gson)
    testImplementation(libs.junit)
    androidTestImplementation(platform(libs.androidx.compose.bom))
    androidTestImplementation(libs.androidx.compose.ui.test.junit4)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(libs.androidx.junit)
    debugImplementation(libs.androidx.compose.ui.test.manifest)
    debugImplementation(libs.androidx.compose.ui.tooling)
}