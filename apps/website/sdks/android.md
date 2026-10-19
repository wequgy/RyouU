---
title: Android SDK (Kotlin & Compose)
description: Native Android SDK for Jetpack Compose and XML Views with hardware camera acceleration.
---

The RyouU Android SDK (`com.ryouu.kyc:sdk:1.0.0`) provides native Jetpack Compose and Android View components that open the hosted verification workflow inside a hardened, isolated WebView.

---

## Installation

Add the local repository to your `settings.gradle.kts` (or root `build.gradle.kts`):

```kotlin
dependencyResolutionManagement {
    repositories {
        google()
        mavenCentral()
        maven { url = uri("../kyc-service/sdk/android/repo") }
        mavenLocal()
    }
}
```

In your app's `build.gradle.kts`:

```kotlin
dependencies {
    implementation("com.ryouu.kyc:sdk:1.0.0")
}
```

---

## Jetpack Compose Integration

```kotlin
import androidx.compose.runtime.*
import androidx.compose.material3.Button
import androidx.compose.material3.Text
import com.ryouu.kyc.model.KycConfig
import com.ryouu.kyc.model.KycParams
import com.ryouu.kyc.model.KycStatus
import com.ryouu.kyc.ui.RyouUKycModal

@Composable
fun MyBankingScreen() {
    var showKycModal by remember { mutableStateOf(false) }

    val kycConfig = remember {
        KycConfig(
            backendUrl = "https://api.yourfintech.com", // Your backend URL, NOT secret KYC server
            timeoutMs = 20_000L
        )
    }

    val kycParams = remember {
        KycParams(
            referenceId = "user_1001",
            name = "Alex Rivera",
            dob = "1998-05-14",
            email = "alex@example.com",
            phone = "+15551234567",
            policy = "strict"
        )
    }

    Button(onClick = { showKycModal = true }) {
        Text("Verify Identity")
    }

    RyouUKycModal(
        visible = showKycModal,
        config = kycConfig,
        params = kycParams,
        onComplete = { result ->
            showKycModal = false
            when (result.status) {
                KycStatus.SUCCESS -> {
                    // Verification approved! Unlock features
                }
                KycStatus.IN_REVIEW -> {
                    // Sent to manual human review
                }
                KycStatus.FAILED -> {
                    // Verification rejected
                }
                KycStatus.CANCELLED -> {
                    // User closed the modal
                }
            }
        },
        onCancel = { showKycModal = false },
        onError = { error -> showKycModal = false }
    )
}
```
