---
title: Reading the Verdict
description: Critical guide to interpreting verification statuses, final decisions, and reason codes.
---

> [!CAUTION]
> **CRITICAL PRODUCTION INTEGRATION RULE**:
> `status: "completed"` **ONLY** means all processing stages and neural models have finished executing. It **DOES NOT** mean the user passed verification!
>
> The actual verification verdict is determined exclusively by:
> ```typescript
> const verdict = verification.final_decision ?? verification.decision;
> ```
> Only `verdict === "approved"` represents a successful verification. Treating `status === "completed"` as success is the **#1 vulnerability** in automated onboarding implementations.

---

## 1. The Three Decision States

Every verification evaluates to one of three server-enforced decision states:

| Decision State | Meaning | Action for Your Backend |
| :--- | :--- | :--- |
| **`approved`** | **Success**. All hard gates passed, face similarity meets threshold, and no anomalous deepfake or anti-spoof flags were triggered. | Activate user account, issue tokens, or permit high-tier transactions. |
| **`needs_review`** | **Neither success nor failure**. One or more probabilistic soft signals (deepfake classifier, lip-sync, anti-spoofing, scene integrity) indicated uncertainty. | Queue verification for manual human compliance review in your internal dashboard. |
| **`rejected_recommended`** | **Failed verification**. A strict, objective hard gate failed (e.g. document name or DOB mismatch, failed SMS OTP, or face cosine similarity &lt; 0.25). | Request re-attempt or reject onboarding attempt according to your risk policy. |

---

## 2. Decision Precedence (`final_decision` vs `decision`)

RyouU implements a human-in-the-loop architecture where automated recommendations can be reviewed and amended by authenticated compliance officers:

```json
{
  "id": "ver_9a482b1c",
  "status": "completed",
  "decision": "needs_review",
  "final_decision": "approved",
  "trust": 0.82,
  "reasons": ["video_deepfake_uncertain", "passive_anti_spoof_uncalibrated"],
  "review": {
    "reviewer_id": "usr_compliance_04",
    "decision": "approved",
    "note": "Physically inspected original physical passport via video call.",
    "reviewed_at": "2026-10-19T14:30:00Z"
  }
}
```

When evaluating a verification:
1. Check `final_decision` first. If non-null, a human reviewer has explicitly made a manual determination that overrides the automated recommendation.
2. If `final_decision` is null, evaluate `decision` (the autonomous recommendation).

```python
# Evaluates final decision with automated fallback
verdict = verification.get("final_decision") or verification.get("decision")

if verdict == "approved":
    grant_access(user_id)
elif verdict == "needs_review":
    queue_for_manual_inspection(verification["id"])
else:
    reject_onboarding(user_id, reasons=verification.get("reasons", []))
```

---

## 3. Reason Code Catalog

When `decision` is `needs_review` or `rejected_recommended`, the `reasons` array lists the exact technical triggers:

### Hard Gate Mismatches (`rejected_recommended`)
- `id_details_name_mismatch`: Name extracted via OCR did not match expected user name within fuzzy token threshold (RapidFuzz &lt; 80%).
- `id_details_dob_mismatch`: Date of birth on document does not match ISO string.
- `id_details_last4_mismatch`: Government identifier does not match expected last 4 digits.
- `face_match_failed`: Cosine similarity between selfie and ID document crop is below 0.25.
- `otp_max_attempts_exceeded`: Phone or email verification OTP was entered incorrectly too many times.

### Soft Model Flags (`needs_review`)
- `face_match_borderline`: Cosine similarity falls between 0.25 and 0.40.
- `anti_spoof_flagged`: MiniFASNet passive anti-spoofing flagged potential paper or screen presentation attack.
- `video_deepfake_flagged`: ViT multi-frame classifier indicated elevated synthetic generation probability.
- `lip_sync_mismatch`: Mouth bounding box RMS displacement failed to synchronize with speech audio envelope during spoken challenge.
- `scene_integrity_multiple_faces`: Multiple distinct faces were detected simultaneously in the camera viewport.
- `scene_integrity_identity_switch`: Face bounding box in liveness stream departed significantly from the primary identity embedding.
- `voice_deepfake_flagged`: Detectif.ai Aletheia detected synthetic or cloned voice patterns in audio stream.
- `speaker_mismatch_flagged`: Detectif.ai Eidos detected a voiceprint deviation from the enrolled KYC reference.

---

## 4. Submitting a Human Review Override

Authorized reviewers can update the verdict using `POST /v1/verifications/{id}/review`:

```bash
curl -X POST http://localhost:8000/v1/verifications/ver_9a482b1c/review \
  -H "Authorization: Bearer kyc_live_..." \
  -H "Content-Type: application/json" \
  -d '{
    "decision": "approved",
    "note": "Verified tax ID records with municipal registry."
  }'
```
