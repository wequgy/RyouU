---
title: Idempotency & Error Handling
description: Using idempotency keys for safe API retries and handling standard HTTP error responses.
---

Network hiccups and mobile reconnects can interrupt in-flight requests. RyouU supports idempotency keys on mutating endpoints to ensure operations can be retried safely without duplicating sessions or charges.

---

## 1. Using Idempotency Keys

Include the `Idempotency-Key` HTTP header (or `idempotency_key` in the JSON body) when calling `POST /v1/verifications`:

```bash
curl -X POST http://localhost:8000/v1/verifications \
  -H "Authorization: Bearer kyc_live_..." \
  -H "Idempotency-Key: req_payment_94021_attempt_1" \
  -H "Content-Type: application/json" \
  -d '{
    "reference_id": "usr_94021",
    "expected": {"name": "Alex Morgan"}
  }'
```

If you re-send the exact request with the same key within 24 hours:
- RyouU does not create a duplicate verification session.
- It returns the original cached response with identical status codes and session IDs.

---

## 2. Standard Error Responses

Errors conform to RFC 7807 Problem Details:

```json
{
  "error": "invalid_request",
  "message": "Missing required field: expected.name",
  "status_code": 422,
  "request_id": "req_8402bc11"
}
```

| HTTP Status | Error Code | Common Cause |
| :--- | :--- | :--- |
| **`400`** | `bad_request` | Malformed JSON or unparseable input parameters. |
| **`401`** | `unauthorized` | Missing or invalid Bearer token. |
| **`403`** | `forbidden` | API key lacks required scope (e.g. key has `kyc:read` but calls write route). |
| **`404`** | `not_found` | Verification ID or interview session does not exist. |
| **`409`** | `conflict` | Idempotency key reused with different request payload parameters. |
| **`429`** | `rate_limit_exceeded` | Tenant exceeded configured request rate limits (default: 120 req/min). |
| **`500`** | `internal_error` | Unhandled server exception. Diagnostics recorded with `request_id`. |
