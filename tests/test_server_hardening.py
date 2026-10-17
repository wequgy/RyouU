"""Tests for server hardening features:
- OTP senders and pluggable SMS provider
- Tenant administration & credential rotation
- Idempotency-Key support
- Rate limiting
- Retention cleanup
- Encrypted evidence and expiring signed URLs
- Flow HTML escaping
- Webhook signatures & replay attack rejection
"""
import time
from pathlib import Path

import pytest
from app import db, retention, security
from app.checks import otp
from app.checks.otp import MockSmsProvider, set_sms_provider


def auth(key):
    return {"Authorization": f"Bearer {key}"}


def test_pluggable_sms_provider(client):
    """Test that registering a MockSmsProvider directly verifies SMS without email bridge fallback."""
    mock_provider = MockSmsProvider()
    set_sms_provider(mock_provider)
    try:
        r = client.post("/v1/verifications", json={"reference_id": "sms_test", "expected": {"name": "Test"}},
                        headers=auth("kyc_demo_strict_key"))
        vid = r.json()["id"]
        flow_token = r.json()["flow_url"].split("t=")[1].split("&")[0]
        fh = {"X-Flow-Token": flow_token}

        send_res = client.post(f"/flow/{vid}/otp/send", headers=fh, json={"channel": "phone", "destination": "+1234567890"})
        assert send_res.status_code == 200
        assert "fallback" not in send_res.json()
        assert len(mock_provider.sent_messages) == 1
        assert mock_provider.sent_messages[0]["destination"] == "+1234567890"
    finally:
        set_sms_provider(None)


def test_tenant_admin_and_rotation(client):
    """Test API key and webhook secret rotation and webhook URL update."""
    tenant_id = "test_tenant_rot"
    # Create tenant
    db.upsert_tenant(tenant_id, "Test Rot Co", "initial_key_123", "https://hook.orig", "orig_sec_123", "strict")
    t = db.tenant_by_id(tenant_id)
    assert t["api_key_hash"] == security.hash_key("initial_key_123")
    assert db.tenant_by_api_key("initial_key_123")["id"] == tenant_id

    # Rotate API key via endpoint
    rot_res = client.post("/v1/tenant/rotate-key", headers=auth("initial_key_123"))
    assert rot_res.status_code == 200
    new_key = rot_res.json()["api_key"]
    assert new_key.startswith("kyc_live_")

    # Old key fails, new key works
    assert client.get("/v1/verifications", headers=auth("initial_key_123")).status_code == 401
    assert client.get("/v1/verifications", headers=auth(new_key)).status_code == 200

    # Rotate webhook secret via endpoint
    sec_res = client.post("/v1/tenant/rotate-webhook-secret", headers=auth(new_key))
    assert sec_res.status_code == 200
    new_sec = sec_res.json()["webhook_secret"]
    assert new_sec.startswith("whsec_")
    assert db.tenant_by_id(tenant_id)["webhook_secret"] == new_sec

    # Update webhook URL via endpoint
    up_res = client.patch("/v1/tenant/webhook", headers=auth(new_key), json={"webhook_url": "https://new.hook.com"})
    assert up_res.status_code == 200
    assert db.tenant_by_id(tenant_id)["webhook_url"] == "https://new.hook.com"


def test_idempotency_key(client):
    """Test that POST /v1/verifications with Idempotency-Key returns cached response."""
    key = "kyc_demo_strict_key"
    idemp = "idemp_test_12345"
    body = {"reference_id": "ref_idemp", "expected": {"name": "Test User"}}

    r1 = client.post("/v1/verifications", json=body, headers={**auth(key), "Idempotency-Key": idemp})
    assert r1.status_code == 201
    j1 = r1.json()

    # Second call with same idempotency key
    r2 = client.post("/v1/verifications", json=body, headers={**auth(key), "Idempotency-Key": idemp})
    assert r2.status_code == 201
    j2 = r2.json()

    assert j1["id"] == j2["id"]
    assert j1["flow_url"] == j2["flow_url"]


def test_rate_limiting(client):
    """Test that per-tenant rate limit triggers 429 when threshold exceeded."""
    tenant_id = "rate_limit_tenant"
    db.upsert_tenant(tenant_id, "Rate Tenant", "rate_key_test", "", "whsec_test", "lenient")

    # Artificially simulate 120 calls already recorded in DB
    for _ in range(120):
        db.check_rate_limit(f"rate:tenant:{tenant_id}", limit=120, window_s=60)

    # 121st call should trigger 429
    r = client.get("/v1/verifications", headers=auth("rate_key_test"))
    assert r.status_code == 429
    assert "rate limit" in r.text.lower()


