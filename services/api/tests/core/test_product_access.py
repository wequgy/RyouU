"""Test per-customer product access, scoped keys, and single-product boot."""
import pytest
from fastapi.testclient import TestClient

from app import db
from app.config import get_settings
from app.main import create_app


@pytest.fixture
def product_tenants():
    # Setup test tenants with specific product entitlements
    db.init_db()
    
    # 1. KYC-only tenant
    db.upsert_tenant(
        tenant_id="tenant_kyc_only",
        name="KYC Only Corp",
        api_key="key_kyc_only_secret",
        webhook_url="",
        webhook_secret="",
        default_policy="lenient",
        products=["kyc"]
    )
    
    # 2. Interview-only tenant
    db.upsert_tenant(
        tenant_id="tenant_interview_only",
        name="Interview Only Corp",
        api_key="key_interview_only_secret",
        webhook_url="",
        webhook_secret="",
        default_policy="lenient",
        products=["interview"]
    )
    
    # 3. Dual-product tenant
    db.upsert_tenant(
        tenant_id="tenant_dual",
        name="Dual Product Corp",
        api_key="key_dual_secret",
        webhook_url="",
        webhook_secret="",
        default_policy="lenient",
        products=["kyc", "interview"]
    )


def test_kyc_only_tenant_cannot_call_interview_routes(client, product_tenants):
    headers = {"Authorization": "Bearer key_kyc_only_secret"}
    
    # Can call KYC route
    res_kyc = client.get("/v1/verifications", headers=headers)
    assert res_kyc.status_code == 200
    
    # Cannot call interview route -> 403 with clear message
    res_iv = client.post("/v1/interviews", headers=headers, json={"metadata": {"test": 1}})
    assert res_iv.status_code == 403
    assert "Tenant does not have access to 'interview' product" in res_iv.json()["detail"]


def test_interview_only_tenant_cannot_call_kyc_routes(client, product_tenants):
    headers = {"Authorization": "Bearer key_interview_only_secret"}
    
    # Can call interview route
    res_iv = client.post("/v1/interviews", headers=headers, json={"metadata": {"test": 1}})
    assert res_iv.status_code == 200
    
    # Cannot call KYC route -> 403 with clear message
    res_kyc = client.get("/v1/verifications", headers=headers)
    assert res_kyc.status_code == 403
    assert "Tenant does not have access to 'kyc' product" in res_kyc.json()["detail"]


def test_scoped_api_keys_cannot_cross_products(client, product_tenants):
    dual_headers = {"Authorization": "Bearer key_dual_secret"}
    
    # Create a scoped KYC key
    res_k = client.post("/v1/tenant/keys", headers=dual_headers, json={"scopes": ["kyc:*"]})
    assert res_k.status_code == 201
    kyc_key = res_k.json()["api_key"]
    
    # Create a scoped Interview key
    res_i = client.post("/v1/tenant/keys", headers=dual_headers, json={"scopes": ["interview:*"]})
    assert res_i.status_code == 201
    iv_key = res_i.json()["api_key"]
    
    # kyc_key on KYC route -> 200
    r1 = client.get("/v1/verifications", headers={"Authorization": f"Bearer {kyc_key}"})
    assert r1.status_code == 200
    
    # kyc_key on Interview route -> 403 (lacks scope)
    r2 = client.post("/v1/interviews", headers={"Authorization": f"Bearer {kyc_key}"}, json={})
    assert r2.status_code == 403
    assert "lacks required scope" in r2.json()["detail"]
    
    # iv_key on Interview route -> 200
    r3 = client.post("/v1/interviews", headers={"Authorization": f"Bearer {iv_key}"}, json={})
    assert r3.status_code == 200
    
    # iv_key on KYC route -> 403 (lacks scope)
    r4 = client.get("/v1/verifications", headers={"Authorization": f"Bearer {iv_key}"})
    assert r4.status_code == 403
    assert "lacks required scope" in r4.json()["detail"]


def test_api_key_revocation(client, product_tenants):
    headers = {"Authorization": "Bearer key_dual_secret"}
    
    res = client.post("/v1/tenant/keys", headers=headers, json={"scopes": ["kyc:*"]})
    key_id = res.json()["key_id"]
    api_key = res.json()["api_key"]
    
    # Works before revocation
    r1 = client.get("/v1/verifications", headers={"Authorization": f"Bearer {api_key}"})
    assert r1.status_code == 200
    
    # Revoke key
    r_rev = client.post(f"/v1/tenant/keys/{key_id}/revoke", headers=headers)
    assert r_rev.status_code == 200
    assert r_rev.json()["revoked"] is True
    
    # Fails after revocation
    r2 = client.get("/v1/verifications", headers={"Authorization": f"Bearer {api_key}"})
    assert r2.status_code == 401


def test_standalone_interview_reports_no_kyc_baseline(client, product_tenants):
    headers = {"Authorization": "Bearer key_interview_only_secret"}
    
    # Create interview session without existing KYC candidate
    res = client.post("/v1/interviews", headers=headers, json={"candidate_id": "cand_standalone_1"})
    assert res.status_code == 200
    iv_id = res.json()["id"]
    token = res.json()["token"]
    
    sum_res = client.get(f"/v1/interviews/{iv_id}/summary", headers={"X-Interview-Token": token})
    assert sum_res.status_code == 200
    data = sum_res.json()
    assert data["kyc_baseline_status"] == "No KYC baseline"


def test_app_boots_with_only_kyc_enabled(monkeypatch):
    monkeypatch.setenv("ENABLE_KYC", "true")
    monkeypatch.setenv("ENABLE_INTERVIEW", "false")
    
    app = create_app()
    with TestClient(app) as test_client:
        # Core routes available
        assert test_client.get("/healthz").status_code == 200
        
        # KYC routes available
        h = {"Authorization": "Bearer kyc_demo_lenient_key"}
        assert test_client.get("/v1/verifications", headers=h).status_code == 200
        
        # Interview routes NOT mounted -> 404
        r = test_client.post("/v1/interviews", headers=h, json={})
        assert r.status_code == 404
        
        # readyz lists only enabled product models
        ready_res = test_client.get("/readyz")
        models = ready_res.json()["models"]
        assert "InsightFace (buffalo_l)" in models
        assert "ViT Deepfake Detector (prithivMLmods/Deep-Fake-Detector-v2-Model)" not in models
        assert "SyncNet (syncnet-python)" not in models


def test_app_boots_with_only_interview_enabled(monkeypatch):
    monkeypatch.setenv("ENABLE_KYC", "false")
    monkeypatch.setenv("ENABLE_INTERVIEW", "true")
    
    app = create_app()
    with TestClient(app) as test_client:
        # Core routes available
        assert test_client.get("/healthz").status_code == 200
        
        # Interview routes available
        h = {"Authorization": "Bearer kyc_demo_lenient_key"}
        assert test_client.post("/v1/interviews", headers=h, json={}).status_code == 200
        
        # KYC routes NOT mounted -> 404
        assert test_client.get("/v1/verifications", headers=h).status_code == 404
        assert test_client.get("/flow/ver_dummy/context").status_code == 404
        
        # readyz lists only interview models
        ready_res = test_client.get("/readyz")
        models = ready_res.json()["models"]
        assert "ViT Deepfake Detector (prithivMLmods/Deep-Fake-Detector-v2-Model)" in models
        assert "InsightFace (buffalo_l)" not in models
