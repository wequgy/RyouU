import json

import httpx
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("KYC_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("KYC_DEV_MODE", "1")
    monkeypatch.setenv("KYC_SEED_DEMO", "1")
    monkeypatch.setenv("WEBHOOK_BACKOFF_S", "0")
    monkeypatch.setenv("DETECTIF_RETRY_SLEEP_CAP_S", "0")
    monkeypatch.setenv("DEMO_WEBHOOK_URL", "http://client.test/webhooks/kyc")
    monkeypatch.setenv("DEMO_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setenv("DETECTIF_API_KEY", "test-key")
    monkeypatch.setenv("KYC_ENFORCE_GATES", "0")
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASS", raising=False)
    monkeypatch.delenv("FAST2SMS_API_KEY", raising=False)
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)


@pytest.fixture
def client():
    from app.main import app
    with TestClient(app) as c:  # runs lifespan: init db + seed demo tenants
        yield c


@pytest.fixture
def webhook_sink(monkeypatch):
    """Capture webhook deliveries instead of hitting the network."""
    from app import webhooks
    sink = {"requests": [], "status": 200}

    def handler(request: httpx.Request):
        sink["requests"].append(request)
        return httpx.Response(sink["status"])

    monkeypatch.setattr(webhooks, "CLIENT_FACTORY", lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    return sink


@pytest.fixture
def fake_models(monkeypatch):
    """Stand-ins for the heavy ML pieces. Everything else (OTP, liveness, decisions, API) runs for real.

    Selfie/ID file CONTENT picks the 'person': b'A' same as ID, b'B' different person, b'M' borderline.
    Detectif is mocked at the HTTP layer; set state['verdict'] to real | fake | not_sure.
    """
    import numpy as np
    from app.checks import face_match, voice_ai

    vecs = {b"A": np.array([1.0, 0.0]), b"B": np.array([0.0, 1.0]),
            b"M": np.array([0.32, (1 - 0.32 ** 2) ** 0.5])}

    def embedder(path):
        return vecs[open(path, "rb").read()[:1]], {"face_px": 200, "n_faces": 1, "det_score": 0.99}

    monkeypatch.setattr(face_match, "EMBEDDER", embedder)

    state = {"verdict": "real", "calls": 0}

    def handler(request: httpx.Request):
        state["calls"] += 1
        fake_p = {"real": 0.07, "fake": 0.93, "not_sure": 0.5}[state["verdict"]]
        return httpx.Response(200, json={"request_id": "req_1", "operation_id": "op_1", "result": {
            "verdict": state["verdict"], "score": fake_p, "threshold": 0.62, "duration_seconds": 6.0}})

    monkeypatch.setattr(voice_ai, "CLIENT_FACTORY", lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    return state
