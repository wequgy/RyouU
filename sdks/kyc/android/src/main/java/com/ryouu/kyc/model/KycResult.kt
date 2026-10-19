package com.ryouu.kyc.model

/**
 * Public status of a verification result.
 *
 * Rules:
 * - SUCCESS: The identity was definitively approved (verdict is 'approved').
 * - IN_REVIEW: Verdict requires manual compliance reviewer triage ('needs_review' or 'rejected_recommended').
 * - FAILED: Verification was definitively rejected by policy/compliance reviewer ('rejected').
 * - CANCELLED: The user exited or cancelled before completion.
 */
enum class KycStatus {
    SUCCESS,
    IN_REVIEW,
    FAILED,
    CANCELLED
}

/**
 * Result returned to the host application after verification completes and authentic
 * verdict is fetched from the customer's backend.
 */
data class KycResult(
    val status: KycStatus,
    val verificationId: String,
    val riskScore: Double? = null,
    val reasons: List<String> = emptyList(),
    val rawDecision: String? = null,
    val rawFinalDecision: String? = null
)
