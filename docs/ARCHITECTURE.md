# Unclone Suite - System Architecture & Security Model

## 1. Executive Architecture Overview

Unclone is a hardened, modular identity integrity suite providing two products:
1. **Unclone KYC**: Asynchronous document OCR, active/passive 3D liveness detection, and facial biometric verification.
2. **Unclone Interview Integrity**: Real-time non-intrusive desktop overlay monitoring video, facial continuity, and synthetic voice detection during live interviews.

Both products can be purchased, deployed, and run **standalone** or **together** in a unified pipeline.

```
                                  +-------------------------------------------------------+
                                  |                 CUSTOMER INFRASTRUCTURE               |
                                  |                                                       |
                                  |  +--------------------+         +------------------+  |
                                  |  |  Customer Backend  | <=====> | Dashboard / Web  |  |
                                  |  |   (Fintech / ATS)  |         |   (HR / Admin)   |  |
                                  +--+---------+----------+---------+--------+---------+--+
                                               |                             |
                       Holds: TENANT_API_KEY   |                             | Mints Short-Lived
                       Scopes: kyc:*, interview:* |                           | Interview Token
                                               v                             v
+---------------------------------------------------------------------------------------------------+
|                                      UNCLONE CORE API SERVICE                                     |
|                                         (FastAPI Gateway)                                         |
|                                                                                                   |
|  +---------------------------------------------------------------------------------------------+  |
|  |  Security & Access Control Middleware                                                       |  |
|  |  - Tenant Authentication & Scope Enforcement (kyc:*, interview:*, admin:*)                   |  |
|  |  - Product Licensing Gate (ENABLE_KYC, ENABLE_INTERVIEW, Tenant.products)                   |  |
|  |  - Interceptor: Overlay Token rejected by /v1/verifications and /flow                       |  |
|  +---------------------------------------------------------------------------------------------+  |
|                                               |                                                   |
|                      +------------------------+------------------------+                          |
|                      |                                                 |                          |
|                      v                                                 v                          |
|       +------------------------------+                  +------------------------------+          |
|       |         KYC PRODUCT          |                  |      INTERVIEW PRODUCT       |          |
|       | (/v1/verifications, /flow)   |                  |       (/v1/interviews)       |          |
|       +--------------+---------------+                  +--------------+---------------+          |
|                      |                                                 |                          |
|                      v                                                 v                          |
|  +---------------------------------------+      +----------------------------------------------+  |
|  | Local / In-Process KYC Workers        |      | Local / In-Process Interview Workers         |  |
|  | - InsightFace (buffalo_l ArcFace)     |      | - MediaPipe 3D Mesh / Blink Landmark         |  |
|  | - MiniFASNet v2 (Anti-Spoofing)       |      | - ViT Deepfake / GenD Detection              |  |
|  | - MediaPipe Blendshapes (Liveness)    |      | - SyncNet Lip-Sync Audio/Video Evaluator     |  |
|  | - RapidOCR ONNX (Document parsing)    |      | - Detectif.ai Voice AI Authenticity          |  |
|  | - Faster-Whisper (Spoken details)     |      +----------------------------------------------+  |
|  +---------------------------------------+                             |                          |
|                      |                                                 |                          |
|                      +------------------------+------------------------+                          |
|                                               |                                                   |
|                                               v                                                   |
|  +---------------------------------------------------------------------------------------------+  |
|  |  Unified Repository & Database Layer (Postgres / SQLite Migrations)                         |  |
|  |  - Core: tenants, api_keys, audit_log, consent                                              |  |
|  |  - KYC: verifications, verification_files, challenges                                       |  |
|  |  - Interview: interviews, interview_clips, biometric_baselines                              |  |
|  +---------------------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------------------+
             ^                                                                 ^
             | Single-Use Flow Token                                           | Scoped Token
             | (flow_tok_...)                                                  | (interview:*)
             |                                                                 |
   +---------+-----------+                                           +---------+-----------+
   |   KYC CLIENT APPS   |                                           |   UNCLONE OVERLAY   |
   | - Web / Hosted Flow |                                           |   (Desktop Electron)|
   | - Mobile SDKs       |                                           |                     |
   |   (Android/iOS/RN)  |                                           | Stores: safeStorage |
   |                     |                                           | Refresh: Auto-timer |
   +---------------------+                                           +---------------------+
```

---

## 2. Secrets Management & Separation of Concerns

Security Rule: **No product (overlay, SDKs, hosted page) ever holds a database key or a Supabase key. The API is the only door to the data.**

