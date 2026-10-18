import time
import httpx
import pytest

from unclone_kyc import (
    Client,
    AuthenticationError,
    NotFoundError,
    ConflictError,
    RateLimitError,
    WebhookVerificationError,
    verify_webhook,
)
import hmac
import hashlib


def _sign_payload(secret: str, body: bytes, ts: int) -> str:
    mac = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={ts},v1={mac}"



def test_client_init_validation():
    with pytest.raises(ValueError):
        Client(api_key="")


def test_client_create_and_get():
    def handler(request: httpx.Request):
        assert request.headers["Authorization"] == "Bearer test_key"
        if request.url.path == "/v1/verifications" and request.method == "POST":
            return httpx.Response(
                201,
                json={
                    "id": "ver_123",
                    "status": "created",
                    "policy": "strict",
                    "expires_at": 1792180000.0,
                    "flow_url": "https://kyc.example/flow?v=ver_123&t=token123",
                },
            )
        if request.url.path == "/v1/verifications/ver_123" and request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "id": "ver_123",
                    "reference_id": "ref_456",
                    "status": "completed",
                    "policy": "strict",
                    "decision": "approved",
                    "final_decision": "approved",
                    "trust": 0.98,
                    "reasons": [],
                    "results": [{"name": "face_match", "status": "pass"}],
                },
            )
        return httpx.Response(404)

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    kyc = Client(api_key="test_key", base_url="https://kyc.example", http_client=mock_client)

    sess = kyc.create_verification("ref_456", expected={"name": "Alice"}, policy="strict", idempotency_key="k1")
    assert sess.id == "ver_123"
    assert sess.flow_url.startswith("https://kyc.example")

    result = kyc.get_verification("ver_123")
    assert result.id == "ver_123"
    assert result.status == "completed"
    assert result.decision == "approved"
    assert result.trust == 0.98


def test_client_error_mapping():
    def handler(request: httpx.Request):
        if request.url.path == "/v1/verifications/auth_fail":
            return httpx.Response(401, json={"detail": "Unauthorized"})
        if request.url.path == "/v1/verifications/missing":
            return httpx.Response(404, json={"detail": "Not found"})
        if request.url.path == "/v1/verifications/conflict/review":
            return httpx.Response(409, text="Already reviewed")
        if request.url.path == "/v1/verifications/rate_limit":
            return httpx.Response(429, json={"detail": "Too many requests"})
        return httpx.Response(200)

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    kyc = Client(api_key="test_key", http_client=mock_client)

    with pytest.raises(AuthenticationError):
        kyc.get_verification("auth_fail")

    with pytest.raises(NotFoundError):
        kyc.get_verification("missing")

    with pytest.raises(ConflictError):
        kyc.review_verification("conflict", "approved")

    with pytest.raises(RateLimitError):
        kyc.get_verification("rate_limit")


def test_webhook_verification():
    secret = "whsec_supersecret123"
    raw_payload = b'{"type":"verification.completed","data":{"id":"ver_999","decision":"approved"}}'
    ts = int(time.time())
    sig = _sign_payload(secret, raw_payload, ts=ts)

    # Valid signature
    event = verify_webhook(raw_payload, sig, secret, tolerance_s=300)
    assert event["type"] == "verification.completed"
    assert event["data"]["decision"] == "approved"

    # Static method on client also works
    event2 = Client.verify_webhook(raw_payload, sig, secret, tolerance_s=300)
    assert event2["data"]["id"] == "ver_999"

    # Tampered body raises WebhookVerificationError
    with pytest.raises(WebhookVerificationError):
        verify_webhook(b'{"tampered":true}', sig, secret)

    # Expired timestamp raises WebhookVerificationError
    expired_sig = _sign_payload(secret, raw_payload, ts=ts - 600)
    with pytest.raises(WebhookVerificationError):
        verify_webhook(raw_payload, expired_sig, secret, tolerance_s=300)
