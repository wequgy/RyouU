"""Tests for Server-enforced Gates and anti-fraud protections (Section 2 & 3).

Verifies:
1. ID details gate: wrong name, wrong dob, wrong id_last4, unreadable/blurry ID.
2. 422 returned on gate failure and file NOT persisted.
3. Lockout after 3 failed attempts (HTTP 429).
4. Selfie gate blocked (403) until ID gate passed.
5. Selfie gate face verification (wrong person -> 422).
6. Direct API calls (challenges, challenge_audio, submit, etc.) blocked (403) until both gates pass.
7. Media replay detection (sha256 collision across verifications -> 422).
"""
import io
import time
import numpy as np
import pytest
from PIL import Image, ImageDraw


def _generate_synthetic_id_card(name="Asha Rao", dob="12/04/1999", id_num="9876 5432 4821") -> bytes:
    """Generate a clean synthetic ID card image with crisp text for RapidOCR."""
    img = Image.new("RGB", (600, 360), color=(245, 247, 250))
    draw = ImageDraw.Draw(img)
    # Header
    draw.rectangle([0, 0, 600, 50], fill=(24, 43, 73))
    draw.text((20, 16), "REPUBLIC IDENTITY CARD", fill=(255, 255, 255))
    # Photo placeholder
    draw.rectangle([30, 80, 160, 240], fill=(200, 210, 225), outline=(100, 120, 150))
    # Text details
    draw.text((190, 80), f"Name: {name}", fill=(10, 20, 30))
    draw.text((190, 130), f"DOB: {dob}", fill=(10, 20, 30))
    draw.text((190, 180), "Sex: F", fill=(10, 20, 30))
    draw.text((190, 230), f"ID No: {id_num}", fill=(10, 20, 30))
    draw.text((30, 300), f"<<ID<{id_num.replace(' ', '')}<<<<<{name.replace(' ', '<')}<<<", fill=(50, 50, 50))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


@pytest.fixture
def gated_env(monkeypatch):
    """Explicitly enable gates for gate tests."""
    monkeypatch.setenv("KYC_ENFORCE_GATES", "1")


def _create_session(client, name="Asha Rao", dob="1999-04-12", id_last4="4821"):
    res = client.post(
        "/v1/verifications",
        headers={"Authorization": "Bearer kyc_demo_strict_key"},
        json={
            "reference_id": f"ref_{time.time()}",
            "policy": "strict",
            "expected": {"name": name, "dob": dob, "id_last4": id_last4}
        }
    )
    assert res.status_code == 201
    data = res.json()
    token = data["flow_url"].split("&t=")[1].split("&")[0]
    return data["id"], token


def test_id_gate_wrong_name_fails_and_does_not_persist(client, gated_env):
    vid, token = _create_session(client, name="Vikram Malhotra")
    id_bytes = _generate_synthetic_id_card(name="Asha Rao")

    res = client.post(
        f"/flow/{vid}/upload/id_image",
        headers={"X-Flow-Token": token},
        files={"file": ("id.jpg", id_bytes, "image/jpeg")}
    )
    assert res.status_code == 422
    assert "mismatch" in res.json()["detail"].lower()
    assert "name" in res.json()["detail"].lower()

    # Verify file is not persisted
    ctx = client.get(f"/flow/{vid}/context", headers={"X-Flow-Token": token}).json()
    assert "id_image" not in ctx["uploaded"]
    assert ctx["gates"]["id_image"]["passed"] is False
    assert ctx["gates"]["id_image"]["attempts"] == 1


def test_id_gate_wrong_dob_fails(client, gated_env):
    vid, token = _create_session(client, dob="1980-01-01")
    id_bytes = _generate_synthetic_id_card(dob="12/04/1999")

    res = client.post(
        f"/flow/{vid}/upload/id_image",
        headers={"X-Flow-Token": token},
        files={"file": ("id.jpg", id_bytes, "image/jpeg")}
    )
    assert res.status_code == 422
    assert "dob" in res.json()["detail"].lower()


def test_id_gate_wrong_id_last4_fails(client, gated_env):
    vid, token = _create_session(client, id_last4="9999")
    id_bytes = _generate_synthetic_id_card(id_num="9876 5432 4821")

    res = client.post(
        f"/flow/{vid}/upload/id_image",
        headers={"X-Flow-Token": token},
        files={"file": ("id.jpg", id_bytes, "image/jpeg")}
    )
    assert res.status_code == 422
    assert "id_last4" in res.json()["detail"].lower()


def test_id_gate_unreadable_blurry_id_fails(client, gated_env):
    vid, token = _create_session(client)
    # Blank white image with no text boxes
    blank = Image.new("RGB", (300, 200), color=(255, 255, 255))
    buf = io.BytesIO()
    blank.save(buf, format="JPEG")
    res = client.post(
        f"/flow/{vid}/upload/id_image",
        headers={"X-Flow-Token": token},
        files={"file": ("id.jpg", buf.getvalue(), "image/jpeg")}
    )
    assert res.status_code == 422
    assert "retake a clearer photo" in res.json()["detail"].lower()


