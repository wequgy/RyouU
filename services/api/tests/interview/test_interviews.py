"""Tests for Interview Overlay API endpoints and checks."""
import io
import time
from pathlib import Path
import pytest
import numpy as np
import cv2

from app.models import PASS, FAIL, UNCERTAIN
from app.checks import interview_loop, interview_voice_auth, interview_face_id


def _create_synthetic_video(tmp_path: Path, n_frames=16, frozen=False) -> Path:
    """Create a temporary mp4 video file with moving or static circles."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    v_path = tmp_path / "test_clip.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(v_path), fourcc, 10.0, (160, 160))
    for i in range(n_frames):
        img = np.zeros((160, 160, 3), dtype=np.uint8)
        pos = (80, 80) if frozen else (40 + i * 5, 80)
        cv2.circle(img, pos, 20, (255, 255, 255), -1)
        out.write(img)
    out.release()
    return v_path


def _create_synthetic_audio(tmp_path: Path, silent=False) -> Path:
    """Create a temporary wav file with tone or silence."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    import wave
    a_path = tmp_path / "test_audio.wav"
    with wave.open(str(a_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        if silent:
            data = np.zeros(16000 * 2, dtype=np.int16)
        else:
            t = np.linspace(0, 2, 16000 * 2, endpoint=False)
            data = (np.sin(2 * np.pi * 440 * t) * 16000).astype(np.int16)
        wf.writeframes(data.tobytes())
    return a_path


def test_interview_session_lifecycle(client):
    headers = {"Authorization": "Bearer kyc_demo_lenient_key"}
    
    # 1. Create interview session
    res = client.post("/v1/interviews", headers=headers, json={
        "candidate_id": "cand_12345",
        "metadata": {"job_title": "Senior Engineer"}
    })
    assert res.status_code == 200, res.text
    data = res.json()
    assert "id" in data
    assert "token" in data
    assert data["candidate_id"] == "cand_12345"
    
    interview_id = data["id"]
    token = data["token"]
    
    # 2. Access with token
    iv_headers = {"X-Interview-Token": token}
    summary_res = client.get(f"/v1/interviews/{interview_id}/summary", headers=iv_headers)
    assert summary_res.status_code == 200
    summary = summary_res.json()
    assert summary["total_clips"] == 0
    assert summary["status"] == "active"
    
    # 3. Invalid token rejected
    bad_res = client.get(f"/v1/interviews/{interview_id}/summary", headers={"X-Interview-Token": "bad_token"})
    assert bad_res.status_code == 401
    
    # 4. End interview
    end_res = client.post(f"/v1/interviews/{interview_id}/end", headers=iv_headers)
    assert end_res.status_code == 200
    assert end_res.json()["status"] == "completed"
    
    # After end, uploads are rejected
    dummy_video = io.BytesIO(b"fake video data")
    upload_res = client.post(
        f"/v1/interviews/{interview_id}/clips",
        headers=iv_headers,
        files={"video": ("clip.webm", dummy_video, "video/webm")},
        data={"round": 1}
    )
    assert upload_res.status_code == 400


def test_interview_clip_upload_and_checks(client, tmp_path, monkeypatch):
    headers = {"Authorization": "Bearer kyc_demo_lenient_key"}
    init = client.post("/v1/interviews", headers=headers, json={"candidate_id": "cand_abc"}).json()
    interview_id = init["id"]
    token = init["token"]
    iv_headers = {"X-Interview-Token": token}
    
    # Create test video and audio
    v_path = _create_synthetic_video(tmp_path, n_frames=16, frozen=False)
    a_path = _create_synthetic_audio(tmp_path, silent=False)
    
    with open(v_path, "rb") as vf, open(a_path, "rb") as af:
        res = client.post(
            f"/v1/interviews/{interview_id}/clips",
            headers=iv_headers,
            files={
                "video": ("clip.mp4", vf, "video/mp4"),
                "audio": ("clip.wav", af, "audio/wav")
            },
            data={"round": 1, "meeting_app": "Zoom", "resolution": "1280x720"}
        )
    assert res.status_code == 200, res.text
    clip_data = res.json()
    assert clip_data["status"] == "completed"
    assert clip_data["round"] == 1
    assert "overall_recommendation" in clip_data
    assert "interviewer_action" in clip_data
    assert len(clip_data["checks"]) == 7
    
    # Verify check contracts
    for chk in clip_data["checks"]:
        assert "name" in chk
        assert "status" in chk
        assert "score" in chk
        assert "confidence" in chk
        assert "reason" in chk
        assert "details" in chk
        assert chk["status"] in (PASS, FAIL, UNCERTAIN)
    
    # Verify clip retrieval
    clip_id = clip_data["clip_id"]
    get_res = client.get(f"/v1/interviews/{interview_id}/clips/{clip_id}", headers=iv_headers)
    assert get_res.status_code == 200
    assert get_res.json()["clip_id"] == clip_id
    
    # Verify summary aggregation
    summary_res = client.get(f"/v1/interviews/{interview_id}/summary", headers=iv_headers)
    assert summary_res.status_code == 200
    summary = summary_res.json()
    assert summary["total_clips"] == 1
    assert len(summary["timeline"]) == 1


def test_loop_check_detection(tmp_path):
    # 1. Natural motion video
    moving_video = _create_synthetic_video(tmp_path / "mov", n_frames=16, frozen=False)
    res_moving = interview_loop.evaluate_interview_loop(moving_video)
    assert res_moving.status == PASS
    assert "Natural continuous motion" in res_moving.reason
    
    # 2. Frozen video
    frozen_video = _create_synthetic_video(tmp_path / "frz", n_frames=16, frozen=True)
    res_frozen = interview_loop.evaluate_interview_loop(frozen_video)
    assert res_frozen.status == FAIL
    assert "Frozen or static" in res_frozen.reason
    assert res_frozen.details.get("frozen") is True


def test_voice_auth_silence_gating(tmp_path):
    silent_audio = _create_synthetic_audio(tmp_path, silent=True)
    
    class DummySettings:
        detectif_api_key = "test_key"
        detectif_base_url = "https://api.detectif.ai"
    
    res = interview_voice_auth.evaluate_interview_voice_auth(silent_audio, "iv_test", DummySettings())
    assert res.status == UNCERTAIN
    assert "silent or contains insufficient speech" in res.reason


def test_overlay_security_and_assets():
    """Verify overlay client security posture and dependency pinning."""
    import json
    overlay_dir = Path("apps/overlay")
    pkg_path = overlay_dir / "package.json"
    assert pkg_path.exists()
    pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
    
    # Dependencies must be pinned to exact version (no caret / wildcard)
    electron_ver = pkg.get("devDependencies", {}).get("electron", "")
    assert electron_ver != "*" and not electron_ver.startswith("^") and not electron_ver.startswith("~")
    assert int(electron_ver.split(".")[0]) >= 32
    
    # HTML security posture (CSP)
    index_html = (overlay_dir / "src/renderer/index.html").read_text(encoding="utf-8")
    assert "Content-Security-Policy" in index_html
    assert "default-src 'self'" in index_html
    
    # No obsolete Python scripts in client
    assert not (overlay_dir / "src/main/verify_deepfake.py").exists()
    assert not (overlay_dir / "src/main/detectifai_verifier.py").exists()
    assert not (overlay_dir / "src/main/supabase_gateway.py").exists()

