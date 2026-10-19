"""End-to-end through the HTTP API. ML is faked (see conftest.fake_models); everything else is real."""
import json
import re

from app import security

LENIENT, STRICT = "kyc_demo_lenient_key", "kyc_demo_strict_key"
EXPECTED = {"name": "Asha Rao", "dob": "1999-04-12", "id_last4": "4821"}
GOOD_SIGNALS = {"camera_labels": ["FaceTime HD Camera"], "focus_loss_count": 0}


def auth(key):
    return {"Authorization": f"Bearer {key}"}


def flow_headers(flow_url):
    return {"X-Flow-Token": re.search(r"[?&]t=([^&]+)", flow_url).group(1)}


def create(client, key=LENIENT, **body):
    r = client.post("/v1/verifications", json={"reference_id": "user_1", "expected": EXPECTED, **body}, headers=auth(key))
    assert r.status_code == 201, r.text
    j = r.json()
    return j["id"], flow_headers(j["flow_url"]), j


def run_flow(client, key=LENIENT, *, selfie=b"A", signals=None, answers=None, do_challenges=True, submit=True):
    """Drive the whole end-user flow the way the verification page would."""
    vid, fh, _ = create(client, key)
    up = lambda kind, name, blob: client.post(f"/flow/{vid}/upload/{kind}", headers=fh, files={"file": (name, blob)})
    assert up("id_image", "id.jpg", b"A").status_code == 200
    assert up("selfie", "me.jpg", selfie).status_code == 200
    assert up("challenge_audio", "clip.webm", b"\x1aE\xdf\xa3" + b"\0" * 64).status_code == 200
    for ch in ("email", "phone"):
        dest = "asha@example.com" if ch == "email" else "+919999999999"
        code = client.post(f"/flow/{vid}/otp/send", headers=fh, json={"channel": ch, "destination": dest}).json()["dev_code"]
        assert client.post(f"/flow/{vid}/otp/verify", headers=fh, json={"channel": ch, "code": code}).status_code == 200
    assert client.post(f"/flow/{vid}/signals", headers=fh, json=signals or GOOD_SIGNALS).status_code == 200
    transcripts = answers or {"name": "my name is Asha Rao", "dob": "12 April 1999", "id_last4": "four eight two one"}
    if do_challenges:
        chs = client.post(f"/flow/{vid}/challenges", headers=fh).json()["challenges"]
        metrics = {
            "head_turn": {"yaw_range_deg": 40, "face_present_ratio": 0.95},
            "eye_blink": {"blink_count": 2, "face_present_ratio": 0.95},
            "hand_wave": {"occlusion_ratio": 0.3, "face_present_ratio_after": 0.95},
            "phrase": {}
        }
        r = client.post(f"/flow/{vid}/challenges/result", headers=fh,
                        json={"results": [{"id": c["id"], "metrics": metrics.get(c["type"], {})} for c in chs]})
        assert r.status_code == 200, r.text
        code = next(c["expected_code"] for c in chs if c["type"] == "phrase")
        transcripts = dict(transcripts, phrase=" ".join(code))
    assert client.post(f"/flow/{vid}/transcripts", headers=fh, json=transcripts).status_code == 200
    if submit:
        assert client.post(f"/flow/{vid}/submit", headers=fh).status_code == 202
    return vid, fh


def result(client, vid, key=LENIENT):
    return client.get(f"/v1/verifications/{vid}", headers=auth(key)).json()


# ---------------- happy path + attacks ----------------
def test_genuine_user_is_approved_on_both_policies(client, webhook_sink, fake_models):
    for key in (LENIENT, STRICT):
        vid, _ = run_flow(client, key)
        r = result(client, vid, key)
        assert r["status"] == "completed" and r["decision"] == "approved", r
        assert {c["name"]: c["status"] for c in r["results"]}["face_match"] == "pass"


def test_different_person_is_rejected_recommended(client, webhook_sink, fake_models):
    vid, _ = run_flow(client, selfie=b"B")
    r = result(client, vid)
    assert r["decision"] == "rejected_recommended" and "face_match" in r["reasons"][0]


def test_borderline_face_always_goes_to_a_human(client, webhook_sink, fake_models):
    for key in (LENIENT, STRICT):                            # face_match is must_pass in every policy
        vid, _ = run_flow(client, key, selfie=b"M")
        r = result(client, vid, key)
        assert r["decision"] == "needs_review" and "face_match" in r["reasons"][0]


def test_cloned_voice_policy_difference(client, webhook_sink, fake_models):
    fake_models["verdict"] = "fake"
    vid, _ = run_flow(client, LENIENT)
    assert result(client, vid)["decision"] == "needs_review"
    vid, _ = run_flow(client, STRICT)
    assert result(client, vid, STRICT)["decision"] == "rejected_recommended"


