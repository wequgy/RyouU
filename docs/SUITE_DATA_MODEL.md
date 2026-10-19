# Unclone Suite - Unified Data Model & Versioned Migrations

**Specification Version:** 2.0  
**Status:** Unified & Migration-Backed  
**Database Engines Supported:** SQLite (WAL mode) & PostgreSQL (Supabase / RDS)

---

## 1. Overview & Architectural Principle

The **Unclone Suite** provides an end-to-end identity integrity pipeline across two decoupled products:
1. **Unclone KYC (`services/api/app/kyc`)**: Asynchronous document OCR, active/passive 3D liveness challenges, and face embedding extraction.
2. **Unclone Interview Integrity (`services/api/app/interview` & `apps/overlay`)**: Real-time non-intrusive desktop overlay capturing candidate video and system loopback audio during live interviews (Zoom, Teams, Meet).

Both products can run standalone or share biometric ground truth:
```
+-----------------------------------------------------------------------------------+
|                                  TENANT ACCOUNT                                   |
|                          products: ["kyc", "interview"]                           |
+-----------------------------------------------------------------------------------+
                                         |
            +----------------------------+----------------------------+
            |                                                         |
            v                                                         v
+-----------------------+                                 +-----------------------+
|    KYC ONBOARDING     |                                 |   INTERVIEW OVERLAY   |
|  (/flow/{vid}/...)    |                                 | (/v1/interviews/...)  |
+-----------------------+                                 +-----------------------+
            |                                                         |
            | (Extracts Verified Face Vector)                         | (Queries Baseline)
            v                                                         v
+-----------------------------------------------------------------------------------+
|                            SHARED BIOMETRIC GROUND TRUTH                          |
|                                 biometric_baselines                               |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
                         Cross-Session Continuity & Anti-Fraud
                         - Impersonation Detection (Candidate != KYC)
                         - Proxy / Second Person Detection
                         - Deepfake & Voice Synthesis Flags
```

---

## 2. Versioned Migration Schema

All database tables are created and managed by the unified migration runner (`services/api/app/migrations/runner.py`) ensuring identical DDL behavior on both SQLite and PostgreSQL.

### Migration 0001: Shared Core & Product Foundations
- **`tenants`**: Multi-tenant isolation boundary.
  - `id` (VARCHAR PK): e.g., `demo_strict`, `tenant_apex`.
  - `name` (TEXT): Display name.
  - `api_key_hash` (TEXT): Legacy hashed API key.
  - `products` (TEXT/JSON): Enabled products, e.g. `["kyc", "interview"]`.
  - `webhook_url` (TEXT): Webhook callback endpoint.
  - `webhook_secret` (TEXT): HMAC payload signing secret.
  - `default_policy` (TEXT): `lenient`, `standard`, or `strict`.
  - `created_at` (DOUBLE): Unix timestamp.
- **`api_keys`**: Scoped, rotatable API keys (SHA-256 hashes only).
  - `id` (VARCHAR PK): e.g. `key_018f...`.
  - `tenant_id` (VARCHAR FK -> tenants.id).
  - `key_hash` (TEXT UNIQUE): SHA-256 hash.
  - `name` (TEXT): Display label.
  - `scopes` (TEXT/JSON): Scopes e.g. `["kyc:*", "interview:*", "admin:*"]`.
  - `created_at`, `expires_at`, `revoked_at` (DOUBLE).
- **`audit_log`**: Tamper-evident administrative audit trail.
  - `id` (VARCHAR PK).
  - `tenant_id` (VARCHAR).
  - `action` (TEXT), `actor` (TEXT), `details` (TEXT/JSON), `created_at` (DOUBLE).
- **`consent`**: GDPR/CCPA candidate biometric consent tracking.
  - `id` (VARCHAR PK).
  - `tenant_id`, `subject_id`, `consent_type`, `granted_at`, `revoked_at`.

### Migration 0002: Product Domain Tables
- **`verifications`** (KYC Product):
  - `id` (VARCHAR PK): Verification ID prefix `ver_`.
  - `tenant_id` (VARCHAR FK -> tenants.id).
  - `status` (TEXT): `created`, `submitted`, `processing`, `completed`, `reviewed`.
  - `decision` (TEXT): `approved`, `needs_review`, `rejected_recommended`.
  - `policy` (TEXT): Policy applied to verification.
  - `candidate_id` / `reference_id` (TEXT): Customer-supplied identifier.
  - `results` (TEXT/JSON): Individual check results (face, liveness, voice, OCR, injection).
  - `reasons` (TEXT/JSON): Human-readable decision rationales.
  - `trust` (DOUBLE): Weighted confidence score [0.0 - 1.0].
  - `review` (TEXT/JSON): Compliance officer review override.
- **`challenges`** (KYC Product):
  - Ephemeral, single-use liveness challenge prompts (blink, head turn, spoken phrase).
- **`verification_files`** (KYC Product):
  - Encrypted document photos, selfie frames, audio clips, and extraction metadata.
- **`interviews`** (Interview Product):
  - `id` (VARCHAR PK): Interview ID prefix `int_`.
  - `tenant_id` (VARCHAR FK -> tenants.id).
  - `candidate_name` (TEXT).
  - `status` (TEXT): `scheduled`, `active`, `completed`.
  - `overall_risk` (TEXT): `low`, `medium`, `high`.
- **`interview_clips`** (Interview Product):
  - Streamed 5-second video/audio segments analyzed for deepfakes, lipsync, and voice cloning.
- **`biometric_baselines`** (Shared Bridge):
  - `id` (VARCHAR PK).
  - `tenant_id` (VARCHAR).
  - `candidate_id` / `reference_id` (TEXT).
  - `face_embedding` (TEXT/JSON): 512-dimensional ArcFace vector.
  - `voiceprint` (TEXT/JSON): Speaker embedding vector.
  - `source_verification_id` (VARCHAR FK -> verifications.id).

### Migration 0003: Performance & Security Indexes
- Indexes on `tenants.api_key_hash`, `api_keys.key_hash`, `verifications.tenant_id`, `interviews.tenant_id`, and `biometric_baselines(tenant_id, candidate_id)`.
