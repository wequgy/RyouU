"""Interview second person / proxy detection check.

Monitors video feed for multiple people or coaches in candidate view (InsightFace)
and checks for background typing sounds / off-camera assistance cues.
"""
import logging
from pathlib import Path
from typing import Optional
import numpy as np

from ..models import CheckResult
from . import face_match, video_deepfake
from .interview_voice_auth import _compute_audio_energy

logger = logging.getLogger(__name__)

MIN_DET_SCORE = 0.60
MIN_FACE_DIM = 40  # pixels
MULTI_FACE_FRAME_RATIO = 0.20


def _detect_typing_audio_cues(audio_path: Optional[Path]) -> bool:
    """Detect repetitive transient peaks characteristic of mechanical keyboard typing."""
    if not audio_path or not Path(audio_path).exists():
        return False
    try:
        import soundfile as sf
        data, sr = sf.read(str(audio_path))
        if len(data.shape) > 1:
            data = data.mean(axis=1)
        if len(data) < sr * 0.5:
            return False
        # High-pass filter or simple diff to isolate sharp transients
        diffs = np.abs(np.diff(data))
        std = np.std(diffs)
        if std == 0:
            return False
        peaks = np.where(diffs > 5 * std)[0]
        # Repetitive typing produces dozens of sharp transients per second
        peak_rate = len(peaks) / (len(data) / sr)
        return peak_rate > 8.0
    except Exception:
        return False


def evaluate_interview_second_person(video_path: Optional[Path], audio_path: Optional[Path] = None) -> CheckResult:
    """Detect multiple individuals in view or proxy assistance."""
    if not video_path or not Path(video_path).exists():
        return CheckResult.uncertain(
            "interview_second_person",
            "No video clip provided for second person check",
            score=0.5,
            confidence=0.0
        )

    try:
        app = face_match._load_app()
    except Exception as e:
        return CheckResult.uncertain(
            "interview_second_person",
            f"InsightFace model unavailable: {e}",
            score=0.5,
            confidence=0.0,
            model="buffalo_l"
        )

    frames = video_deepfake.sample_frames(video_path, n=10)
    if not frames:
        return CheckResult.uncertain(
            "interview_second_person",
            "Could not decode video frames from clip",
            score=0.5,
            confidence=0.0
        )

    total_frames = len(frames)
    frames_with_multi = 0
    face_counts = []

    for img in frames:
        if img is None:
            continue
        try:
            faces = app.get(img)
        except Exception:
            continue

        valid = []
        for f in faces:
            bbox = getattr(f, "bbox", None)
            if bbox is not None:
                w = float(bbox[2] - bbox[0])
                h = float(bbox[3] - bbox[1])
                if w < MIN_FACE_DIM or h < MIN_FACE_DIM:
                    continue
            det_score = float(getattr(f, "det_score", 0.0))
            if det_score >= MIN_DET_SCORE:
                valid.append(f)

        face_counts.append(len(valid))
        if len(valid) >= 2:
            frames_with_multi += 1

    multi_ratio = frames_with_multi / float(max(1, total_frames))
    avg_faces = float(np.mean(face_counts)) if face_counts else 0.0
    typing_detected = _detect_typing_audio_cues(audio_path)

    details = {
        "multi_face_ratio": round(multi_ratio, 2),
        "avg_faces_in_frame": round(avg_faces, 1),
        "keyboard_cues_detected": typing_detected,
        "frames_evaluated": total_frames
    }

    if multi_ratio >= MULTI_FACE_FRAME_RATIO:
        return CheckResult.failed(
            "interview_second_person",
            f"Multiple individuals detected in camera view ({int(multi_ratio * 100)}% of frames)",
            score=0.0,
            confidence=0.88,
            **details
        )
    elif avg_faces < 0.3:
        return CheckResult.uncertain(
            "interview_second_person",
            "Candidate face not visible in camera frame",
            score=0.5,
            confidence=0.0,
            **details
        )
    else:
        return CheckResult.passed(
            "interview_second_person",
            "Single individual observed in camera view",
            score=1.0,
            confidence=0.90,
            **details
        )
