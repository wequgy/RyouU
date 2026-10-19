---
title: Python SDK
description: Official Python client library for RyouU identity verification and webhook handling.
---

The `unclone-kyc` Python package provides typed bindings for creating sessions, polling statuses, submitting reviewer decisions, and verifying inbound HMAC webhooks.

---

## Installation

```bash
pip install unclone-kyc
```

---

## 1. Initialize Client

```python
from unclone_kyc import Client

client = Client(
    api_key="kyc_live_...",
    base_url="https://api.yourfintech.com",  # Or http://localhost:8000 for local development
    timeout=30.0
)
```

---

## 2. Create Verification Session

```python
session = client.create_verification(
    reference_id="user_4821",
    expected={
        "name": "Alex Morgan",
        "dob": "1995-08-20",
        "id_last4": "4821"
    },
    policy="strict",  # Or "lenient"
    idempotency_key="tx_req_001"
)

print("Session ID:", session.id)
print("Flow URL:", session.flow_url)
```

---

## 3. Check Status & Verdict

```python
res = client.get_verification(session.id)

print("Status:", res.status)               # e.g. "completed"
print("Decision:", res.decision)           # "approved" | "needs_review" | "rejected_recommended"
print("Final Decision:", res.final_decision)
print("Trust Score:", res.trust)
print("Reasons:", res.reasons)
```

---

## 4. Human Review Override

```python
reviewed = client.review_verification(
    session.id,
    decision="approved",  # "approved" or "rejected"
    note="Reviewed physical national identity card in branch office."
)

print("Updated Final Decision:", reviewed.final_decision)
```

---

## 5. Verify Inbound Webhooks

```python
from unclone_kyc import verify_webhook, WebhookVerificationError

# Inside your FastAPI / Flask / Django handler:
try:
    event = verify_webhook(
        body=raw_body_bytes,
        signature_header=request.headers.get("X-KYC-Signature"),
        secret="whsec_...",
        tolerance_s=300
    )
    print("Received verified event:", event["type"], event["data"]["id"])
except WebhookVerificationError as err:
    print("Invalid webhook signature:", err)
```
