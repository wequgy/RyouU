# KYC Verification Service (backend)

A multi-tenant verification API: a customer's backend creates a session, their user completes a flow
(hosted page, built separately), and a signed webhook delivers the result. Checks are plug-in modules.

```
customer backend --POST /v1/verifications--> API --> flow_url --> end user (verification page)
end user --/flow/* (uploads, OTP, signals, challenges, submit)--> API --> background pipeline
pipeline: run checks in parallel -> decision engine (per-tenant policy) -> save -> signed webhook
customer: GET /v1/verifications/{id}, human review via POST .../review
```

## Run it
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt          # core + tests
pip install -r requirements-ml.txt           # optional: InsightFace, Whisper (heavy)
cp .env.example .env && set -a && source .env && set +a

uvicorn app.main:app --port 8000             # the service (docs at /docs)
uvicorn demo_client.app:app --port 9000      # the fake customer ("FakeBank") receiving webhooks
python -m scripts.e2e_demo --key kyc_demo_strict_key     # drive a full verification
python -m pytest tests -q                    # 47 tests
```
Demo tenants (seeded when KYC_SEED_DEMO=1): `kyc_demo_lenient_key`, `kyc_demo_strict_key`.
Without the ML packages the face and Whisper checks return `uncertain` (never `pass`).

## Endpoints
Customer API (`Authorization: Bearer <key>`):
`POST /v1/verifications`, `GET /v1/verifications[/{id}]`, `POST /v1/verifications/{id}/review`,
`DELETE /v1/verifications/{id}`, `GET /v1/policies`.

End-user flow API (`X-Flow-Token`, token is in the flow_url):
`GET /flow/{id}/context` (which steps to show), `POST .../otp/send|verify`, `POST .../upload/{kind}`
(id_image, selfie, challenge_audio, phrase_audio, spoken_name, spoken_dob, spoken_id_last4),
`POST .../signals`, `POST .../challenges` + `.../challenges/result`, `POST .../submit`.

Webhook: `X-KYC-Signature: t=<unix>,v1=<hmac_sha256("<t>.<body>")>`. Verify with `app.security.verify_signature`.

## Checks (`app/checks/`)
| Check | Implementation | Status |
|---|---|---|
| face_match | InsightFace buffalo_l (non-commercial weights) | real, needs `requirements-ml.txt` + threshold calibration |
| email_otp / phone_otp | hashed, expiring, single-use, attempt- and send-limited | real; phone uses a console mock sender |
| voice_ai | Detectif `/v1/deepfake/detect` | real HTTP client, mocked in tests, not run against the live API yet |
| spoken_details | faster-whisper + rapidfuzz + date/digit normalisation | real, needs ML install |
| liveness | server-issued random challenges, replay-proof, time-limited | real logic; metrics are client-supplied (untrusted) |
| source_checks | virtual-camera names, screen share, focus loss, extra display | real, from untrusted client signals |
| video_deepfake | stub, returns `uncertain` | TODO (CLIP-based head) |

Result contract (`app/models.py::CheckResult`): `name, status(pass|fail|uncertain|skipped), score (trust, 1=genuine),
confidence, reason, details`.

## Decisions (`app/policies.py`, `app/pipeline.py::decide`)
`approved` / `needs_review` / `rejected_recommended` (always a recommendation; a human can override via /review).
Per policy: `reject_on_fail` (FAIL -> rejected_recommended), `must_pass` (anything but PASS -> needs_review),
`max_uncertain_required` (how many other required checks may be uncertain). A crashing or missing check
becomes `uncertain`, never `pass`. A customer-side webhook outage never changes the verdict.

## Before you rely on it
1. **Calibrate face thresholds** (`FACE_PASS_SIM` / `FACE_FAIL_SIM` are placeholders): `python -m scripts.face_cli id.jpg selfie1.jpg other_person.jpg`.
2. **Test Detectif early**: `python -m scripts.detectif_cli clip.wav`. Try a 3 s clip (their docs disagree on minimum length), a real recording, a cloned one, phone-quality audio.
3. **Dev mode** (`KYC_DEV_MODE=1`) echoes OTP codes and accepts client transcripts. Never enable it in production.
4. Liveness metrics and source signals come from the browser and can be forged. For production, recompute from uploaded frames server-side.

## Not built yet
Verification page and dashboard (frontend), ID OCR (tenant supplies `expected` for now), video deepfake model,
Idempotency-Key on create, rate limiting, per-tenant policy editing API, speaker consistency via Detectif
enroll/verify, real SMS provider (India needs DLT registration), Postgres, encryption of stored uploads,
retention jobs, audit log. Compliance (RBI V-CIP, DPDP) needs legal review before any real deployment.
