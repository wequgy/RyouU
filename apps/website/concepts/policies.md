---
title: Policies & Gates
description: Configuring verification policies, gate prerequisites, and custom threshold profiles.
---

RyouU enables organizations to tune fraud sensitivity and onboarding friction through declarative verification policies.

---

## 1. Built-in Policy Profiles

When creating a verification session, pass the `policy` parameter:

```python
session = client.create_verification(
    reference_id="usr_102",
    expected={"name": "Alex Morgan"},
    policy="strict" # "strict" or "lenient"
)
```

| Check / Signal | `strict` Policy | `lenient` Policy |
| :--- | :--- | :--- |
| **Document OCR Match** | RapidFuzz &ge; 85%, exact DOB, last 4 digits | RapidFuzz &ge; 75%, fuzzy DOB |
| **Face Cosine Threshold** | Pass &ge; 0.45, Fail &lt; 0.30 | Pass &ge; 0.38, Fail &lt; 0.22 |
| **Active Liveness** | Directed yaw turn + voluntary blink | Voluntary blink only |
| **Anti-Spoofing PAD** | Enabled (Flag &gt; 0.40) | Enabled (Flag &gt; 0.65) |
| **Spoken Challenge** | Spontaneous phrase ASR + Lip-sync | Skipped |
| **SMS OTP Gate** | Mandatory gate before document upload | Optional |

---

## 2. Gate Prerequisites & Sequencing

Verification stages execute in a deterministic, server-enforced sequence. The hosted flow enforces that each gate is validated before subsequent endpoints accept data:

1. **Gate 1: Contact Verification (OTP)**  
   The candidate receives an SMS or Email OTP. The API validates the code before unlocking document upload routes.
2. **Gate 2: Government ID Capture**  
   The candidate uploads front and back photos. RapidOCR executes immediately, checking for document corners, blur, and minimum text box count (&ge; 2).
3. **Gate 3: Active Liveness Challenge**  
   MediaPipe tracks real-time blendshapes. The candidate is prompted with randomized gestures (e.g. "turn head slightly left", "blink twice").
4. **Gate 4: Spoken Challenge & Voiceprint**  
   The candidate speaks a dynamic 4-word prompt. Whisper transcribes the phrase for accuracy; SyncNet verifies mouth motion matches audio.
5. **Final Evaluation**  
   The server compiles all signals into a consolidated decision and dispatches the signed webhook.
