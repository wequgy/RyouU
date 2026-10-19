---
title: Human in the Loop
description: How RyouU balances automated fraud detection with human review, overriding recommendations, and preserving audit logs.
---

Automated machine learning models are fundamentally probabilistic. Deepfake detection, acoustic voice analysis, and anti-spoofing can misclassify legitimate users with unusual lighting, accents, or camera hardware.

RyouU is architected around a strict principle: **The machine flags and explains; a human decides.**

---

## 1. The Human Review Workflow

```
+-------------------------------------------------------------+
|                     AUTOMATED PIPELINE                      |
|  - ID OCR Match                                             |
|  - Face Cosine Similarity                                   |
|  - Passive Anti-Spoofing PAD                                |
|  - Visual Deepfake ViT                                      |
+------------------------------+------------------------------+
                               |
                               v
            +-------------------------------------+
            |  Autonomous State: "needs_review"   |
            +------------------+------------------+
                               |
                               v
+-------------------------------------------------------------+
|                  HUMAN COMPLIANCE OFFICER                   |
|  - Inspects high-resolution ID document photos              |
|  - Reviews recorded liveness and challenge video clips      |
|  - Reads machine reason tags (e.g. "anti_spoof_uncalibrated")|
|  - Submits final decision: "approved" or "rejected"         |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|                       IMMUTABLE AUDIT                       |
|  - final_decision recorded                                  |
|  - Reviewer ID, timestamp, and explanation note stored      |
|  - Signed webhook dispatched to customer backend            |
+-------------------------------------------------------------+
```

---

## 2. Overriding Recommendations via API

Compliance officers or internal workflow tools can submit a manual review via `POST /v1/verifications/{id}/review`:

```bash
curl -X POST http://localhost:8000/v1/verifications/ver_9a482b1c/review \
  -H "Authorization: Bearer kyc_live_..." \
  -H "Content-Type: application/json" \
  -d '{
    "decision": "approved",
    "note": "Document photo verified manually. Low lighting caused passive anti-spoof flag."
  }'
```

### Audit Payload

The review submission is stored immutably with the verification record:

```json
{
  "id": "ver_9a482b1c",
  "status": "completed",
  "decision": "needs_review",
  "final_decision": "approved",
  "review": {
    "reviewer_id": "compliance_officer_02",
    "decision": "approved",
    "note": "Document photo verified manually. Low lighting caused passive anti-spoof flag.",
    "reviewed_at": "2026-10-19T14:32:10Z"
  }
}
```