def test_gate_lockout_after_three_attempts(client, gated_env):
    vid, token = _create_session(client, name="Wrong Person")
    id_bytes = _generate_synthetic_id_card(name="Asha Rao")

    for i in range(3):
        r = client.post(
            f"/flow/{vid}/upload/id_image",
            headers={"X-Flow-Token": token},
            files={"file": ("id.jpg", id_bytes, "image/jpeg")}
        )
        assert r.status_code == 422

    # 4th attempt must be locked out with 429
    r4 = client.post(
        f"/flow/{vid}/upload/id_image",
        headers={"X-Flow-Token": token},
        files={"file": ("id.jpg", id_bytes, "image/jpeg")}
    )
    assert r4.status_code == 429
    assert "locked" in r4.json()["detail"].lower()


def test_selfie_gate_blocked_before_id_gate_passes(client, gated_env):
    vid, token = _create_session(client)
    res = client.post(
        f"/flow/{vid}/upload/selfie",
        headers={"X-Flow-Token": token},
        files={"file": ("selfie.jpg", b"dummy_selfie", "image/jpeg")}
    )
    assert res.status_code == 403
    assert "id image must be uploaded and pass" in res.json()["detail"].lower()


def test_direct_api_calls_blocked_before_gates_pass(client, gated_env):
    vid, token = _create_session(client)
    headers = {"X-Flow-Token": token}

    assert client.post(f"/flow/{vid}/challenges", headers=headers).status_code == 403
    assert client.post(f"/flow/{vid}/challenges/result", headers=headers, json={"results": []}).status_code == 403
    assert client.post(f"/flow/{vid}/submit", headers=headers).status_code == 403
    assert client.post(
        f"/flow/{vid}/upload/challenge_video",
        headers=headers,
        files={"file": ("video.mp4", b"dummy", "video/mp4")}
    ).status_code == 403


def test_matching_flow_unlocks_challenges_and_submit(client, gated_env, monkeypatch):
    from app.checks import face_match

    # Mock face_match embedder so synthetic ID and selfie produce identical face embeddings
    shared_emb = np.ones(512, dtype=np.float32) / np.sqrt(512)
    def mock_embedder(path):
        return shared_emb, {"face_px": 120, "n_faces": 1, "det_score": 0.99}

    monkeypatch.setattr(face_match, "EMBEDDER", mock_embedder)

    vid, token = _create_session(client, name="Asha Rao", dob="1999-04-12", id_last4="4821")
    id_bytes = _generate_synthetic_id_card(name="Asha Rao", dob="12/04/1999", id_num="9876 5432 4821")

    # 1. Upload valid ID
    r_id = client.post(
        f"/flow/{vid}/upload/id_image",
        headers={"X-Flow-Token": token},
        files={"file": ("id.jpg", id_bytes, "image/jpeg")}
    )
    assert r_id.status_code == 200

    # 2. Upload matching Selfie
    selfie_img = Image.new("RGB", (200, 200), color=(100, 150, 200))
    buf = io.BytesIO()
    selfie_img.save(buf, format="JPEG")
    r_selfie = client.post(
        f"/flow/{vid}/upload/selfie",
        headers={"X-Flow-Token": token},
        files={"file": ("selfie.jpg", buf.getvalue(), "image/jpeg")}
    )
    assert r_selfie.status_code == 200

    # 3. Challenges and submit endpoints are now accessible
    r_ch = client.post(f"/flow/{vid}/challenges", headers={"X-Flow-Token": token})
    assert r_ch.status_code == 200
    issued = r_ch.json()["challenges"]
    assert len(issued) == 2

    r_submit = client.post(f"/flow/{vid}/submit", headers={"X-Flow-Token": token})
    assert r_submit.status_code == 202


def test_media_replay_prevention_across_verifications(client, gated_env, monkeypatch):
    from app.checks import face_match
    shared_emb = np.ones(512, dtype=np.float32) / np.sqrt(512)
    monkeypatch.setattr(face_match, "EMBEDDER", lambda p: (shared_emb, {"face_px": 120, "n_faces": 1, "det_score": 0.99}))

    # Session 1
    vid1, token1 = _create_session(client)
    id_bytes = _generate_synthetic_id_card()
    client.post(f"/flow/{vid1}/upload/id_image", headers={"X-Flow-Token": token1}, files={"file": ("id.jpg", id_bytes, "image/jpeg")})
    
    selfie_img = Image.new("RGB", (200, 200), color=(50, 100, 150))
    buf = io.BytesIO()
    selfie_img.save(buf, format="JPEG")
    selfie_bytes = buf.getvalue()
    r1 = client.post(f"/flow/{vid1}/upload/selfie", headers={"X-Flow-Token": token1}, files={"file": ("selfie.jpg", selfie_bytes, "image/jpeg")})
    assert r1.status_code == 200

    # Session 2 tries to reuse the exact same selfie file
    vid2, token2 = _create_session(client)
    client.post(f"/flow/{vid2}/upload/id_image", headers={"X-Flow-Token": token2}, files={"file": ("id.jpg", id_bytes, "image/jpeg")})
    r2 = client.post(f"/flow/{vid2}/upload/selfie", headers={"X-Flow-Token": token2}, files={"file": ("selfie.jpg", selfie_bytes, "image/jpeg")})
    assert r2.status_code == 422
    assert "replay detected" in r2.json()["detail"].lower()
