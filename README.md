# Unclone KYC Verification Service (Backend)

A production-quality multi-tenant identity verification API: a customer's backend creates a session, their user completes a verification flow (hosted page at `/flow`), and a signed webhook delivers the result. Checks are pluggable modules.

```
customer backend --POST /v1/verifications--> API --> flow_url --> end user (hosted page /flow in WebView)
end user --/flow/* (uploads, OTP, signals, challenges, submit)--> API --> background pipeline
pipeline: run checks in parallel -> decision engine (per-tenant policy) -> save -> signed webhook
customer: GET /v1/verifications/{id}, human review via POST .../review, evidence via GET .../evidence
```

## Quickstart

### Local Setup
```bash
python -m venv .venv
source .venv/bin/activate       # On Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt          # core + dev tools
pip install -r requirements-ml.txt           # optional: InsightFace, Whisper

# Set environment
cp .env.example .env

# Run API server
uvicorn app.main:app --port 8000 --reload    # docs at http://localhost:8000/docs
# Run test suite
python -m pytest tests -q
```

### Docker & Docker Compose
```bash
# Run API with optional PostgreSQL backend
docker-compose up --build
```

Demo tenants (seeded when `KYC_SEED_DEMO=1`):
- `kyc_demo_lenient_key` (lenient policy)
- `kyc_demo_strict_key` (strict policy)

---

## API Endpoints

### 1. Customer API (`Authorization: Bearer <api_key>`)

- `POST /v1/verifications`
  - Create a new verification session.
  - Supports `Idempotency-Key` header to safely retry requests without double-creation.
  - Body: `{"reference_id": "...", "policy": "strict|lenient", "expected": {"name": "...", "dob": "...", "id_last4": "..."}}`
  - Returns: `{"id": "...", "status": "created", "policy": "...", "flow_url": "https://.../flow?v=...&t=..."}`

- `GET /v1/verifications`
  - List verifications for the authenticated tenant with pagination (`?limit=50`).

- `GET /v1/verifications/{id}`
  - Fetch verification status and decision.
  - Returns: `id`, `reference_id`, `status`, `policy`, `decision`, `final_decision`, `trust`, `reasons`, `results`, `review`, `webhook`.
  - Notice: No sensitive customer PII is leaked in this endpoint.

- `GET /v1/verifications/{id}/evidence`
  - Returns a manifest of expiring signed download URLs for all encrypted evidence artifacts.

- `GET /v1/verifications/{id}/evidence/{kind}`
  - Download decrypted evidence artifact (e.g. `selfie`, `id_image`, `challenge_video`, `challenge_audio`).
  - Authorized via `?token=<signed_token>` or tenant `Bearer <api_key>`.

- `POST /v1/verifications/{id}/review`
  - Human reviewer override (`{"decision": "approved|rejected", "note": "..."}`).

- `DELETE /v1/verifications/{id}`
  - Deletes database records and purges encrypted upload files from disk.

- `GET /v1/policies`
  - List available policies (`lenient`, `strict`).

- `POST /v1/tenant/rotate-key`
  - Rotate the tenant's API key. Returns new live key; only its SHA-256 hash is retained in DB.

- `POST /v1/tenant/rotate-webhook-secret`
  - Rotate the tenant's webhook HMAC signing secret.

- `PATCH /v1/tenant/webhook`
  - Update tenant webhook endpoint URL (`{"webhook_url": "https://..."}`).

---

### 2. End-User Flow API (`X-Flow-Token: <token>`)

- `GET /flow`
  - Hosted verification UI page rendered in a secure WebView or browser.
- `GET /flow/{id}/context`
  - Fetch session configuration and required steps.
- `POST /flow/{id}/otp/send` & `POST /flow/{id}/otp/verify`
  - Send and verify OTP codes for email and phone.
- `POST /flow/{id}/upload/{kind}`
  - Secure upload encrypted at rest (`id_image`, `selfie`, `challenge_audio`, `phrase_audio`, `spoken_name`, `spoken_dob`, `spoken_id_last4`, `challenge_video`).
- `POST /flow/{id}/signals`
  - Client device and environment fraud signals.
- `POST /flow/{id}/challenges` & `POST /flow/{id}/challenges/result`
  - Interactive replay-proof liveness challenges.
- `POST /flow/{id}/submit`
  - Atomically claims the session and enqueues a durable background processing job.

---

## Webhooks

Webhooks deliver completion and review events with an HMAC-SHA256 signature in the `X-KYC-Signature` header:
```
X-KYC-Signature: t=<unix_timestamp>,v1=<hex_hmac>
```
Verify the signature using `verify_signature(secret, raw_body, header, tolerance_s=300)`.

Webhook attempts are retried with exponential backoff and logged in the database table `webhook_deliveries`.

---

## Storage & Security

- **Encryption at Rest**: Uploaded evidence is encrypted on disk using Fernet (AES-128-CBC + HMAC). Set `KYC_ENCRYPTION_KEY` or rely on the persistent key generated in `KYC_DATA_DIR`.
- **Database**: Default SQLite with WAL mode; optional PostgreSQL via `DATABASE_URL=postgresql://...`.
- **Durability**: Pipeline jobs survive server restarts via the `pipeline_jobs` table.
- **Pluggable SMS Provider**: Pluggable `SmsProvider` interface (`MockSmsProvider`, `Fast2SmsProvider`, `TwilioSmsProvider`, `EmailBridgeSmsProvider`).

---

## License Notice
Licensed under the MIT License. Note that InsightFace `buffalo_l` model weights are licensed for non-commercial research purposes only.
