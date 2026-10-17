# RyouU KYC Android SDK

Native Android SDK for identity verification and biometric liveness checks using RyouU KYC.

## Architecture & Security Principles

1. **Zero Secret Key Exposure**:
   The Android SDK **NEVER** holds your KYC secret API key.
   The mobile app connects to your customer backend (e.g. `ApexPay Server`), which uses the server-side SDK (Python/Node) to create verification sessions with your secret API key.

2. **Hardware Biometric Acceleration**:
   The verification page runs inside an in-app WebView with hardware camera, audio, and WebRTC grants. Direct camera capture ensures authentic selfie and document capture without gallery bypass.

3. **Cryptographic Verdict Isolation**:
   The client application **NEVER** trusts WebView `postMessage` data for the verification verdict.
   When the hosted flow finishes, the SDK automatically polls your customer backend (`GET /kyc/status/{id}`) to fetch the authentic server verdict (`approved` -> `SUCCESS`, `needs_review`/`rejected_recommended` -> `IN_REVIEW`, `rejected` -> `FAILED`).

## Installation

Add the local repository to your app's `settings.gradle.kts` (or root `build.gradle.kts` `dependencyResolutionManagement`):
```kotlin
dependencyResolutionManagement {
    repositories {
        google()
        mavenCentral()
        // Path to the published sdk repo directory in the cloned kyc-service repository:
        maven { url = uri("../kyc-service/sdk/android/repo") }
        // Or resolve from ~/.m2 if you ran ./gradlew publishToMavenLocal
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


## Quick Start (Jetpack Compose)

```kotlin
import com.ryouu.kyc.model.KycConfig
import com.ryouu.kyc.model.KycParams
import com.ryouu.kyc.model.KycStatus
import com.ryouu.kyc.ui.RyouUKycModal

@Composable
fun MyBankingScreen() {
    var showKycModal by remember { mutableStateOf(false) }

    val kycConfig = remember {
        KycConfig(
            backendUrl = "http://10.0.2.2:9000", // Your customer backend URL
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
                    // Verification approved! Unlock high-tier limits
                }
                KycStatus.IN_REVIEW -> {
                    // Under manual review
                }
                KycStatus.FAILED -> {
                    // Verification failed
                }
                KycStatus.CANCELLED -> {
                    // User dismissed
                }
            }
        },
        onCancel = {
            showKycModal = false
        },
        onError = { error ->
            showKycModal = false
            // Handle network or permission error
        }
    )
}
```
