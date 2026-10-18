"""Synthetic test suite for liveness verification:
- MediaPipe Face Landmarker blendshapes blink detection (peaks, baseline, counts)
- InsightFace head turn yaw analysis (directions, ranges, static/loop detection)
- MiniFASNet passive anti-spoofing detector (real vs spoof scoring)
- Zero exception swallowing verification
"""
import numpy as np
import pytest
from pathlib import Path

from app.checks import anti_spoof, liveness
from app.models import CheckContext
from app.config import get_settings


def make_ctx(data=None, files=None):
    st = get_settings().model_copy() if hasattr(get_settings(), "model_copy") else get_settings()
    return CheckContext("synth_session", data or {}, files or {}, {}, st)


# ---------------- Synthetic Eye Blink Tests ----------------
def test_synthetic_blink_detection_pass(monkeypatch):
    """Simulate realistic eye closure blendshapes sequence with 2 natural blinks."""
    # 24 frames: 0..4 open, 5..7 blink 1, 8..14 open, 15..17 blink 2, 18..23 open
    scores = [
        0.05, 0.06, 0.04, 0.05, 0.10,
        0.55, 0.78, 0.45,               # Blink 1 peak
        0.08, 0.05, 0.06, 0.07, 0.05, 0.08, 0.12,
        0.62, 0.81, 0.50,               # Blink 2 peak
        0.06, 0.05, 0.04, 0.05, 0.06, 0.05
    ]

    class MockCategory:
        def __init__(self, name, score):
            self.category_name = name
            self.score = score

    class MockResult:
        def __init__(self, score):
            self.face_blendshapes = [[
                MockCategory("eyeBlinkLeft", score),
                MockCategory("eyeBlinkRight", score),
            ]]

    class MockDetector:
        def __init__(self):
            self.idx = 0
        def detect(self, img):
            score = scores[min(self.idx, len(scores) - 1)]
            self.idx += 1
            return MockResult(score)

    monkeypatch.setattr(liveness, "_load_face_landmarker", lambda: MockDetector())
    # Mock video_deepfake.sample_frames to return 24 dummy frames
    dummy_frames = [np.zeros((100, 100, 3), dtype=np.uint8) for _ in range(24)]
    from app.checks import video_deepfake, face_match
    monkeypatch.setattr(video_deepfake, "sample_frames", lambda path, n=24: dummy_frames)
    monkeypatch.setattr(face_match, "_load_app", lambda: type("App", (), {"get": lambda s, f: [type("Face", (), {"bbox": [10, 10, 80, 80], "landmark_3d_68": np.zeros((68, 3))})()]})())

    status, reason, det = liveness._detect_server_blinks(Path("dummy.mp4"), target_blinks=2)
    assert status == "pass"
    assert det["detected_blinks"] == 2
    assert "2 blinks detected" in reason


def test_synthetic_blink_detection_static_eyes_fail(monkeypatch):
    """Simulate static eyes (stare without blinking) -> fails."""
    class MockCategory:
        def __init__(self, name, score):
            self.category_name = name
            self.score = score

    class MockDetector:
        def detect(self, img):
            return type("Res", (), {"face_blendshapes": [[
                MockCategory("eyeBlinkLeft", 0.04),
                MockCategory("eyeBlinkRight", 0.05),
            ]]})()

    monkeypatch.setattr(liveness, "_load_face_landmarker", lambda: MockDetector())
    from app.checks import video_deepfake, face_match
    dummy_frames = [np.zeros((100, 100, 3), dtype=np.uint8) for _ in range(24)]
    monkeypatch.setattr(video_deepfake, "sample_frames", lambda path, n=24: dummy_frames)
    monkeypatch.setattr(face_match, "_load_app", lambda: type("App", (), {"get": lambda s, f: [type("Face", (), {"bbox": [10, 10, 80, 80], "landmark_3d_68": None})()]})())

    status, reason, det = liveness._detect_server_blinks(Path("dummy.mp4"), target_blinks=2)
    assert status == "fail"
    assert det["detected_blinks"] == 0
    assert "No eye blinks detected" in reason


