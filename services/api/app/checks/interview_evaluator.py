"""Interview clip evaluator.

Coordinates execution of all 7 integrity checks on uploaded interview clips,
determines overall clip recommendation, and generates contextual interviewer guidance.
"""
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from ..models import CheckResult, PASS, FAIL, UNCERTAIN, SKIPPED
from .interview_voice_auth import evaluate_interview_voice_auth
from .interview_voice_id import evaluate_interview_voice_id
from .interview_face_id import evaluate_interview_face_id
from .interview_deepfake_video import evaluate_interview_deepfake_video
from .interview_second_person import evaluate_interview_second_person
from .interview_loop import evaluate_interview_loop
from .interview_lip_sync import evaluate_interview_lip_sync

logger = logging.getLogger(__name__)


def evaluate_interview_clip(
    video_path: Optional[Path],
    audio_path: Optional[Path],
    interview_id: str,
    round_num: int,
    face_baseline: Optional[List[float]],
    speaker_id: Optional[str],
    settings
) -> Tuple[List[CheckResult], str, str, Optional[List[float]], Optional[str]]:
    """Run all 7 checks on a 25s meeting clip.

    Returns:
        (check_results, recommendation, suggested_action, new_face_baseline, new_speaker_id)
    """
    results: List[CheckResult] = []
    new_face_baseline = face_baseline
    new_speaker_id = speaker_id

    # 1. Loop and Freeze Detection
    try:
        r_loop = evaluate_interview_loop(video_path)
    except Exception as e:
        logger.error(f"Loop check exception: {e}")
        r_loop = CheckResult.uncertain("interview_loop", f"Loop check error: {e}")
    results.append(r_loop)

    # 2. Second Person / Multiple Individuals
    try:
        r_second = evaluate_interview_second_person(video_path, audio_path)
    except Exception as e:
        logger.error(f"Second person check exception: {e}")
        r_second = CheckResult.uncertain("interview_second_person", f"Second person check error: {e}")
    results.append(r_second)

    # 3. Facial Identity Consistency
    try:
        r_face, updated_baseline = evaluate_interview_face_id(video_path, round_num, face_baseline)
        if updated_baseline:
            new_face_baseline = updated_baseline
    except Exception as e:
        logger.error(f"Face id check exception: {e}")
        r_face = CheckResult.uncertain("interview_face_id", f"Face identity check error: {e}")
    results.append(r_face)

    # 4. Video Deepfake Detection (GenD + ViT)
    try:
        r_df_vid = evaluate_interview_deepfake_video(video_path)
    except Exception as e:
        logger.error(f"Video deepfake check exception: {e}")
        r_df_vid = CheckResult.uncertain("interview_deepfake_video", f"Video deepfake check error: {e}")
    results.append(r_df_vid)

    # 5. Voice Authenticity (Detectif.ai + VAD)
    try:
        r_voice_auth = evaluate_interview_voice_auth(audio_path, interview_id, settings)
    except Exception as e:
        logger.error(f"Voice auth check exception: {e}")
        r_voice_auth = CheckResult.uncertain("interview_voice_auth", f"Voice authenticity check error: {e}")
    results.append(r_voice_auth)

    # 6. Speaker Identity Verification (Detectif.ai)
    try:
        r_voice_id, updated_speaker = evaluate_interview_voice_id(audio_path, interview_id, round_num, speaker_id, settings)
        if updated_speaker:
            new_speaker_id = updated_speaker
    except Exception as e:
        logger.error(f"Voice id check exception: {e}")
        r_voice_id = CheckResult.uncertain("interview_voice_id", f"Speaker verification check error: {e}")
    results.append(r_voice_id)

    # 7. Lip Synchronization (SyncNet)
    try:
        r_lip = evaluate_interview_lip_sync(video_path, audio_path)
    except Exception as e:
        logger.error(f"Lip sync check exception: {e}")
        r_lip = CheckResult.uncertain("interview_lip_sync", f"Lip sync check error: {e}")
    results.append(r_lip)

    # Determine overall recommendation and interviewer action
    recommendation, suggested_action = _derive_recommendation_and_action(results)

    return results, recommendation, suggested_action, new_face_baseline, new_speaker_id


def _derive_recommendation_and_action(results: List[CheckResult]) -> Tuple[str, str]:
    """Derive human-centric recommendation and action. Never labels someone 'fake'."""
    res_by_name = {r.name: r for r in results}

    # High-confidence failures
    failed_checks = [r for r in results if r.status == FAIL and r.confidence >= 0.70]
    uncertain_checks = [r for r in results if r.status == UNCERTAIN]

    # Specific actionable guidance
    if any(r.name == "interview_second_person" and r.status == FAIL for r in failed_checks):
        return (
            "flagged",
            "Multiple individuals detected in camera view. Ask candidate to confirm their physical interview environment."
        )

    if any(r.name == "interview_face_id" and r.status == FAIL for r in failed_checks):
        return (
            "flagged",
            "Face in view does not match enrolled candidate identity. Pause and verify identity against application records."
        )

    if any(r.name == "interview_voice_auth" and r.status == FAIL for r in failed_checks):
        return (
            "flagged",
            "Acoustic markers suggest possible synthetic voice. Ask an unscripted, impromptu technical question."
        )

    if any(r.name == "interview_loop" and r.status == FAIL for r in failed_checks):
        return (
            "flagged",
            "Video stream appears frozen or replaying. Ask candidate to make a natural hand wave or gesture."
        )

    if any(r.name == "interview_voice_id" and r.status == FAIL for r in failed_checks):
        return (
            "caution",
            "Speaker voiceprint differs from initial enrollment. Verify candidate audio device settings."
        )

    if any(r.name == "interview_deepfake_video" and r.status == FAIL for r in failed_checks):
        return (
            "caution",
            "Visual artifacts detected on candidate video (UNCALIBRATED). Review video quality and observe candidate motion."
        )

    if len(uncertain_checks) >= 4:
        return (
            "caution",
            "Multiple signals uncertain due to audio silence or low video resolution. Ask candidate to adjust lighting or microphone."
        )

    # If any remaining failures
    if failed_checks:
        first = failed_checks[0]
        return (
            "caution",
            f"Signal anomaly observed in {first.name.replace('interview_', '')}. Exercise interviewer discretion."
        )

    # If some uncertain checks exist but primary checks pass
    if uncertain_checks:
        return (
            "clear",
            "Primary identity and motion signals healthy. (Some auxiliary checks returned uncertain due to silence or missing models)."
        )

    return (
        "clear",
        "All integrity signals healthy and consistent with live candidate interview. Continue interview normally."
    )
