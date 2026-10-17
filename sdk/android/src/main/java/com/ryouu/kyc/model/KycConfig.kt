package com.ryouu.kyc.model

/**
 * Configuration options for the RyouU KYC Android SDK.
 *
 * NOTE: The SDK connects to your CUSTOMER BACKEND (e.g. ApexPay Server), NEVER directly
 * to the KYC API with a secret key. Secret API keys must live strictly on your backend.
 *
 * @param backendUrl The base URL of your customer backend (e.g., "http://10.0.2.2:9000")
 * @param timeoutMs Maximum duration in milliseconds to wait for backend responses
 * @param pollingIntervalMs Polling frequency in milliseconds when fetching verdicts
 * @param maxPollingAttempts Maximum number of poll attempts before timing out
 */
data class KycConfig(
    val backendUrl: String,
    val timeoutMs: Long = 20_000L,
    val pollingIntervalMs: Long = 1_500L,
    val maxPollingAttempts: Int = 30
)
