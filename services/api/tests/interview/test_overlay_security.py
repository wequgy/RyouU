"""Security tests locking overlay credentials and isolation."""
import os
import re
from pathlib import Path
import pytest


def test_tenant_key_does_not_appear_under_overlay():
    """Verify that tenant API keys and demo keys never appear anywhere under apps/overlay."""
    overlay_dir = Path("apps/overlay")
    assert overlay_dir.exists(), "apps/overlay directory must exist"
    
    forbidden_patterns = [
        re.compile(r"kyc_demo_lenient_key"),
        re.compile(r"kyc_demo_strict_key"),
        re.compile(r"tenantApiKey"),
    ]
    
    violations = []
    # Check all files in apps/overlay excluding node_modules and .git
    for root, dirs, files in os.walk(overlay_dir):
        if "node_modules" in dirs:
            dirs.remove("node_modules")
        if ".git" in dirs:
            dirs.remove(".git")
        if "tests" in dirs:
            dirs.remove("tests")
        for f in files:
            file_path = Path(root) / f
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                for pattern in forbidden_patterns:
                    matches = pattern.findall(content)
                    if matches:
                        violations.append(f"{file_path}: matched {pattern.pattern}")
            except Exception:
                pass

    assert not violations, f"Forbidden tenant credentials found in apps/overlay:\n" + "\n".join(violations)


def test_overlay_token_rejected_by_verifications_and_flow(client):
    """Verify that an overlay interviewer token is rejected by every /v1/verifications and /flow endpoint."""
    headers_tenant = {"Authorization": "Bearer kyc_demo_lenient_key"}
    
    # 1. Create a KYC verification session
    v_res = client.post("/v1/verifications", headers=headers_tenant, json={
        "reference_id": "ref_sec_test_01",
        "expected": {"name": "Bob Stone"}
    })
    assert v_res.status_code == 201
    vid = v_res.json()["id"]
    
    # 2. Create an interview session and get scoped interviewer token
    iv_res = client.post("/v1/interviews", headers=headers_tenant, json={
        "candidate_id": "cand_sec_01",
        "ttl_hours": 1
    })
    assert iv_res.status_code == 200
    iv_data = iv_res.json()
    interview_id = iv_data["id"]
    overlay_token = iv_data["token"]
    
    overlay_bearer = {"Authorization": f"Bearer {overlay_token}"}
    overlay_flow_header = {"X-Flow-Token": overlay_token}
    overlay_iv_header = {"X-Interview-Token": overlay_token}
    
    # 3. /v1/verifications endpoints MUST reject overlay token
    # POST /v1/verifications
    r1 = client.post("/v1/verifications", headers=overlay_bearer, json={"reference_id": "ref_bad"})
    assert r1.status_code == 401, f"Expected 401, got {r1.status_code}: {r1.text}"
    
    # GET /v1/verifications
    r2 = client.get("/v1/verifications", headers=overlay_bearer)
    assert r2.status_code == 401, f"Expected 401, got {r2.status_code}: {r2.text}"
    
    # GET /v1/verifications/{vid}
    r3 = client.get(f"/v1/verifications/{vid}", headers=overlay_bearer)
    assert r3.status_code == 401, f"Expected 401, got {r3.status_code}: {r3.text}"
    
    # GET /v1/verifications/{vid}/evidence
    r4 = client.get(f"/v1/verifications/{vid}/evidence", headers=overlay_bearer)
    assert r4.status_code == 401, f"Expected 401, got {r4.status_code}: {r4.text}"
    
    # POST /v1/verifications/{vid}/review
    r5 = client.post(f"/v1/verifications/{vid}/review", headers=overlay_bearer, json={"decision": "approved"})
    assert r5.status_code == 401, f"Expected 401, got {r5.status_code}: {r5.text}"
    
    # DELETE /v1/verifications/{vid}
    r6 = client.delete(f"/v1/verifications/{vid}", headers=overlay_bearer)
    assert r6.status_code == 401, f"Expected 401, got {r6.status_code}: {r6.text}"
    
    # 4. /flow endpoints MUST reject overlay token (when passed as X-Flow-Token)
    f1 = client.get(f"/flow/{vid}/context", headers=overlay_flow_header)
    assert f1.status_code in (401, 404), f"Expected 401/404, got {f1.status_code}"
    
    f2 = client.post(f"/flow/{vid}/signals", headers=overlay_flow_header, json={"camera_labels": []})
    assert f2.status_code in (401, 404), f"Expected 401/404, got {f2.status_code}"
    
    f3 = client.post(f"/flow/{vid}/upload/id_image", headers=overlay_flow_header, files={"file": ("test.jpg", b"123", "image/jpeg")})
    assert f3.status_code in (401, 404), f"Expected 401/404, got {f3.status_code}"
    
    f4 = client.post(f"/flow/{vid}/submit", headers=overlay_flow_header)
    assert f4.status_code in (401, 404), f"Expected 401/404, got {f4.status_code}"


def test_overlay_token_mint_and_refresh_lifecycle(client):
    """Verify that interviewer tokens can be minted by tenant, used by overlay, and refreshed before expiry."""
    headers_tenant = {"Authorization": "Bearer kyc_demo_lenient_key"}
    
    # 1. Create interview
    iv_res = client.post("/v1/interviews", headers=headers_tenant, json={
        "candidate_id": "cand_refresh_test",
        "ttl_hours": 1
    })
    assert iv_res.status_code == 200
    iv = iv_res.json()
    interview_id = iv["id"]
    token1 = iv["token"]
    
    # 2. Mint alternative token through tenant API
    mint_res = client.post(f"/v1/interviews/{interview_id}/token", headers=headers_tenant)
    assert mint_res.status_code == 200
    mint_data = mint_res.json()
    token2 = mint_data["token"]
    assert token2 != token1
    assert "expires_at" in mint_data
    
    # 3. Old token should now fail
    sum_old = client.get(f"/v1/interviews/{interview_id}/summary", headers={"X-Interview-Token": token1})
    assert sum_old.status_code == 401
    
    # 4. New minted token works
    sum_new = client.get(f"/v1/interviews/{interview_id}/summary", headers={"X-Interview-Token": token2})
    assert sum_new.status_code == 200
    assert sum_new.json()["status"] == "active"
    
    # 5. Refresh token using active token
    refresh_res = client.post(f"/v1/interviews/{interview_id}/refresh", headers={"X-Interview-Token": token2})
    assert refresh_res.status_code == 200
    refreshed = refresh_res.json()
    token3 = refreshed["token"]
    assert token3 != token2
    assert refreshed["expires_at"] > 0
    
    # 6. Verify refreshed token works and previous is superseded
    assert client.get(f"/v1/interviews/{interview_id}/summary", headers={"X-Interview-Token": token2}).status_code == 401
    assert client.get(f"/v1/interviews/{interview_id}/summary", headers={"X-Interview-Token": token3}).status_code == 200
