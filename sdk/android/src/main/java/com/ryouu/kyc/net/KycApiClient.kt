package com.ryouu.kyc.net

import com.ryouu.kyc.model.KycConfig
import com.ryouu.kyc.model.KycParams
import com.ryouu.kyc.model.KycResult
import com.ryouu.kyc.model.KycStatus
import com.ryouu.kyc.verdict.VerdictMapper
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.IOException
import java.net.URLEncoder
import java.util.concurrent.TimeUnit

class KycApiClient(
    private val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .build()
) {

    /**
     * Calls the customer backend (e.g. POST /kyc/session) to create a session without exposing secret keys.
     * Returns Pair(verificationId, flowUrl).
     */
    suspend fun createSession(config: KycConfig, params: KycParams): Pair<String, String> = withContext(Dispatchers.IO) {
        val jsonPayload = JSONObject().apply {
            put("reference_id", params.referenceId)
            put("policy", params.policy)
            val expected = JSONObject()
            params.name?.let { expected.put("name", it) }
            params.dob?.let { expected.put("dob", it) }
            params.idLast4?.let { expected.put("id_last4", it) }
            params.email?.let { expected.put("email", it) }
            params.phone?.let { expected.put("phone", it) }
            put("expected", expected)
            // Top-level fallbacks for compatibility with simple backend handlers
            params.name?.let { put("name", it) }
            params.dob?.let { put("dob", it) }
            params.email?.let { put("email", it) }
            params.phone?.let { put("phone", it) }
        }

        val requestBody = jsonPayload.toString().toRequestBody("application/json".toMediaType())
        val url = config.backendUrl.trimEnd('/') + "/kyc/session"
        val request = Request.Builder()
            .url(url)
            .post(requestBody)
            .build()

        val response = client.newCall(request).execute()
        val bodyString = response.body?.string() ?: ""
        if (!response.isSuccessful) {
            throw IOException("Customer backend session creation failed (${response.code}): $bodyString")
        }

        val respJson = JSONObject(bodyString)
        val id = respJson.getString("id")
        val baseFlowUrl = respJson.getString("flow_url")
        val hostFromBackend = try {
            java.net.URI(config.backendUrl).host
        } catch (e: Exception) {
            null
        }

        val resolvedBaseUrl = if (hostFromBackend != null && (
            baseFlowUrl.contains("localhost") ||
            baseFlowUrl.contains("127.0.0.1") ||
            baseFlowUrl.contains("10.0.2.2")
        )) {
            baseFlowUrl
                .replace("10.0.2.2", hostFromBackend)
                .replace("localhost", hostFromBackend)
                .replace("127.0.0.1", hostFromBackend)
        } else {
            baseFlowUrl
        }

        // Append query pre-fills if not already embedded
        val queryParams = mutableListOf<String>()
        params.name?.takeIf { it.isNotBlank() }?.let { queryParams.add("name=${URLEncoder.encode(it, "UTF-8")}") }
        params.dob?.takeIf { it.isNotBlank() }?.let { queryParams.add("dob=${URLEncoder.encode(it, "UTF-8")}") }
        params.email?.takeIf { it.isNotBlank() }?.let { queryParams.add("email=${URLEncoder.encode(it, "UTF-8")}") }
        params.phone?.takeIf { it.isNotBlank() }?.let { queryParams.add("phone=${URLEncoder.encode(it, "UTF-8")}") }

        val flowUrl = if (queryParams.isNotEmpty()) {
            val delimiter = if (resolvedBaseUrl.contains("?")) "&" else "?"
            resolvedBaseUrl + delimiter + queryParams.joinToString("&")
        } else {
            resolvedBaseUrl
        }

        Pair(id, flowUrl)
    }

    /**
     * Polls the customer backend GET /kyc/status/{vid} until terminal verdict or timeout.
     * Never trusts the WebView; always fetches the authentic server verdict.
     */
    suspend fun pollVerdict(
        config: KycConfig,
        verificationId: String
    ): KycResult = withContext(Dispatchers.IO) {
        val url = config.backendUrl.trimEnd('/') + "/kyc/status/$verificationId"
        var attempts = 0
        var lastResult: KycResult? = null

        while (attempts < config.maxPollingAttempts) {
            attempts++
            try {
                val request = Request.Builder().url(url).get().build()
                val response = client.newCall(request).execute()
                val body = response.body?.string() ?: ""

                if (response.isSuccessful) {
                    val result = VerdictMapper.mapBackendVerdict(body)
                    lastResult = result

                    val obj = JSONObject(body)
                    val status = obj.optString("status", "")
                    val hasDecision = (result.rawFinalDecision != null || result.rawDecision != null)

                    // If checks are completed or definitive decision is rendered, return immediately
                    if (status == "completed" || hasDecision) {
                        return@withContext result
                    }
                }
            } catch (e: Exception) {
                // Continue polling on transient network error
            }

            delay(config.pollingIntervalMs)
        }

        // Return last fetched result or fallback to IN_REVIEW
        lastResult ?: KycResult(
            status = KycStatus.IN_REVIEW,
            verificationId = verificationId,
            reasons = listOf("Polling timed out while waiting for terminal verification verdict")
        )
    }
}