def test_encrypted_evidence_and_signed_url(client, tmp_path):
    """Test that uploads are stored encrypted on disk and decrypted on download."""
    r = client.post("/v1/verifications", json={"reference_id": "u_enc", "expected": {"name": "A"}},
                    headers=auth("kyc_demo_strict_key"))
    vid = r.json()["id"]
    token = r.json()["flow_url"].split("t=")[1].split("&")[0]
    fh = {"X-Flow-Token": token}

    raw_selfie = b"\xFF\xD8\xFF\xE0FakeJpegImageContent12345"
    up = client.post(f"/flow/{vid}/upload/selfie", headers=fh, files={"file": ("me.jpg", raw_selfie)})
    assert up.status_code == 200

    # Verify on-disk file is ENCRYPTED (does not start with raw plaintext)
    folder = tmp_path / "uploads" / vid
    disk_file = next(folder.glob("selfie.*"))
    disk_bytes = disk_file.read_bytes()
    assert disk_bytes != raw_selfie
    # Verify it decrypts cleanly
    assert security.decrypt_bytes(disk_bytes) == raw_selfie

    # Get evidence manifest
    ev_resp = client.get(f"/v1/verifications/{vid}/evidence", headers=auth("kyc_demo_strict_key"))
    assert ev_resp.status_code == 200
    evidence = ev_resp.json()["evidence"]
    assert "selfie" in evidence
    signed_url = evidence["selfie"]["url"]

    # Download with token
    dl_token = signed_url.split("token=")[1]
    dl_resp = client.get(f"/v1/verifications/{vid}/evidence/selfie?token={dl_token}")
    assert dl_resp.status_code == 200
    assert dl_resp.content == raw_selfie


def test_retention_job(client, tmp_path):
    """Test that retention job deletes expired verifications and their files."""
    r = client.post("/v1/verifications", json={"reference_id": "u_old", "expected": {}},
                    headers=auth("kyc_demo_lenient_key"))
    vid = r.json()["id"]
    flow_token = r.json()["flow_url"].split("t=")[1].split("&")[0]

    # Upload a file
    client.post(f"/flow/{vid}/upload/selfie", headers={"X-Flow-Token": flow_token},
                files={"file": ("me.jpg", b"ABCD")})
    upload_dir = tmp_path / "uploads" / vid
    assert upload_dir.exists()

    # Artificially age the verification record
    with db.conn() as c:
        c.execute("UPDATE verifications SET created_at=? WHERE id=?", (time.time() - 10000, vid))

    # Run retention cleanup for age > 5000s
    cleaned = retention.cleanup_expired_verifications(max_age_s=5000)
    assert cleaned >= 1
    assert not upload_dir.exists()
    assert client.get(f"/v1/verifications/{vid}", headers=auth("kyc_demo_lenient_key")).status_code == 404


def test_flow_html_escaping(client):
    """Test that flow.html includes esc function to prevent XSS."""
    r = client.get("/flow")
    assert r.status_code == 200
    text = r.text
    assert "esc(" in text
    assert "replace(/[&<>'\"/]/g" in text or "replace(/[&<>\"]/g" in text or "esc(PRE_NAME)" in text or "esc = (v)" in text


def test_webhook_tamper_and_replay_rejection():
    """Test webhook verification rejects tampered body, wrong secret, and replayed timestamps."""
    secret = "whsec_test_secret_123"
    body = b'{"type":"verification.completed","id":"evt_1"}'

    # Valid signature
    sig = security.sign_payload(secret, body)
    assert security.verify_signature(secret, body, sig) is True

    # Tampered body fails
    assert security.verify_signature(secret, b'{"tampered":true}', sig) is False

    # Wrong secret fails
    assert security.verify_signature("whsec_wrong_secret", body, sig) is False

    # Timestamp replay attack outside tolerance fails
    old_ts = int(time.time()) - 600
    old_sig = security.sign_payload(secret, body, ts=old_ts)
    assert security.verify_signature(secret, body, old_sig, tolerance_s=300) is False
