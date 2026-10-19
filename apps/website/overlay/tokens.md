---
title: Interviewer Token Minting
description: How your backend mints short-lived interviewer tokens for the desktop overlay.
---

The desktop overlay **never** holds tenant master API keys or database credentials. Instead, interviewers authenticate using short-lived, cryptographically signed interviewer tokens minted by your customer backend.

---

## 1. Token Minting Flow

```
+------------------+         1. Login / Interview ID        +------------------+
|  Interviewer App | -------------------------------------> | Customer Backend |
| (Electron HUD)   |                                        | (Holds KYC Key)  |
|                  | <------------------------------------- +------------------+
+------------------+     2. Returns itok_... (TTL 1 hr)              |
         |                                                           | 3. POST /v1/interviews
         | 4. Connects with Authorization: Bearer itok_...           v
         +-------------------------------------------------> +------------------+
                                                             |  RyouU API Core  |
                                                             +------------------+
```

---

## 2. Server Minting Endpoint

Your backend mints an interviewer token by calling `POST /v1/interviews`:

```python
import requests

response = requests.post(
    "http://localhost:8000/v1/interviews",
    headers={"Authorization": "Bearer kyc_live_..."},
    json={
        "candidate_id": "candidate-001",
        "interviewer_id": "eng_lead_sarah",
        "meeting_platform": "zoom",
        "ttl_seconds": 3600 # 1 hour
    }
)

data = response.json()
interviewer_token = data["token"] # e.g. "itok_8a49c02b..."
```

---

## 3. Scopes & Boundaries

Interviewer tokens are constrained to a single interview session:
- **Permitted**: Uploading 25-second video clips (`POST /v1/interviews/{id}/clips`), fetching summary anomaly counts (`GET /v1/interviews/{id}/summary`), and closing the session (`POST /v1/interviews/{id}/end`).
- **Forbidden**: Querying tenant billing, inspecting other candidates, or accessing administrative configurations.
- **Revocation**: The token automatically expires when the meeting ends or when `POST /v1/interviews/{id}/end` is called.
