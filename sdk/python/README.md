# Unclone KYC Python SDK

The official Python client library for the Unclone Identity Verification Service.

## Installation

```bash
pip install unclone-kyc
```

## Usage

### 1. Initialize Client
```python
from unclone_kyc import Client

client = Client(
    api_key="kyc_live_...",
    base_url="https://api.unclone.ai",  # or http://localhost:8000 for local dev
)
```

### 2. Create Verification Session
```python
session = client.create_verification(
    reference_id="user_4821",
    expected={
        "name": "Alex Morgan",
        "dob": "1995-08-20",
        "id_last4": "4821"
    },
    policy="strict",  # or "lenient"
    idempotency_key="tx_req_001"
)

# Send session.flow_url to your mobile app or frontend
print("Session ID:", session.id)
print("Flow URL:", session.flow_url)
```

### 3. Check Verification Status
```python
res = client.get_verification(session.id)
print("Status:", res.status)               # e.g. "completed"
print("Decision:", res.decision)           # "approved" | "needs_review" | "rejected_recommended"
print("Final Decision:", res.final_decision)
print("Trust Score:", res.trust)
print("Reasons:", res.reasons)
```

### 4. Human Review Override
```python
reviewed = client.review_verification(
    session.id,
    decision="approved",  # "approved" or "rejected"
    note="Reviewed physical identity document in person"
)
print("Updated Final Decision:", reviewed.final_decision)
```

### 5. Verify Inbound Webhooks
```python
from unclone_kyc import verify_webhook, WebhookVerificationError

# In your FastAPI / Flask / Django webhook handler:
try:
    event = verify_webhook(
        body=raw_body_bytes,
        signature_header=request.headers.get("X-KYC-Signature"),
        secret="whsec_...",
        tolerance_s=300
    )
    print("Received event:", event["type"], event["data"]["id"])
except WebhookVerificationError as e:
    print("Invalid webhook signature:", e)
```
