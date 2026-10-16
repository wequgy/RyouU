"""A fake customer ('FakeBank') integrating the KYC service. This is what you show judges.

Run:  uvicorn demo_client.app:app --port 9000
  GET  /start?ref=user_1&policy=strict   -> creates a verification and returns the flow URL
  POST /webhooks/kyc                     -> receives signed results (signature verified)
  GET  /events                           -> everything received so far
"""
import os
import time

import httpx
from fastapi import FastAPI, HTTPException, Request

from app.security import verify_signature

API = os.environ.get("KYC_API_BASE", "http://localhost:8000")
KEY = os.environ.get("KYC_API_KEY", "kyc_demo_lenient_key")
SECRET = os.environ.get("DEMO_WEBHOOK_SECRET", "whsec_demo")

app = FastAPI(title="FakeBank (demo client)")
EVENTS: list = []


@app.get("/start")
def start(ref: str = "user_123", policy: str = "", name: str = "Asha Rao", dob: str = "1999-04-12",
          id_last4: str = "4821"):
    body = {"reference_id": ref, "expected": {"name": name, "dob": dob, "id_last4": id_last4}}
    if policy:
        body["policy"] = policy
    r = httpx.post(f"{API}/v1/verifications", json=body, headers={"Authorization": f"Bearer {KEY}"}, timeout=15)
    r.raise_for_status()
    return r.json()          # send the user to r.json()["flow_url"]


@app.post("/webhooks/kyc")
async def webhook(request: Request):
    body = await request.body()
    if not verify_signature(SECRET, body, request.headers.get("x-kyc-signature", "")):
        raise HTTPException(400, "bad signature")
    import json
    event = json.loads(body)
    EVENTS.append({"received_at": time.time(), "type": event["type"], "id": event["id"],
                   "verification": event["data"]["id"], "reference_id": event["data"]["reference_id"],
                   "decision": event["data"]["decision"], "final_decision": event["data"]["final_decision"],
                   "trust": event["data"]["trust"], "reasons": event["data"]["reasons"]})
    return {"ok": True}


@app.get("/events")
def events():
    return {"data": EVENTS}
