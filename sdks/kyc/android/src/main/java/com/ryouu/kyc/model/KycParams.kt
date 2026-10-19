package com.ryouu.kyc.model

/**
 * Parameters used to initiate a verification session via the customer backend.
 *
 * @param referenceId Unique reference for this verification (e.g. user ID or order ID)
 * @param name Expected full name to match against document and audio/ID details
 * @param dob Expected date of birth (YYYY-MM-DD)
 * @param idLast4 Expected last 4 digits of government ID
 * @param email Expected email address for OTP verification
 * @param phone Expected phone number for OTP verification
 * @param policy Verification policy (e.g. "strict" or "lenient")
 */
data class KycParams(
    val referenceId: String,
    val name: String? = null,
    val dob: String? = null,
    val idLast4: String? = null,
    val email: String? = null,
    val phone: String? = null,
    val policy: String = "strict"
)
