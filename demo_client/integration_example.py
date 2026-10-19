import os
import httpx

api_key = os.environ.get("KYC_API_KEY")
if not api_key:
    raise RuntimeError("KYC_API_KEY environment variable is required")

r = httpx.post("http://localhost:8000/v1/verifications",
               headers={"Authorization": f"Bearer {api_key}"},
               json={"reference_id": "user_123",
                     "expected": {"name": "Asha Rao", "dob": "1999-04-12", "id_last4": "4821"}})
print(r.json()["flow_url"])   # send your user here; the result arrives at your webhook
