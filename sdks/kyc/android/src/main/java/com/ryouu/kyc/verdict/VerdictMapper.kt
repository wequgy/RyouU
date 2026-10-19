package com.ryouu.kyc.verdict

import com.ryouu.kyc.model.KycResult
import com.ryouu.kyc.model.KycStatus
import org.json.JSONObject

object VerdictMapper {

    /**
     * Maps the customer backend /kyc/status response JSON to the public KycResult.
     *
     * Rules:
     * - The VERDICT is `final_decision ?? decision`, NEVER `status`.
     * - `status="completed"` only means checks have finished evaluating; it is NOT success.
     * - Only `approved` is success (KycStatus.SUCCESS).
     * - `needs_review` and `rejected_recommended` map to KycStatus.IN_REVIEW.
     * - `rejected` maps to KycStatus.FAILED.
     * - Inconclusive or null verdict maps to KycStatus.IN_REVIEW.
     */
    fun mapBackendVerdict(jsonString: String): KycResult {
        val obj = JSONObject(jsonString)
        val id = obj.optString("id", "")
        val rawDecision = if (obj.has("decision") && !obj.isNull("decision")) obj.getString("decision") else null
        val rawFinalDecision = if (obj.has("final_decision") && !obj.isNull("final_decision")) obj.getString("final_decision") else null

        val verdict = rawFinalDecision ?: rawDecision

        val status = when (verdict) {
            "approved" -> KycStatus.SUCCESS
            "needs_review", "rejected_recommended" -> KycStatus.IN_REVIEW
            "rejected" -> KycStatus.FAILED
            else -> KycStatus.IN_REVIEW
        }

        val riskScore: Double? = if (obj.has("trust") && !obj.isNull("trust")) {
            val trust = obj.getDouble("trust")
            Math.round((1.0 - trust) * 100.0) / 100.0
        } else {
            null
        }

        val reasonsList = mutableListOf<String>()
        if (obj.has("reasons") && !obj.isNull("reasons")) {
            val reasonsArr = obj.getJSONArray("reasons")
            for (i in 0 until reasonsArr.length()) {
                reasonsList.add(reasonsArr.getString(i))
            }
        }

        return KycResult(
            status = status,
            verificationId = id,
            riskScore = riskScore,
            reasons = reasonsList,
            rawDecision = rawDecision,
            rawFinalDecision = rawFinalDecision
        )
    }
}
