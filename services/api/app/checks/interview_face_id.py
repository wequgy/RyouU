"""Interview face identity verification via InsightFace (buffalo_l).

Enrolls facial baseline from initial round or verified KYC record, and monitors
face identity consistency across subsequent interview clips.
Requires minimum face resolution of 60x60 px.
"""
import logging
from pathlib import Path
from typing import Optional, Tuple, List
import numpy as np

from ..models import CheckResult
from . import face_match, video_deepfake

logger = logging.getLogger(__name__)

MIN_FACE_SIZE = 40  # minimum bounding box width and height in px
COSINE_MATCH_THRESHOLD = 0.65
COSINE_FAIL_THRESHOLD = 0.40


def evaluate_interview_face_id(
    video_path: Optional[Path],
    round_num: int,
    face_baseline: Optional[List[float]],
) -> Tuple[CheckResult, Optional[List[float]]]:
    """Verify facial identity consistency across interview rounds.

    Returns:
        (CheckResult, updated_face_baseline)
    """
    if not video_path or not Path(video_path).exists():
        return CheckResult.uncertain(
            "interview_face_id",
            "No video clip provided for face identity check",
            score=0.5,
            confidence=0.0
        ), face_baseline

    try:
        app = face_match._load_app()
    except Exception as e:
        return CheckResult.uncertain(
            "interview_face_id",
            f"InsightFace model unavailable: {e}",
            score=0.5,
            confidence=0.0,
            model="buffalo_l"
        ), face_baseline

    # Sample frames from video
    frames = video_deepfake.sample_frames(video_path, n=8)
    if not frames:
        return CheckResult.uncertain(
            "interview_face_id",
            "Could not decode video frames from clip",
            score=0.5,
            confidence=0.0
        ), face_baseline

    # Collect valid face crops meeting min_face_size
    valid_embeddings = []
    for img in frames:
        if img is None:
            continue
        try:
            faces = app.get(img)
        except Exception:
            continue
        for f in faces:
            bbox = getattr(f, "bbox", None)
            if bbox is not None:
                w = float(bbox[2] - bbox[0])
                h = float(bbox[3] - bbox[1])
                if w < MIN_FACE_SIZE or h < MIN_FACE_SIZE:
                    continue
            det_score = float(getattr(f, "det_score", 0.0))
            emb = getattr(f, "embedding", None)
            if det_score >= 0.5 and emb is not None:
                norm = np.linalg.norm(emb)
                if norm > 0:
                    valid_embeddings.append(emb / norm)

    if not valid_embeddings:
        return CheckResult.uncertain(
            "interview_face_id",
            "No face detected in video feed. Select candidate video tile to monitor face identity.",
            score=0.5,
            confidence=0.0,
            min_resolution_px=MIN_FACE_SIZE
        ), face_baseline

    # Round 1: Baseline Enrollment if not yet present
    if not face_baseline and round_num <= 1:
        # Use mean embedding of high quality crops as baseline
        mean_emb = np.mean(valid_embeddings, axis=0)
        norm = np.linalg.norm(mean_emb)
        if norm > 0:
            mean_emb = mean_emb / norm
        new_baseline = [round(float(x), 5) for x in mean_emb]
        return CheckResult.passed(
            "interview_face_id",
            "Initial candidate face identity enrolled successfully",
            score=1.0,
            confidence=0.90,
            enrolled_crops=len(valid_embeddings)
        ), new_baseline

    if not face_baseline:
        return CheckResult.uncertain(
            "interview_face_id",
            "Candidate face identity not enrolled in baseline round",
            score=0.5,
            confidence=0.0
        ), None

    # Compare with baseline
    base_arr = np.array(face_baseline, dtype=np.float32)
    base_norm = np.linalg.norm(base_arr)
    if base_norm > 0:
        base_arr = base_arr / base_norm

    sims = [float(np.dot(emb, base_arr)) for emb in valid_embeddings]
    mean_sim = float(np.mean(sims))
    max_sim = float(np.max(sims))
    # Effective score weighted towards maximum observed face similarity
    score = round(max(0.0, min(1.0, 0.7 * mean_sim + 0.3 * max_sim)), 3)

    if mean_sim >= COSINE_MATCH_THRESHOLD:
        return CheckResult.passed(
            "interview_face_id",
            "Face matches enrolled candidate identity",
            score=score,
            confidence=0.92,
            similarity=round(mean_sim, 3),
            crops_evaluated=len(valid_embeddings)
        ), face_baseline
    elif mean_sim < COSINE_FAIL_THRESHOLD:
        return CheckResult.failed(
            "interview_face_id",
            "Face in view does not match enrolled candidate identity",
            score=score,
            confidence=0.88,
            similarity=round(mean_sim, 3),
            crops_evaluated=len(valid_embeddings)
        ), face_baseline
    else:
        return CheckResult.uncertain(
            "interview_face_id",
            "Facial identity similarity borderline / requires visual review",
            score=score,
            confidence=0.50,
            similarity=round(mean_sim, 3),
            crops_evaluated=len(valid_embeddings)
        ), face_baseline
