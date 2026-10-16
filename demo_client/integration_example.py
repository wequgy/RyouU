"""The whole integration a customer writes (about 10 lines)."""
import httpx

r = httpx.post("http://localhost:8000/v1/verifications",
               headers={"Authorization": "Bearer kyc_demo_lenient_key"},
               json={"reference_id": "user_123",
                     "expected": {"name": "Asha Rao", "dob": "1999-04-12", "id_last4": "4821"}})
print(r.json()["flow_url"])   # send your user here; the result arrives at your webhook
