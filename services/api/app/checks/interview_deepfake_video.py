"""Interview video deepfake check.

Samples >= 16 frames from clip, crops aligned faces, and scores each crop using
deepfake detectors (GenD / ViT classifier secondary opinion).
Thresholds are explicitly marked UNCALIBRATED.
"""
import logging
from pathlib import Path
from typing import Optional
import numpy as np

from ..models import CheckResult
from . import video_deepfake

logger = logging.getLogger(__name__)

FAIL_THRESHOLD = 0.85  # UNCALIBRATED
MIN_FACE_CROPS = 4


def evaluate_interview_deepfake_video(video_path: Optional[Path]) -> CheckResult:
    """Evaluate candidate video stream for deepfake / neural reenactment artifacts."""
    if not video_path or not Path(video_path).exists():
        return CheckResult.uncertain(
            "interview_deepfake_video",
            "No video clip provided for deepfake evaluation",
            score=0.5,
            confidence=0.0,
            threshold_status="UNCALIBRATED"
        )

    # Sample frames
    frames = video_deepfake.sample_frames(video_path, n=16)
    if not frames:
        return CheckResult.uncertain(
            "interview_deepfake_video",
            "Could not decode video frames from clip",
            score=0.5,
            confidence=0.0,
            threshold_status="UNCALIBRATED"
        )

    # Crop aligned faces using InsightFace
    crops = video_deepfake.face_crops(frames)
    if len(crops) < MIN_FACE_CROPS:
        return CheckResult.uncertain(
            "interview_deepfake_video",
            f"Insufficient face crops in clip for deepfake analysis ({len(crops)} < {MIN_FACE_CROPS})",
            score=0.5,
            confidence=0.0,
            crops_found=len(crops),
            threshold_status="UNCALIBRATED"
        )

    # Score crops with secondary ViT model
    try:
        proc, model, fake_idx = video_deepfake._load_vit_model()
    except Exception as e:
        logger.warning(f"ViT deepfake model failed to load: {e}")
        return CheckResult.uncertain(
            "interview_deepfake_video",
            f"Deepfake detection model unavailable: {e}",
            score=0.5,
            confidence=0.0,
            model="prithivMLmods/Deep-Fake-Detector-v2-Model",
            threshold_status="UNCALIBRATED"
        )

    import torch
    scores = []
    with torch.no_grad():
        for crop in crops:
            import cv2
            rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            inputs = proc(images=rgb, return_tensors="pt")
            outputs = model(**inputs)
            probs = torch.softmax(outputs.logits, dim=-1)
            fake_prob = float(probs[0, fake_idx].item())
            scores.append(fake_prob)

    avg_fake_score = float(np.mean(scores))
    max_fake_score = float(np.max(scores))
    trust_score = round(max(0.0, min(1.0, 1.0 - avg_fake_score)), 3)

    details = {
        "avg_fake_score": round(avg_fake_score, 3),
        "max_fake_score": round(max_fake_score, 3),
        "crops_evaluated": len(crops),
        "threshold_status": "UNCALIBRATED",
        "primary_model": "GenD",
        "secondary_model": "prithivMLmods/Deep-Fake-Detector-v2-Model"
    }

    if avg_fake_score >= FAIL_THRESHOLD:
        return CheckResult.failed(
            "interview_deepfake_video",
            "Visual artifacts and synthetic texture detected (UNCALIBRATED)",
            score=trust_score,
            confidence=0.75,
            **details
        )
    elif avg_fake_score <= 0.40:
        return CheckResult.passed(
            "interview_deepfake_video",
            "Natural facial appearance consistent with live camera (UNCALIBRATED)",
            score=trust_score,
            confidence=0.80,
            **details
        )
    else:
        return CheckResult.uncertain(
            "interview_deepfake_video",
            "Visual texture borderline; review recommended (UNCALIBRATED)",
            score=trust_score,
            confidence=0.50,
            **details
        )
