plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "ga.mrhomes.callnote"
    compileSdk = 34

    defaultConfig {
        applicationId = "ga.mrhomes.callnote"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"
    }

    signingConfigs {
        create("release") {
            // 개인 사이드로드용 키 (저장소에 포함 — callnote-android/README.md의 보안 주의 참고)
            storeFile = rootProject.file("release-key.jks")
            storePassword = "callnote-sideload"
            keyAlias = "callnote"
            keyPassword = "callnote-sideload"
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("release")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.work:work-runtime-ktx:2.9.1")
}
