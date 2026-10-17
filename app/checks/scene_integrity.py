"""Scene integrity check on challenge_video using InsightFace.

Monitors two key fraud vectors:
1. Second person / coach beside user: >= 2 faces (det_score >= 0.6, size >= 40 px) in >= 20% of frames -> fail.
2. Identity continuity (face-swap / person change): embedding of the largest face per frame vs
   the verified selfie; below threshold in >= 30% of frames -> fail.
Too few usable frames -> uncertain.
"""
import numpy as np

from ..models import CheckContext, CheckResult
from .base import register
from . import face_match, video_deepfake


def evaluate_scene_integrity(video_path, selfie_path, s) -> CheckResult:
    if not video_path:
        return CheckResult.skipped("scene_integrity", "No challenge video provided")
    if not selfie_path:
        return CheckResult.uncertain("scene_integrity", "Verified selfie required to verify continuity in video")

    try:
        app = face_match._load_app()
    except Exception as e:
        return CheckResult.uncertain("scene_integrity", f"InsightFace model unavailable: {e}")

    try:
        e_selfie, m_selfie = face_match.EMBEDDER(selfie_path)
    except Exception as e:
        return CheckResult.uncertain("scene_integrity", f"Failed to extract selfie embedding: {e}")

    if e_selfie is None:
        return CheckResult.uncertain("scene_integrity", "Could not extract face embedding from verified selfie")

    norm_selfie = np.linalg.norm(e_selfie)
    if norm_selfie > 0:
        e_selfie = e_selfie / norm_selfie

    frames = video_deepfake.sample_frames(video_path, n=16)
    if not frames:
        return CheckResult.uncertain("scene_integrity", "No frames could be extracted from video")

    total_frames = len(frames)
    frames_with_multi_face = 0
    continuity_failures = 0
    usable_face_frames = 0
    similarities = []

    for img in frames:
        if img is None:
            continue
        try:
            faces = app.get(img)
        except Exception:
            continue

        if not faces:
            continue

        # Check for multiple people: det_score >= 0.6, bbox width and height >= 40px
        valid_faces = [
            f for f in faces
            if float(getattr(f, "det_score", 0.0)) >= 0.6 and
            (f.bbox[2] - f.bbox[0]) >= 40 and (f.bbox[3] - f.bbox[1]) >= 40
        ]
        if len(valid_faces) >= 2:
            frames_with_multi_face += 1

        # Check identity continuity on largest face
        f_largest = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
        if (f_largest.bbox[2] - f_largest.bbox[0]) >= 40 and (f_largest.bbox[3] - f_largest.bbox[1]) >= 40:
            usable_face_frames += 1
            e_frame = f_largest.normed_embedding
            norm_frame = np.linalg.norm(e_frame)
            if norm_frame > 0:
                e_frame = e_frame / norm_frame
                sim = float(np.dot(e_selfie, e_frame))
                similarities.append(round(sim, 3))
                # Below threshold (face swap / person change)
                if sim < s.face_fail_sim:
                    continuity_failures += 1

    details = {
        "total_frames_sampled": total_frames,
        "usable_face_frames": usable_face_frames,
        "multi_face_frames": frames_with_multi_face,
        "continuity_failures": continuity_failures,
        "mean_similarity": round(float(np.mean(similarities)), 3) if similarities else 0.0,
    }

    # 1. Second person check: >= 20% of frames have multiple faces
    if total_frames > 0 and (frames_with_multi_face / total_frames) >= 0.20:
        return CheckResult(
            "scene_integrity", "fail", 0.0, 0.7,
            f"Multiple people detected in video ({frames_with_multi_face}/{total_frames} frames)",
            details
        )

    # Need at least 4 usable face frames to assess continuity
    if usable_face_frames < 4:
        return CheckResult(
            "scene_integrity", "uncertain", 0.4, 0.3,
            f"Too few usable face frames ({usable_face_frames}) to verify continuity",
            details
        )

    # 2. Identity continuity: below threshold in >= 30% of usable frames
    if (continuity_failures / usable_face_frames) >= 0.30:
        return CheckResult(
            "scene_integrity", "fail", 0.1, 0.7,
            f"Identity discontinuity / face-swap detected ({continuity_failures}/{usable_face_frames} frames below threshold)",
            details
        )

    mean_sim = np.mean(similarities) if similarities else 0.0
    trust = min(1.0, max(0.0, float(mean_sim)))
    return CheckResult("scene_integrity", "pass", trust, 0.6, "Scene integrity verified: continuous single person", details)


@register("scene_integrity")
def scene_integrity(ctx: CheckContext) -> CheckResult:
    video_path = ctx.files.get("challenge_video")
    selfie_path = ctx.files.get("selfie")
    return evaluate_scene_integrity(video_path, selfie_path, ctx.settings)
