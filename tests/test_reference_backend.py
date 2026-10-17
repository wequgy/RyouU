"""Test reference customer backend (demo_client/app.py)."""
import json
import time

from fastapi.testclient import TestClient
from demo_client.app import app as customer_app
from app import security


def test_customer_backend_flow(monkeypatch):
    test_client = TestClient(customer_app)

    # 1. Mock the client.create_verification and client.get_verification
    from demo_client.app import client as kyc_sdk_client

    class MockSession:
        id = "ver_customer_1"
        status = "created"
        policy = "strict"
        expires_at = 1792180000.0
        flow_url = "http://localhost:8000/flow?v=ver_customer_1&t=tok123"

    class MockResult:
        id = "ver_customer_1"
        reference_id = "user_abc"
        status = "completed"
        policy = "strict"
        decision = "approved"
        final_decision = "approved"
        trust = 0.99
        reasons = []

    monkeypatch.setattr(kyc_sdk_client, "create_verification", lambda **kwargs: MockSession())
    monkeypatch.setattr(kyc_sdk_client, "get_verification", lambda vid: MockResult())

    # POST /kyc/session
    res = test_client.post("/kyc/session", json={"referenceId": "user_abc", "name": "Alice"})
    assert res.status_code == 201
    assert res.json()["id"] == "ver_customer_1"
    assert "flow_url" in res.json()

    # GET /kyc/status/{id}
    status_res = test_client.get("/kyc/status/ver_customer_1")
    assert status_res.status_code == 200
    assert status_res.json()["decision"] == "approved"
    assert status_res.json()["final_decision"] == "approved"

    # POST /webhooks/kyc
    secret = "whsec_demo"
    body = json.dumps({"id": "evt_hook_1", "type": "verification.completed", "data": {"id": "ver_customer_1", "decision": "approved"}}).encode()
    sig = security.sign_payload(secret, body)

    hook_res = test_client.post("/webhooks/kyc", content=body, headers={"x-kyc-signature": sig})
    assert hook_res.status_code == 200
    assert hook_res.json()["received"] is True

    # Bad signature rejected
    bad_hook = test_client.post("/webhooks/kyc", content=body, headers={"x-kyc-signature": "bad"})
    assert bad_hook.status_code == 400