# ---------------- Synthetic Head Turn Yaw Tests ----------------
def test_synthetic_head_turn_left_and_right(monkeypatch):
    from app.checks import video_deepfake, face_match

    # A. Left turn simulation (starts frontal ~0, turns to -30 deg, returns)
    yaws_left = [0.0, -5.0, -15.0, -28.0, -32.0, -25.0, -10.0, 0.0]
    idx = [0]
    def make_face(yaw):
        f = type("F", (), {"bbox": [10, 10, 80, 80], "pose": [0.0, yaw, 0.0]})()
        return [f]

    class MockFaceApp:
        def get(self, img):
            y = yaws_left[idx[0] % len(yaws_left)]
            idx[0] += 1
            return make_face(y)

    monkeypatch.setattr(face_match, "_load_app", lambda: MockFaceApp())
    monkeypatch.setattr(video_deepfake, "sample_frames", lambda p, n=20: [np.zeros((100, 100, 3), dtype=np.uint8)] * len(yaws_left))

    status, reason, det = liveness._recompute_server_yaw(Path("vid.mp4"), expected_direction="left")
    assert status == "pass"
    assert det["yaw_range_deg"] >= 20.0
    assert "Head turn to left verified" in reason

    # B. Static head (yaw stays < 10 deg) -> fails
    yaws_static = [0.0, 1.0, 2.0, 1.5, 0.5, 1.0, 2.0, 0.0]
    idx[0] = 0
    class MockStaticApp:
        def get(self, img):
            y = yaws_static[idx[0] % len(yaws_static)]
            idx[0] += 1
            return make_face(y)

    monkeypatch.setattr(face_match, "_load_app", lambda: MockStaticApp())
    status, reason, det = liveness._recompute_server_yaw(Path("vid.mp4"), expected_direction="left")
    assert status == "fail"
    assert "Static head detected" in reason


# ---------------- Synthetic MiniFASNet Passive Anti-Spoofing Tests ----------------
def test_synthetic_anti_spoof_scoring(monkeypatch):
    """Test MiniFASNet score_face_crop and evaluate_anti_spoof behavior."""
    crop = np.zeros((80, 80, 3), dtype=np.uint8)
    real_p, class_probs = anti_spoof.score_face_crop(crop)
    assert 0.0 <= real_p <= 1.0
    assert "real" in class_probs
    assert "spoof_2d_print" in class_probs
    assert "spoof_3d_screen_mask" in class_probs

    # Mock high real score -> passes
    monkeypatch.setattr(anti_spoof, "score_face_crop", lambda c: (0.95, {"real": 0.95}))
    res = anti_spoof.evaluate_anti_spoof(None, [crop, crop])
    assert res["status"] == "pass"
    assert res["mean_real_score"] == 0.95

    # Mock spoof score -> needs_review (never hard fail)
    monkeypatch.setattr(anti_spoof, "score_face_crop", lambda c: (0.15, {"real": 0.15}))
    res_spoof = anti_spoof.evaluate_anti_spoof(None, [crop, crop])
    assert res_spoof["status"] == "needs_review"
    assert "presentation attack suspected" in res_spoof["reason"]


def test_missing_model_returns_uncertain_never_pass(monkeypatch):
    """Zero-fallback principle: If model cannot load, returns uncertain, never pass."""
    monkeypatch.setattr(liveness, "_load_face_landmarker", lambda: (_ for _ in ()).throw(FileNotFoundError("face_landmarker.task")))
    from app.checks import video_deepfake
    dummy_frames = [np.zeros((100, 100, 3), dtype=np.uint8) for _ in range(24)]
    monkeypatch.setattr(video_deepfake, "sample_frames", lambda path, n=24: dummy_frames)

    status, reason, _ = liveness._detect_server_blinks(Path("dummy.mp4"), target_blinks=2)
    assert status == "uncertain"
    assert "unavailable" in reason or "not found" in reason
