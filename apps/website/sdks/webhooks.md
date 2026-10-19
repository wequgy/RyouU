---
title: Webhooks & Signature Verification
description: Cryptographic HMAC-SHA256 signature scheme, headers, timestamp replay tolerance, and retry policies.
---

RyouU delivers asynchronous event notifications via signed HTTP POST requests to your configured webhook URL.

---

## 1. Webhook Headers

Every outbound webhook includes the following headers:

| Header | Example | Description |
| :--- | :--- | :--- |
| **`Content-Type`** | `application/json` | JSON serialized event body. |
| **`X-KYC-Signature`** | `t=1729352400,v1=5d41402abc4b...` | Timestamped HMAC-SHA256 signature. |
| **`X-KYC-Event-Id`** | `evt_8a92f0bc` | Unique identifier for deduplication. |

---

## 2. Signature Verification Scheme

The signature is computed over the concatenated string:
```text
t=<timestamp>.<raw_request_body_bytes>
```
Using your tenant `whsec_...` webhook secret with `HMAC-SHA256`.

### Manual Verification Algorithm

1. Extract `t` and `v1` from the `X-KYC-Signature` header.
2. Verify that `|current_time - t| <= tolerance_seconds` (default 300s) to prevent replay attacks.
3. Compute `expected_sig = hmac_sha256(secret, f"{t}.{body}")`.
4. Perform constant-time string comparison between `v1` and `expected_sig`.

---

## 3. Retries and Delivery Guarantees

- **Timeout**: The webhook dispatcher waits up to 10 seconds for an HTTP 2xx status response.
- **Backoff**: If your server returns 5xx or times out, RyouU retries up to 5 times using exponential backoff:
  - Attempt 1: immediate
  - Attempt 2: 15 seconds
  - Attempt 3: 60 seconds
  - Attempt 4: 5 minutes
  - Attempt 5: 30 minutes
- **Idempotency**: Use `X-KYC-Event-Id` to detect and safely ignore duplicate webhook deliveries.
