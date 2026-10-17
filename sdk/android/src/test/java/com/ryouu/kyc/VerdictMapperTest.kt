package com.ryouu.kyc

import com.ryouu.kyc.model.KycStatus
import com.ryouu.kyc.verdict.VerdictMapper
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class VerdictMapperTest {

    @Test
    fun testApprovedVerdictMapsToSuccess() {
        val json = """
            {
                "id": "vid_123",
                "status": "completed",
                "decision": "approved",
                "trust": 0.95,
                "reasons": []
            }
        """.trimIndent()

        val result = VerdictMapper.mapBackendVerdict(json)
        assertEquals(KycStatus.SUCCESS, result.status)
        assertEquals("vid_123", result.verificationId)
        assertEquals(0.05, result.riskScore ?: 0.0, 0.001)
        assertTrue(result.reasons.isEmpty())
    }

    @Test
    fun testNeedsReviewMapsToInReview() {
        val json = """
            {
                "id": "vid_456",
                "status": "completed",
                "decision": "needs_review",
                "trust": 0.65,
                "reasons": ["face_match_uncertain"]
            }
        """.trimIndent()

        val result = VerdictMapper.mapBackendVerdict(json)
        assertEquals(KycStatus.IN_REVIEW, result.status)
        assertEquals("vid_456", result.verificationId)
        assertEquals(1, result.reasons.size)
        assertEquals("face_match_uncertain", result.reasons[0])
    }

    @Test
    fun testRejectedRecommendedMapsToInReview() {
        val json = """
            {
                "id": "vid_789",
                "status": "completed",
                "decision": "rejected_recommended",
                "trust": 0.20,
                "reasons": ["synthetic_voice_detected"]
            }
        """.trimIndent()

        val result = VerdictMapper.mapBackendVerdict(json)
        assertEquals(KycStatus.IN_REVIEW, result.status)
        assertEquals("rejected_recommended", result.rawDecision)
    }

    @Test
    fun testRejectedMapsToFailed() {
        val json = """
            {
                "id": "vid_999",
                "status": "completed",
                "final_decision": "rejected",
                "reasons": ["fraud_confirmed_by_analyst"]
            }
        """.trimIndent()

        val result = VerdictMapper.mapBackendVerdict(json)
        assertEquals(KycStatus.FAILED, result.status)
    }

    @Test
    fun testCompletedStatusWithoutApprovedDecisionNeverMapsToSuccess() {
        // Critical Section 1.4 security requirement: status='completed' only means checks finished.
        val json = """
            {
                "id": "vid_hack_attempt",
                "status": "completed",
                "decision": null,
                "reasons": []
            }
        """.trimIndent()

        val result = VerdictMapper.mapBackendVerdict(json)
        assertEquals(KycStatus.IN_REVIEW, result.status)
    }

    @Test
    fun testFinalDecisionOverridesAutomatedDecision() {
        val json = """
            {
                "id": "vid_override",
                "status": "completed",
                "decision": "needs_review",
                "final_decision": "approved"
            }
        """.trimIndent()

        val result = VerdictMapper.mapBackendVerdict(json)
        assertEquals(KycStatus.SUCCESS, result.status)
        assertEquals("approved", result.rawFinalDecision)
        assertEquals("needs_review", result.rawDecision)
    }
}
