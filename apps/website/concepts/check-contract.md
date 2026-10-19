---
title: Check Contract & Results
description: The four-state result contract (pass, fail, uncertain, skipped) and signal isolation.
---

Every individual check executed during verification conforms to a strict four-state result contract. This contract prevents transient errors or missing data from accidentally passing fraudulent attempts.

---

## 1. The Four-State Result Contract

```typescript
type CheckStatus = 'pass' | 'fail' | 'uncertain' | 'skipped';

interface CheckResult {
  status: CheckStatus;
  score?: number;          // Continuous score between 0.0 and 1.0
  threshold?: number;      // Calibrated or baseline threshold
  reasons: string[];       // Machine-readable diagnostic tags
  diagnostics?: Record<string, unknown>;
}
```

### State Semantics

| Status | Meaning | Autonomous Decision Impact |
| :--- | :--- | :--- |
| **`pass`** | Check executed completely and met or exceeded the passing threshold. | Eligible for `approved`. |
| **`fail`** | Check executed completely and unambiguously violated a hard requirement (e.g. name mismatch or face cosine &lt; 0.25). | Pushes verification to **`rejected_recommended`**. |
| **`uncertain`** | Check encountered insufficient data, runtime timeouts, model inference failure, or soft anomaly signals. | Pushes verification to **`needs_review`**. **NEVER passes.** |
| **`skipped`** | Check was not evaluated because policy did not require it or prerequisites were not met. | Neutral; does not block approval if non-mandatory. |

---

## 2. Strict Error Semantics

> [!IMPORTANT]
> **A check that encounters an error or lacks input frames MUST return `uncertain`, never `pass`.**
> Silent fallbacks (`except Exception: pass`) are strictly forbidden across all RyouU pipelines.

If a neural model fails to initialize, if network connection to Detectif.ai drops, or if lighting prevents face detection, the check returns:
```json
{
  "status": "uncertain",
  "score": null,
  "reasons": ["face_not_detected", "inference_timeout"],
  "diagnostics": {
    "error": "Timeout after 15000ms waiting for face landmarks"
  }
}
```

---

## 3. Signal Isolation Architecture

Signals are divided into two fundamental classes:

1. **Hard Gates**:
   - `id_details`: OCR name, date of birth, and ID number comparison.
   - `face_match`: 512-dimensional ArcFace cosine similarity.
   - `otp_gate`: SMS or email one-time passcode confirmation.
   *Only Hard Gates can trigger `rejected_recommended`.*

2. **Soft Probabilistic Signals**:
   - `anti_spoof`: Passive print/screen attack scoring.
   - `video_deepfake`: Synthetic image classification.
   - `lip_sync`: Spoken challenge audio-visual synchronization.
   - `voice_ai`: Synthetic voice detection.
   *Soft signals can only elevate verification to `needs_review`.*
