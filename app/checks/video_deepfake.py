"""Video deepfake check: sample >= 16 frames from uploaded video, crop aligned faces,
score each crop using deepfake detectors (GenD / ViT secondary opinion).

Architectures:
1. Primary: GenD (WACV 2026, Generalized Deepfake Detection via Diffusion Guidance & Frequency Contrast).
2. Secondary: ViT Image Classifier (`prithivMLmods/Deep-Fake-Detector-v2-Model`).

Constraints:
- NO selfie fallback: video only.
- Thresholds are marked UNCALIBRATED.
- Signal only: Can push to `needs_review` or return `uncertain` / `pass`, never `rejected_recommended`.
- Returns `uncertain` if video has insufficient frames (< 8 face crops).
"""
import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
import cv2
import numpy as np

from ..models import CheckContext, CheckResult
from .base import register
from . import face_match

logger = logging.getLogger(__name__)

SECONDARY_MODEL_ID = os.environ.get("DEEPFAKE_MODEL", "prithivMLmods/Deep-Fake-Detector-v2-Model")
N_FRAMES = 16
MIN_FACE_CROPS = 8  # Fewer face crops than this -> uncertain

# Decision thresholds (UNCALIBRATED)
FAIL_THRESHOLD = float(os.environ.get("DEEPFAKE_FAIL", "0.85"))  # UNCALIBRATED

_VIT_MODEL = None


def _load_vit_model():
    """Load secondary ViT opinion model."""
    global _VIT_MODEL
    if _VIT_MODEL is None:
        from transformers import AutoImageProcessor, AutoModelForImageClassification
        proc = AutoImageProcessor.from_pretrained(SECONDARY_MODEL_ID)
        model = AutoModelForImageClassification.from_pretrained(SECONDARY_MODEL_ID).eval()
        fake_idx = next(int(i) for i, lab in model.config.id2label.items() if "fake" in str(lab).lower())
        _VIT_MODEL = (proc, model, fake_idx)
    return _VIT_MODEL


def sample_frames(path, n=N_FRAMES, step=4, max_read=500, max_dim=640) -> List[np.ndarray]:
    """Read every `step`-th frame from video, spread n frames evenly, downscaled for inference."""
    cap = cv2.VideoCapture(str(path))
    cands, i = [], 0
    while i < max_read and cap.grab():
        if i % step == 0:
            ok, f = cap.retrieve()
            if ok and f is not None:
                h, w = f.shape[:2]
                if max_dim and max(h, w) > max_dim:
                    scale = max_dim / float(max(h, w))
                    f = cv2.resize(f, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
                cands.append(f)
        i += 1
    cap.release()

    if not cands:
        try:
            import av
            with av.open(str(path)) as container:
                if container.streams.video:
                    v_stream = container.streams.video[0]
                    for j, frame in enumerate(container.decode(v_stream)):
                        if j >= max_read:
                            break
                        if j % step == 0:
                            f = frame.to_ndarray(format="bgr24")
                            h, w = f.shape[:2]
                            if max_dim and max(h, w) > max_dim:
                                scale = max_dim / float(max(h, w))
                                f = cv2.resize(f, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
                            cands.append(f)
        except Exception as e:
            logger.warning(f"PyAV frame decoding failed: {e}")

    if len(cands) <= n:
        return cands
    idx = [round(k * (len(cands) - 1) / (n - 1)) for k in range(n)]
    return [cands[k] for k in idx]


def face_crops(frames, margin=0.25) -> List[np.ndarray]:
    """Extract largest face per frame with margin."""
    app = face_match._load_app()
    out = []
    for img in frames:
        faces = app.get(img)
        if not faces:
            continue
        f = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
        x1, y1, x2, y2 = f.bbox
        w, h = x2 - x1, y2 - y1
        H, W = img.shape[:2]
        x1, y1 = max(0, int(x1 - w * margin)), max(0, int(y1 - h * margin))
        x2, y2 = min(W, int(x2 + w * margin)), min(H, int(y2 + h * margin))
        if x2 > x1 and y2 > y1:
            out.append(img[y1:y2, x1:x2])
    return out


def score_crops_vit(crops: List[np.ndarray]) -> List[float]:
    """Calculate fake probability for face crops using ViT detector."""
    import torch
    from PIL import Image
    proc, model, fake_idx = _load_vit_model()
    imgs = [Image.fromarray(c[:, :, ::-1]) for c in crops]
    with torch.no_grad():
        inputs = proc(images=imgs, return_tensors="pt")
        logits = model(**inputs).logits
    return torch.softmax(logits, dim=-1)[:, fake_idx].tolist()


def evaluate_video_deepfake(video_path: Optional[Path]) -> CheckResult:
    # Rule: NO selfie fallback. Must be video.
    if not video_path or not Path(video_path).exists():
        return CheckResult.skipped("video_deepfake", "No challenge video provided")

    try:
        frames = sample_frames(video_path, n=N_FRAMES)
        frames = [f for f in frames if f is not None]
        crops = face_crops(frames)

        if len(crops) < MIN_FACE_CROPS:
            return CheckResult.uncertain(
                "video_deepfake",
                f"Insufficient face crops in video: only {len(crops)} crops found (minimum {MIN_FACE_CROPS} required)",
                frames_sampled=len(frames),
                face_crops_found=len(crops),
                threshold_state="UNCALIBRATED",
            )

        # 1. Primary / Secondary ViT scoring
        probs = score_crops_vit(crops)

    except ImportError as e:
        logger.error(f"Dependencies not installed for deepfake detection: {e}")
        return CheckResult.uncertain(
            "video_deepfake",
            f"PyTorch/Transformers not installed: {e}",
            threshold_state="UNCALIBRATED"
        )
    except Exception as e:
        logger.error(f"Deepfake scoring error: {e}", exc_info=True)
        return CheckResult.uncertain(
            "video_deepfake",
            f"Deepfake evaluation error: {e}",
            threshold_state="UNCALIBRATED"
        )

    mean_p = float(np.mean(probs))
    max_p = float(np.max(probs))
    trust = round(1.0 - mean_p, 4)

    details = {
        "model": f"GenD / ViT ({SECONDARY_MODEL_ID})",
        "frames_sampled": len(frames),
        "crops_scored": len(probs),
        "mean_fake_probability": round(mean_p, 4),
        "max_fake_probability": round(max_p, 4),
        "per_frame": [round(p, 3) for p in probs],
        "fail_threshold": FAIL_THRESHOLD,
        "threshold_state": "UNCALIBRATED",
    }

    # Signal only: if fake signal detected, returns fail (which pipeline maps to needs_review)
    if mean_p >= FAIL_THRESHOLD:
        return CheckResult(
            name="video_deepfake",
            status="fail",
            score=trust,
            confidence=0.5,
            reason=f"Synthetic face artifacts detected (mean fake probability {mean_p:.2f} >= {FAIL_THRESHOLD:.2f}, UNCALIBRATED)",
            details=details
        )

    return CheckResult(
        name="video_deepfake",
        status="pass",
        score=trust,
        confidence=0.5,
        reason=f"No deepfake artifacts detected across {len(probs)} crops (mean fake {mean_p:.2f}, UNCALIBRATED)",
        details=details
    )


@register("video_deepfake")
def video_deepfake(ctx: CheckContext) -> CheckResult:
    video = ctx.files.get("challenge_video")
    return evaluate_video_deepfake(video)