def test_virtual_camera_is_flagged(client, webhook_sink, fake_models):
    sig = {"camera_labels": ["OBS Virtual Camera"]}
    vid, _ = run_flow(client, LENIENT, signals=sig)
    assert result(client, vid)["decision"] == "needs_review"
    vid, _ = run_flow(client, STRICT, signals=sig)
    assert result(client, vid, STRICT)["decision"] == "rejected_recommended"


def test_wrong_spoken_details_need_review_never_auto_reject(client, webhook_sink, fake_models):
    vid, _ = run_flow(client, STRICT, answers={"name": "Rahul Sharma", "dob": "12 April 1999", "id_last4": "four eight two one"})
    r = result(client, vid, STRICT)
    assert r["decision"] == "needs_review" and "spoken_details" in r["reasons"][0]


def test_missing_steps_never_approve_strict(client, webhook_sink, fake_models):
    vid, _ = run_flow(client, STRICT, do_challenges=False)    # no liveness challenges completed
    assert result(client, vid, STRICT)["decision"] == "needs_review"


# ---------------- webhooks ----------------
def test_webhook_is_signed_complete_and_leaks_nothing(client, webhook_sink, fake_models):
    vid, fh = run_flow(client)
    assert len(webhook_sink["requests"]) == 1
    req = webhook_sink["requests"][0]
    body = req.content
    assert security.verify_signature("whsec_test", body, req.headers["x-kyc-signature"])
    ev = json.loads(body)
    assert ev["type"] == "verification.completed" and ev["data"]["id"] == vid and ev["data"]["decision"] == "approved"
    text = body.decode()
    token = fh["X-Flow-Token"]
    assert token not in text and "uploads" not in text and "flow_token_hash" not in text and "dev_code" not in text
    assert result(client, vid)["webhook"]["status"] == "delivered"


def test_webhook_failure_is_recorded_and_retried(client, webhook_sink, fake_models):
    webhook_sink["status"] = 500
    vid, _ = run_flow(client)
    assert len(webhook_sink["requests"]) == 3
    w = result(client, vid)["webhook"]
    assert w["status"] == "failed" and w["attempts"] == 3
    assert result(client, vid)["decision"] == "approved"      # a customer outage never changes the verdict


# ---------------- human review + deletion ----------------
def test_review_overrides_and_notifies(client, webhook_sink, fake_models):
    vid, _ = run_flow(client, selfie=b"B")
    n = len(webhook_sink["requests"])
    r = client.post(f"/v1/verifications/{vid}/review", headers=auth(LENIENT), json={"decision": "approved", "note": "checked ID in person"})
    assert r.status_code == 200 and r.json()["final_decision"] == "approved" and r.json()["decision"] == "rejected_recommended"
    assert json.loads(webhook_sink["requests"][n].content)["type"] == "verification.reviewed"
    assert client.post(f"/v1/verifications/{vid}/review", headers=auth(LENIENT), json={"decision": "approved"}).status_code == 409


def test_review_validation(client, webhook_sink, fake_models):
    vid, _, _ = create(client)
    assert client.post(f"/v1/verifications/{vid}/review", headers=auth(LENIENT), json={"decision": "approved"}).status_code == 409
    vid, _ = run_flow(client)
    assert client.post(f"/v1/verifications/{vid}/review", headers=auth(LENIENT), json={"decision": "maybe"}).status_code == 400


def test_delete_removes_record_and_files(client, webhook_sink, fake_models, tmp_path):
    vid, _ = run_flow(client)
    assert (tmp_path / "uploads" / vid).exists()
    assert client.delete(f"/v1/verifications/{vid}", headers=auth(LENIENT)).status_code == 204
    assert not (tmp_path / "uploads" / vid).exists()
    assert client.get(f"/v1/verifications/{vid}", headers=auth(LENIENT)).status_code == 404


# ---------------- auth, isolation, abuse ----------------
def test_api_key_auth_and_tenant_isolation(client, webhook_sink, fake_models):
    assert client.post("/v1/verifications", json={}).status_code == 401
    assert client.post("/v1/verifications", json={}, headers=auth("nope")).status_code == 401
    vid, _ = run_flow(client, LENIENT)
    assert client.get(f"/v1/verifications/{vid}", headers=auth(STRICT)).status_code == 404     # other tenant
    assert client.post(f"/v1/verifications/{vid}/review", headers=auth(STRICT), json={"decision": "approved"}).status_code == 404
    assert client.delete(f"/v1/verifications/{vid}", headers=auth(STRICT)).status_code == 404
    assert all(v["id"] != vid for v in client.get("/v1/verifications", headers=auth(STRICT)).json()["data"])


def test_unknown_policy_rejected(client):
    r = client.post("/v1/verifications", json={"policy": "yolo"}, headers=auth(LENIENT))
    assert r.status_code == 400


