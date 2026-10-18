"""Passive face anti-spoofing detector using MiniFASNetV2 (Silent-Face-Anti-Spoofing).

Evaluates applicant selfie and frontal frames (yaw <= 30 deg) from challenge video.
Distinguishes genuine live human faces from 2D print attacks, screen replays, and 3D masks.

NOTE: Thresholds are marked UNCALIBRATED until validated on production presentation attacks.
Signal only: Can only push a verification session to `needs_review`, never `rejected_recommended`.
"""
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import cv2
import numpy as np

logger = logging.getLogger(__name__)

MODEL_PATH = Path("models/minifasnet_v2.onnx")
_SESSION = None

# Classification thresholds (UNCALIBRATED)
# MiniFASNet outputs 3 classes: [0: 2D spoof, 1: Real face, 2: 3D spoof]
REAL_THRESHOLD = 0.50  # UNCALIBRATED: Real face probability required to pass


def _load_session():
    global _SESSION
    if _SESSION is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(f"MiniFASNet model not found at {MODEL_PATH}")
        import onnxruntime as ort
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        _SESSION = ort.InferenceSession(str(MODEL_PATH), opts)
    return _SESSION


def crop_face_multiscale(img_bgr: np.ndarray, bbox: List[float], scale: float = 2.7) -> Optional[np.ndarray]:
    """Crop face bounding box expanded by a multi-scale factor (2.7x) for MiniFASNet."""
    try:
        x1, y1, x2, y2 = bbox[:4]
        w, h = x2 - x1, y2 - y1
        cx, cy = x1 + w / 2.0, y1 + h / 2.0

        side = max(w, h) * scale
        new_x1 = max(0, int(cx - side / 2.0))
        new_y1 = max(0, int(cy - side / 2.0))
        new_x2 = min(img_bgr.shape[1], int(cx + side / 2.0))
        new_y2 = min(img_bgr.shape[0], int(cy + side / 2.0))

        if new_x2 <= new_x1 or new_y2 <= new_y1:
            return None
        cropped = img_bgr[new_y1:new_y2, new_x1:new_x2]
        return cv2.resize(cropped, (80, 80))
    except Exception as e:
        logger.warning(f"Failed to crop face for anti-spoofing: {e}")
        return None


def score_face_crop(face_80x80: np.ndarray) -> Tuple[float, Dict[str, float]]:
    """Score an 80x80 BGR face crop with MiniFASNet.
    
    Returns:
        (real_prob, class_probs_dict)
    """
    session = _load_session()
    blob = face_80x80.astype(np.float32).transpose(2, 0, 1)[np.newaxis, ...]
    inp_name = session.get_inputs()[0].name
    logits = session.run(None, {inp_name: blob})[0][0]

    # Softmax
    e_x = np.exp(logits - np.max(logits))
    probs = e_x / e_x.sum()
    spoof2d, real, spoof3d = float(probs[0]), float(probs[1]), float(probs[2])

    return real, {
        "real": round(real, 4),
        "spoof_2d_print": round(spoof2d, 4),
        "spoof_3d_screen_mask": round(spoof3d, 4),
    }


def evaluate_anti_spoof(selfie_path: Optional[Path], frontal_crops: List[np.ndarray]) -> Dict[str, Any]:
    """Run passive anti-spoofing on selfie and video frontal frames."""
    scores = []
    frames_scored = 0

    try:
        # 1. Score selfie if available
        if selfie_path and Path(selfie_path).exists():
            img = cv2.imread(str(selfie_path))
            if img is not None:
                from . import face_match
                app = face_match._load_app()
                faces = app.get(img)
                if faces:
                    f = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
                    crop = crop_face_multiscale(img, f.bbox, scale=2.7)
                    if crop is not None:
                        real_p, _ = score_face_crop(crop)
                        scores.append(real_p)
                        frames_scored += 1

        # 2. Score video frontal crops
        for crop in frontal_crops[:8]:
            if crop is not None:
                resized = cv2.resize(crop, (80, 80))
                real_p, _ = score_face_crop(resized)
                scores.append(real_p)
                frames_scored += 1

    except Exception as e:
        logger.warning(f"MiniFASNet anti-spoof evaluation failed: {e}")
        return {
            "status": "uncertain",
            "reason": f"MiniFASNet anti-spoofing error: {e}",
            "frames_scored": frames_scored,
            "mean_real_score": 0.0,
            "threshold": REAL_THRESHOLD,
            "threshold_state": "UNCALIBRATED",
        }

    if not scores:
        return {
            "status": "uncertain",
            "reason": "No usable face frames for anti-spoofing",
            "frames_scored": 0,
            "mean_real_score": 0.0,
            "threshold": REAL_THRESHOLD,
            "threshold_state": "UNCALIBRATED",
        }

    mean_real = float(np.mean(scores))
    min_real = float(np.min(scores))

    # Signal only: if below threshold, triggers needs_review (never hard reject)
    if mean_real < REAL_THRESHOLD or min_real < (REAL_THRESHOLD * 0.7):
        return {
            "status": "needs_review",
            "reason": f"Passive anti-spoofing warning: presentation attack suspected (real score {mean_real:.2f})",
            "frames_scored": frames_scored,
            "mean_real_score": round(mean_real, 4),
            "min_real_score": round(min_real, 4),
            "threshold": REAL_THRESHOLD,
            "threshold_state": "UNCALIBRATED",
        }

    return {
        "status": "pass",
        "reason": f"Passive anti-spoofing passed (real score {mean_real:.2f})",
        "frames_scored": frames_scored,
        "mean_real_score": round(mean_real, 4),
        "min_real_score": round(min_real, 4),
        "threshold": REAL_THRESHOLD,
        "threshold_state": "UNCALIBRATED",
    }