| Component | Secrets Held | Secrets Explicitly Forbidden | Storage / Transport |
| :--- | :--- | :--- | :--- |
| **Customer Backend** | `TENANT_API_KEY` (Scoped `kyc:*`, `interview:*`) | Database master keys, customer biometric vectors | Environment variables (`.env`), Secrets Manager |
| **Unclone API Service** | `DATABASE_URL`, `DETECTIF_API_KEY`, `WEBHOOK_SECRET` | None (API is the authority) | Environment variables, encrypted config |
| **Database (Postgres / Supabase)** | Master database connection credentials | Direct network exposure to clients | Behind VPC / firewall, accessible ONLY to API |
| **Unclone Overlay (Desktop App)** | Short-lived scoped token (`interview:*`), TTL 1 hour | `TENANT_API_KEY`, Database keys, Supabase keys | Electron `safeStorage` (OS-level DPAPI/Keytar), refreshed automatically |
| **KYC SDKs (iOS, Android, React Native)** | Ephemeral flow token (`flow_tok_...`), TTL 30 mins | `TENANT_API_KEY`, Interview tokens, DB keys | In-memory session state |
| **Hosted Verification Web Page** | Single-use session token | Any persistent credential | In-memory URL token parameter |

---

## 3. Product Decoupling & Scoped Permissions

### Product Flags
- `ENABLE_KYC=true|false`: Controls whether KYC routes (`/v1/verifications`, `/flow`, `/v1/policies`, `/v1/reviews`) and KYC models (`InsightFace`, `MediaPipe FaceLandmarker`, `MiniFASNet`, `RapidOCR`, `Whisper`) are mounted and loaded.
- `ENABLE_INTERVIEW=true|false`: Controls whether Interview routes (`/v1/interviews`) and Interview models (`ViT Deepfake`, `SyncNet`, `Detectif.ai`) are mounted and loaded.

### Scoped API Keys
Tenant API keys are hashed with SHA-256 before storage in `api_keys`. They carry scopes:
- `kyc:*`: Grants access to KYC verification creation, status, and reviews.
- `interview:*`: Grants access to interview session creation, clip uploads, and analysis.
- `admin:*`: Grants tenant admin functions (API key minting, rotation, revocation).

### Standalone Interview Mode
When a customer uses Interview Integrity without KYC:
- An interview session is initiated without a `reference_id` or `candidate_id` linked to KYC.
- The overlay UI displays: `No KYC baseline`.
- The interview functions independently: detecting voice deepfakes, video injection, and facial continuity across clips.

---

## 4. Platform Compatibility & Meeting Detection

The Unclone Overlay monitors active meeting windows (Zoom, Microsoft Teams, Google Meet, Webex) to synchronize recording:

| Platform | Detection Mechanism | Status | Notes |
| :--- | :--- | :--- | :--- |
| **Windows** | Win32 Window Title & Process Enumeration via PowerShell (`Get-Process`) | **VERIFIED & TESTED** | Detects `Zoom.exe`, `Teams.exe`, and browser titles matching `Meet - `, `Zoom Workplace` |
| **macOS** | AppleScript / Quartz Window Services | **UNTESTED** | Native binding stubbed; marked UNTESTED in this release |
| **Linux** | `xdotool` / `wmctrl` X11 Window Property queries | **UNTESTED** | Native binding stubbed; marked UNTESTED in this release |

---

## 5. Model Inference & Runtime Workers

All models run free, pretrained open weights (no custom training required):

- **InsightFace (`buffalo_l`)**: SCRFD face detection, 512-dim ArcFace embedding, 3D head pose estimation. *(Non-commercial research notice applies)*.
- **MediaPipe Face Mesh (`face_landmarker.task`)**: 478 3D landmarks + 52 real-time FACS blendshapes for active eye blink and head turn liveness.
- **MiniFASNet v2 (`minifasnet_v2.onnx`)**: Silent-Face anti-spoofing classifying physical screens, printed paper, and replay attacks.
- **RapidOCR (`onnxruntime`)**: Server-side document text recognition for ID name and date-of-birth extraction.
- **Faster-Whisper (`base.en`)**: Automatic speech recognition validating spoken challenge phrases.
- **ViT Deepfake Detector (`prithivMLmods/Deep-Fake-Detector-v2-Model`)**: Vision Transformer analyzing candidate video frames for generative artifacts.
- **SyncNet Python**: Audio-to-video lip synchronization assessing candidate speech correlation.
- **Detectif.ai**: External zero-shot synthetic voice authenticity API.