def test_flow_requires_the_right_token(client):
    vid, fh, _ = create(client)
    assert client.get(f"/flow/{vid}/context").status_code == 404
    assert client.get(f"/flow/{vid}/context", headers={"X-Flow-Token": "wrong"}).status_code == 404
    assert client.get(f"/flow/{vid}/context", headers=fh).status_code == 200
    other, ofh, _ = create(client)
    assert client.get(f"/flow/{vid}/context", headers=ofh).status_code == 404       # another session's token


def test_flow_link_expires(client, monkeypatch):
    monkeypatch.setenv("FLOW_TOKEN_TTL_S", "-1")
    vid, fh, _ = create(client)
    assert client.get(f"/flow/{vid}/context", headers=fh).status_code == 410


def test_context_lists_steps_for_the_policy(client):
    _, fh, j = create(client, LENIENT)
    vid = j["id"]
    steps = client.get(f"/flow/{vid}/context", headers=fh).json()["steps"]
    assert "upload_selfie" in steps and "email_otp" in steps
    _, fh2, j2 = create(client, STRICT)
    assert "liveness_challenges" in client.get(f"/flow/{j2['id']}/context", headers=fh2).json()["steps"]


def test_upload_validation(client, monkeypatch):
    vid, fh, _ = create(client)
    post = lambda kind, name, blob: client.post(f"/flow/{vid}/upload/{kind}", headers=fh, files={"file": (name, blob)})
    assert post("id_image", "id.exe", b"x").status_code == 415
    assert post("selfie", "me.wav", b"x").status_code == 415                  # audio into an image slot
    assert post("../../etc/passwd", "a.jpg", b"x").status_code in (400, 404)
    assert post("nonsense", "a.jpg", b"x").status_code == 400
    assert post("id_image", "id.jpg", b"").status_code == 400
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    assert post("id_image", "id.jpg", b"x" * (1024 * 1024 + 1)).status_code == 413
    r = post("id_image", "../../evil.jpg", b"x")                              # hostile filename: stored under a server-chosen name
    assert r.status_code == 200


def test_state_machine_blocks_edits_and_double_submit(client, webhook_sink, fake_models):
    vid, fh = run_flow(client)
    assert client.post(f"/flow/{vid}/submit", headers=fh).status_code == 409
    assert client.post(f"/flow/{vid}/upload/selfie", headers=fh, files={"file": ("me.jpg", b"B")}).status_code == 409
    assert client.post(f"/flow/{vid}/otp/send", headers=fh, json={"channel": "email", "destination": "a@b.co"}).status_code == 409


def test_otp_endpoints(client):
    vid, fh, _ = create(client)
    send = lambda: client.post(f"/flow/{vid}/otp/send", headers=fh, json={"channel": "email", "destination": "a@b.co"})
    assert client.post(f"/flow/{vid}/otp/verify", headers=fh, json={"channel": "email", "code": "123456"}).status_code == 400
    assert [send().status_code for _ in range(4)] == [200, 200, 200, 429]
    assert client.post(f"/flow/{vid}/otp/send", headers=fh, json={"channel": "fax", "destination": "x"}).status_code == 400


def test_challenge_replay_and_forgery_are_rejected(client):
    vid, fh, _ = create(client)
    chs = client.post(f"/flow/{vid}/challenges", headers=fh).json()["challenges"]
    item = {"id": chs[0]["id"], "metrics": {}}
    assert client.post(f"/flow/{vid}/challenges/result", headers=fh, json={"results": [item]}).status_code == 200
    assert client.post(f"/flow/{vid}/challenges/result", headers=fh, json={"results": [item]}).status_code == 400
    assert client.post(f"/flow/{vid}/challenges/result", headers=fh, json={"results": [{"id": "forged", "metrics": {}}]}).status_code == 400


def test_dev_transcripts_disabled_in_production(client, monkeypatch):
    monkeypatch.setenv("KYC_DEV_MODE", "0")
    vid, fh, _ = create(client)
    assert client.post(f"/flow/{vid}/transcripts", headers=fh, json={"name": "Asha Rao"}).status_code == 403
    r = client.post(f"/flow/{vid}/otp/send", headers=fh, json={"channel": "email", "destination": "a@b.co"})
    assert "dev_code" not in r.json()                                           # OTPs never echoed outside dev mode


def test_list_and_policies(client, webhook_sink, fake_models):
    run_flow(client)
    run_flow(client)
    assert len(client.get("/v1/verifications", headers=auth(LENIENT)).json()["data"]) == 2
    p = client.get("/v1/policies", headers=auth(STRICT)).json()
    assert p["default"] == "strict" and set(p["policies"]) == {"lenient", "strict"}
    assert client.get("/healthz").json()["ok"] is True
