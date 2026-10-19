---
title: REST API Reference
description: Complete REST API endpoint reference generated from OpenAPI 3.1.0 specifications.
---

The RyouU API Gateway exposes RESTful endpoints for verification lifecycle management, evidence retrieval, reviewer audits, and interview monitoring.

---

## 1. System Health

### `GET /healthz`
Basic container liveness probe.
- **Response `200`**: `{"status": "ok"}`

### `GET /readyz`
Kubernetes readiness probe. Checks database connectivity and loaded ONNX neural models.
- **Response `200`**: `{"status": "ready", "database": "connected", "models_loaded": true}`
- **Response `503`**: Returned if database is unreachable or models are still loading.

---

## 2. Verifications

### `POST /v1/verifications`
Creates a new identity verification session and generates a scoped `flow_url`.

- **Headers**:
  - `Authorization: Bearer <KYC_API_KEY>` (Required)
  - `Idempotency-Key: <string>` (Optional, recommended)
- **Request Body**:
```json
{
  "reference_id": "usr_98412",
  "expected": {
    "name": "Alex Morgan",
    "dob": "1995-08-20",
    "id_last4": "4821",
    "email": "alex@example.com",
    "phone": "+15551234567"
  },
  "policy": "strict",
  "idempotency_key": "tx_req_001"
}
```
- **Response `201`**:
```json
{
  "id": "ver_8a92f0bc",
  "reference_id": "usr_98412",
  "status": "draft",
  "flow_url": "https://api.yourfintech.com/flow/ver_8a92f0bc?token=flow_tok_4a...",
  "created_at": "2026-10-19T14:00:00Z"
}
```

### `GET /v1/verifications/{id}`
Retrieves verification state, execution status, autonomous recommendation, and human review overrides.

- **Headers**: `Authorization: Bearer <KYC_API_KEY>`
- **Response `200`**:
```json
{
  "id": "ver_8a92f0bc",
  "reference_id": "usr_98412",
  "status": "completed",
  "decision": "approved",
  "final_decision": null,
  "trust": 0.94,
  "reasons": [],
  "checks": {
    "id_details": { "status": "pass", "score": 0.96 },
    "face_match": { "status": "pass", "score": 0.78, "threshold": 0.40 },
    "liveness": { "status": "pass", "reasons": ["blink_verified", "yaw_verified"] },
    "anti_spoof": { "status": "pass", "score": 0.12, "threshold": 0.50 }
  },
  "created_at": "2026-10-19T14:00:00Z",
  "completed_at": "2026-10-19T14:02:15Z"
}
```

### `POST /v1/verifications/{id}/review`
Submits a compliance reviewer override decision.

- **Headers**: `Authorization: Bearer <KYC_API_KEY>`
- **Request Body**:
```json
{
  "decision": "approved",
  "note": "Physically inspected original passport in regional branch."
}
```
- **Response `200`**:
```json
{
  "id": "ver_8a92f0bc",
  "final_decision": "approved",
  "review": {
    "reviewer_id": "usr_compliance_02",
    "decision": "approved",
    "note": "Physically inspected original passport in regional branch.",
    "reviewed_at": "2026-10-19T14:30:00Z"
  }
}
```

### `GET /v1/verifications/{id}/evidence`
Lists available captured biometric and document evidence artifacts.

### `GET /v1/verifications/{id}/evidence/{kind}`
Streams the binary payload of an encrypted evidence artifact (`id_front`, `id_back`, `selfie`, `video_liveness`, `audio_challenge`).

---

## 3. Interview Overlay Sessions

### `POST /v1/interviews`
Creates a monitored interview session and mints an interviewer token (`itok_...`).

- **Headers**: `Authorization: Bearer <KYC_API_KEY>`
- **Request Body**:
```json
{
  "candidate_id": "candidate-001",
  "interviewer_id": "lead_eng_01",
  "meeting_platform": "zoom"
}
```
- **Response `201`**:
```json
{
  "id": "int_7a8109bf",
  "token": "itok_8402bc11...",
  "candidate_id": "candidate-001",
  "expires_at": "2026-10-19T16:00:00Z"
}
```

### `POST /v1/interviews/{id}/clips`
Uploads a 25-second video/audio clip from the interviewer HUD for asynchronous analysis.

### `GET /v1/interviews/{id}/summary`
Fetches the cumulative anomaly count and real-time status pills for the session.

### `POST /v1/interviews/{id}/end`
Terminates the monitoring session and revokes the interviewer token.
