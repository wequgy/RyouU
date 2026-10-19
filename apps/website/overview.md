---
title: Overview & Architecture
description: Comprehensive architecture of RyouU identity verification and live interview monitoring suite.
---

RyouU provides a **layered, server-enforced, human-in-the-loop** identity integrity suite spanning two modular products:

1. **KYC Verification Suite**: Document OCR, passive screen/print anti-spoofing, active 3D face liveness, spoken challenge ASR, and facial biometric matching.
2. **Interview Integrity Overlay**: Real-time non-intrusive desktop HUD for technical interviews, monitoring visual deepfakes, synthetic voice clones, multiple faces, and stream loop/virtual cameras.

```
+-------------------------------------------------------------------------+
|                        CUSTOMER BACKEND SERVICE                         |
|  - Holds Tenant API Key (kyc:*, interview:*, admin:*)                   |
|  - Creates KYC sessions (/v1/verifications)                             |
|  - Mints short-lived interviewer tokens (/v1/interviews/{id}/token)     |
|  - Receives and verifies signed HMAC webhooks                           |
+------------------------------------+------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|                        RYOUU CORE API GATEWAY                           |
|  - Product Licensing Gates (ENABLE_KYC, ENABLE_INTERVIEW)               |
|  - Scoped API key & session auth (Argon2, CSRF protection, rate limits) |
|  - Server-side state machine (draft -> in_progress -> completed)         |
+-------------------+---------------------------------+-------------------+
                    |                                 |
                    v                                 v
+-------------------------------+ +---------------------------------------+
|          KYC PRODUCT          | |           INTERVIEW PRODUCT           |
|  - Hosted web UI (/flow)      | |  - Real-time overlay HUD (Electron)   |
|  - Mobile SDKs (Android / RN) | |  - Background loopback audio capture  |
|  - Evidence encryption        | |  - Multi-round clip verification      |
+---------------+---------------+ +-------------------+-------------------+
                |                                     |
                v                                     v
+-------------------------------+ +---------------------------------------+
|       LOCAL KYC WORKERS       | |       LOCAL INTERVIEW WORKERS         |
|  - InsightFace (buffalo_l)    | |  - ViT Deepfake / GenD detector       |
|  - MiniFASNet v2 (anti-spoof) | |  - SyncNet Python (lip-sync)          |
|  - MediaPipe FaceLandmarker   | |  - Detectif.ai Voice Authenticity     |
|  - RapidOCR (ONNX)            | |  - Virtual Camera & loop detection    |
|  - Faster-Whisper (ASR)       | |                                       |
+-------------------------------+ +---------------------------------------+
```

## Security Rule: Separation of Concerns

> [!IMPORTANT]
> **No product client (overlay, mobile SDK, hosted flow page) ever holds a database key or customer tenant API key.**
> The RyouU API gateway is the only door to the data.

| Component | Credentials Held | Forbidden Credentials | Storage / Transport |
| :--- | :--- | :--- | :--- |
| **Customer Backend** | `KYC_API_KEY` (Scoped `kyc:*`, `interview:*`) | Database master passwords | Secure environment variables |
| **RyouU API Service** | `DATABASE_URL`, `DETECTIF_API_KEY` | None (Server authority) | Encrypted server environment |
| **Desktop Overlay** | Short-lived interviewer token (`itok_...`), TTL 1 hr | Tenant API keys, provider keys | OS `safeStorage` (DPAPI/Keytar) |
| **Mobile SDKs** | Ephemeral flow token (`flow_tok_...`), TTL 30 min | Tenant API keys, DB credentials | In-memory session state |
| **Hosted Flow Page** | Single-use session token | Any persistent credential | In-memory ephemeral URL state |
