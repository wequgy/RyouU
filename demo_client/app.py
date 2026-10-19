"""Reference customer backend (e.g. 'ApexPay Server' / 'FakeBank') integrating the KYC service via the Unclone KYC SDK.

Run:
  uvicorn demo_client.app:app --port 9000 --reload

Endpoints:
  POST /kyc/session      -> creates session via SDK, returns {id, flow_url}
  GET  /kyc/status/{id}  -> returns {status, decision, final_decision, trust, reasons}
  POST /webhooks/kyc     -> verifies signature using SDK and stores event
  GET  /events           -> list all webhook events received
"""
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Ensure unclone_kyc package is importable
sdk_path = Path(__file__).resolve().parent.parent / "sdks" / "kyc" / "python"
if str(sdk_path) not in sys.path:
    sys.path.insert(0, str(sdk_path))

from unclone_kyc import Client, WebhookVerificationError, verify_webhook

API_BASE = os.environ.get("KYC_API_BASE", "http://localhost:8000")
API_KEY = os.environ.get("KYC_API_KEY", "kyc_demo_strict_key")
WEBHOOK_SECRET = os.environ.get("KYC_WEBHOOK_SECRET", os.environ.get("DEMO_WEBHOOK_SECRET", "whsec_demo"))

app = FastAPI(title="Reference Customer Backend (ApexPay Server)")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

client = Client(api_key=API_KEY, base_url=API_BASE)
EVENTS: List[Dict[str, Any]] = []


class CreateSessionRequest(BaseModel):
    reference_id: Optional[str] = None
    referenceId: Optional[str] = None
    expected: Optional[Dict[str, Any]] = None
    name: Optional[str] = None
    dob: Optional[str] = None
    idLast4: Optional[str] = None
    id_last4: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    policy: Optional[str] = "strict"


@app.post("/kyc/session", status_code=201)
def create_session(body: CreateSessionRequest):
    """Creates verification session with the customer's secret API key. Returns {id, flow_url}."""
    ref_id = body.reference_id or body.referenceId or f"user_{int(time.time())}"
    expected = dict(body.expected or {})
    if body.name:
        expected["name"] = body.name
    if body.dob:
        expected["dob"] = body.dob
    last4 = body.idLast4 or body.id_last4
    if last4:
        expected["id_last4"] = last4
    if body.email:
        expected["email"] = body.email
    if body.phone:
        expected["phone"] = body.phone

    try:
        session = client.create_verification(
            reference_id=ref_id,
            expected=expected,
            policy=body.policy or "strict",
        )
        return {
            "id": session.id,
            "flow_url": session.flow_url,
            "status": session.status,
            "policy": session.policy,
            "expires_at": session.expires_at,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create KYC session: {e}")


@app.get("/kyc/status/{vid}")
def get_status(vid: str):
    """Returns verdict fields needed by client: status, decision, final_decision, trust, reasons."""
    try:
        res = client.get_verification(vid)
        return {
            "id": res.id,
            "reference_id": res.reference_id,
            "status": res.status,
            "decision": res.decision,
            "final_decision": res.final_decision,
            "trust": res.trust,
            "reasons": res.reasons,
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Verification not found: {e}")


@app.post("/webhooks/kyc")
async def webhook(request: Request):
    """Verifies HMAC signature on incoming webhook and stores event."""
    body = await request.body()
    sig_header = request.headers.get("x-kyc-signature", "")
    try:
        event = verify_webhook(body, sig_header, WEBHOOK_SECRET, tolerance_s=300)
    except WebhookVerificationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    record = {
        "received_at": time.time(),
        "id": event.get("id"),
        "type": event.get("type"),
        "data": event.get("data", {}),
    }
    EVENTS.append(record)
    return {"received": True, "event_id": event.get("id")}


@app.get("/events")
def list_events():
    return {"events": EVENTS}


# Backward-compatible convenience route for quick browser testing
@app.get("/start")
def start(ref: str = "user_123", policy: str = "strict", name: str = "Asha Rao",
          dob: str = "1999-04-12", id_last4: str = "4821"):
    return create_session(CreateSessionRequest(
        reference_id=ref, policy=policy, name=name, dob=dob, id_last4=id_last4
    ))
