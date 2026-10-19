"""Regression lock tests to guarantee zero unintended behavior change during suite hardening."""
import io
import re
import time
from pathlib import Path
import numpy as np
import cv2
import pytest

from app.models import PASS, FAIL, UNCERTAIN


def _make_dummy_video(tmp_path: Path, n_frames=10) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    v_path = tmp_path / "lock_clip.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(v_path), fourcc, 10.0, (120, 120))
    for i in range(n_frames):
        img = np.zeros((120, 120, 3), dtype=np.uint8)
        cv2.circle(img, (30 + i * 5, 60), 15, (255, 255, 255), -1)
        out.write(img)
    out.release()
    return v_path


def _make_dummy_audio(tmp_path: Path) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    import wave
    a_path = tmp_path / "lock_audio.wav"
    with wave.open(str(a_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        t = np.linspace(0, 1, 16000, endpoint=False)
        data = (np.sin(2 * np.pi * 440 * t) * 10000).astype(np.int16)
        wf.writeframes(data.tobytes())
    return a_path


def test_lock_kyc_full_lifecycle(client, fake_models):
    headers = {"Authorization": "Bearer kyc_demo_lenient_key"}
    
    # 1. Create verification
    res = client.post("/v1/verifications", headers=headers, json={
        "reference_id": "ref_regression_lock_1",
        "expected": {"name": "Alice Smith", "dob": "1995-01-01", "id_last4": "1234"}
    })
    assert res.status_code == 201, res.text
    v = res.json()
    vid = v["id"]
    assert vid.startswith("ver_")
    assert "flow_url" in v
    token = re.search(r"[?&]t=([^&]+)", v["flow_url"]).group(1)
    
    # 2. Get flow context with token
    f_headers = {"X-Flow-Token": token}
    ctx_res = client.get(f"/flow/{vid}/context", headers=f_headers)
    assert ctx_res.status_code == 200
    ctx = ctx_res.json()
    assert ctx["id"] == vid
    assert "steps" in ctx
    assert "policy" in ctx
    
    # 3. Post signals
    sig_res = client.post(f"/flow/{vid}/signals", headers=f_headers, json={
        "camera_labels": ["FaceTime HD Camera"],
        "focus_loss_count": 0
    })
    assert sig_res.status_code == 200
    assert sig_res.json()["stored"] is True
    
    # 4. Upload id and selfie
    up_id = client.post(f"/flow/{vid}/upload/id_image", headers=f_headers,
                        files={"file": ("id.jpg", b"A fake id image data", "image/jpeg")})
    assert up_id.status_code == 200
    assert up_id.json()["stored"] == "id_image"
    
    up_selfie = client.post(f"/flow/{vid}/upload/selfie", headers=f_headers,
                            files={"file": ("selfie.jpg", b"A fake selfie image data", "image/jpeg")})
    assert up_selfie.status_code == 200
    assert up_selfie.json()["stored"] == "selfie"
    
    # 5. Submit flow
    sub_res = client.post(f"/flow/{vid}/submit", headers=f_headers)
    assert sub_res.status_code == 202
    
    # 6. Fetch verification status via tenant API
    v_res = client.get(f"/v1/verifications/{vid}", headers=headers)
    assert v_res.status_code == 200
    v_data = v_res.json()
    assert v_data["id"] == vid
    assert v_data["status"] in ("completed", "passed", "failed", "review_recommended", "expired", "initiated")
    assert "results" in v_data
    
    # 7. Review verification
    rev_res = client.post(f"/v1/verifications/{vid}/review", headers=headers, json={
        "decision": "approved",
        "note": "Locked regression test pass"
    })
    assert rev_res.status_code == 200
    assert rev_res.json()["final_decision"] == "approved"


def test_lock_interview_full_lifecycle(client, tmp_path, monkeypatch):
    headers = {"Authorization": "Bearer kyc_demo_lenient_key"}
    
    # 1. Create interview session
    res = client.post("/v1/interviews", headers=headers, json={
        "candidate_id": "cand_lock_99",
        "metadata": {"role": "Security Engineer"}
    })
    assert res.status_code == 200, res.text
    iv = res.json()
    interview_id = iv["id"]
    token = iv["token"]
    
    iv_headers = {"X-Interview-Token": token}
    
    # 2. Check initial summary
    sum_res = client.get(f"/v1/interviews/{interview_id}/summary", headers=iv_headers)
    assert sum_res.status_code == 200
    assert sum_res.json()["total_clips"] == 0
    assert sum_res.json()["status"] == "active"
    
    # 3. Post a clip with video + loopback + mic
    v_file = _make_dummy_video(tmp_path)
    a_file = _make_dummy_audio(tmp_path)
    
    with open(v_file, "rb") as vf, open(a_file, "rb") as af, open(a_file, "rb") as mf:
        clip_res = client.post(
            f"/v1/interviews/{interview_id}/clips",
            headers=iv_headers,
            files={
                "video": ("clip.mp4", vf, "video/mp4"),
                "audio": ("audio.wav", af, "audio/wav"),
                "mic_audio": ("mic.wav", mf, "audio/wav")
            },
            data={"round": 1}
        )
    assert clip_res.status_code == 200, clip_res.text
    clip_data = clip_res.json()
    assert "clip_id" in clip_data
    assert "checks" in clip_data
    assert len(clip_data["checks"]) == 7
    
    for chk in clip_data["checks"]:
        assert "name" in chk
        assert "status" in chk
        assert "score" in chk
        assert "confidence" in chk
        assert "reason" in chk
        assert "details" in chk
        assert chk["status"] in (PASS, FAIL, UNCERTAIN)
    
    # 4. End interview
    end_res = client.post(f"/v1/interviews/{interview_id}/end", headers=iv_headers)
    assert end_res.status_code == 200
    assert end_res.json()["status"] == "completed"
    
    # 5. Summary reflects completed
    final_summary = client.get(f"/v1/interviews/{interview_id}/summary", headers=iv_headers).json()
    assert final_summary["status"] == "completed"
    assert final_summary["total_clips"] == 1


def test_lock_checks_error_returns_uncertain():
    """Rule: A check that errors or lacks data returns uncertain, never pass."""
    from app.checks import video_deepfake, lip_sync, interview_loop
    
    # Insufficient crops or missing path in video deepfake
    res_df = video_deepfake.evaluate_video_deepfake(Path("non_existent_file.mp4"))
    assert res_df.status in (UNCERTAIN, "skipped")
    
    # Missing weights / error in lip_sync returns uncertain
    res_ls = lip_sync.evaluate_lip_sync(Path("non_existent_v.mp4"))
    assert res_ls.status in (UNCERTAIN, "skipped")
    
    # Missing video in interview loop
    res_loop = interview_loop.evaluate_interview_loop(Path("non_existent_loop.mp4"))
    assert res_loop.status == UNCERTAIN
