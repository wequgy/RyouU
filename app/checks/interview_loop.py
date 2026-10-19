"""Interview loop and video freeze detection via perceptual frame hashing (dHash).

Detects:
1. Video replay loops (cyclically repeating perceptual hash sequences).
2. Frozen video streams (identical frames with zero temporal motion variance).
3. Natural live motion (healthy continuous variation).
"""
import logging
from pathlib import Path
from typing import Optional, List
import cv2
import numpy as np

from ..models import CheckResult
from . import video_deepfake

logger = logging.getLogger(__name__)


def _compute_dhash(frame: np.ndarray, hash_size: int = 8) -> int:
    """Compute 64-bit difference hash of a frame."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
    resized = cv2.resize(gray, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA)
    diff = resized[:, 1:] > resized[:, :-1]
    # Pack boolean array into an integer
    h = 0
    for bit in diff.flatten():
        h = (h << 1) | int(bit)
    return h


def _hamming_distance(h1: int, h2: int) -> int:
    return bin(h1 ^ h2).count("1")


def evaluate_interview_loop(video_path: Optional[Path]) -> CheckResult:
    """Evaluate video for looping playback or frozen camera."""
    if not video_path or not Path(video_path).exists():
        return CheckResult.uncertain(
            "interview_loop",
            "No video clip provided for loop detection",
            score=0.5,
            confidence=0.0
        )

    # Sample frames across clip
    frames = video_deepfake.sample_frames(video_path, n=16, step=1)
    if len(frames) < 6:
        return CheckResult.uncertain(
            "interview_loop",
            f"Insufficient video frames for loop analysis ({len(frames)} < 6)",
            score=0.5,
            confidence=0.0
        )

    hashes = [_compute_dhash(f) for f in frames if f is not None]
    if len(hashes) < 6:
        return CheckResult.uncertain(
            "interview_loop",
            "Could not compute perceptual frame hashes",
            score=0.5,
            confidence=0.0
        )

    # 1. Consecutive Frame Distances (Freeze Check)
    consec_dists = [_hamming_distance(hashes[i], hashes[i+1]) for i in range(len(hashes) - 1)]
    frozen_count = sum(1 for d in consec_dists if d <= 1)
    frozen_ratio = frozen_count / float(len(consec_dists))

    # 2. Pairwise Matrix & Loop/Replay Detection
    # Look for recurring frames separated by interval > 3
    loop_matches = 0
    total_checks = 0
    for i in range(len(hashes)):
        for j in range(i + 4, len(hashes)):
            total_checks += 1
            if _hamming_distance(hashes[i], hashes[j]) <= 2:
                loop_matches += 1

    details = {
        "frames_evaluated": len(hashes),
        "mean_consecutive_hamming": round(float(np.mean(consec_dists)), 2),
        "frozen_ratio": round(frozen_ratio, 2),
        "loop_recurring_pairs": loop_matches
    }

    if frozen_ratio >= 0.70:
        return CheckResult.failed(
            "interview_loop",
            "Frozen or static camera stream detected across clip",
            score=0.0,
            confidence=0.92,
            frozen=True,
            **details
        )

    if loop_matches >= 3:
        return CheckResult.failed(
            "interview_loop",
            "Video sequence replay / cyclic loop pattern detected",
            score=0.0,
            confidence=0.88,
            loop_detected=True,
            **details
        )

    return CheckResult.passed(
        "interview_loop",
        "Natural continuous motion variation observed without loop repetition",
        score=1.0,
        confidence=0.90,
        **details
    )
