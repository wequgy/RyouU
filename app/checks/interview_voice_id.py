"""Interview speaker identity verification via Detectif.ai Eidos API.

- Initial round: Enrolls candidate voiceprint (/v1/speakers/enroll).
- Subsequent rounds: Verifies voice against enrolled voiceprint (/v1/speakers/verify).
- No heuristic fallback: Returns 'uncertain' if speech too short or service unavailable.
"""
import logging
from pathlib import Path
from typing import Optional, Tuple

from ..models import CheckResult
from . import voice_ai
from .interview_voice_auth import _compute_audio_energy

logger = logging.getLogger(__name__)


def evaluate_interview_voice_id(
    audio_path: Optional[Path],
    interview_id: str,
    round_num: int,
    speaker_id: Optional[str],
    settings
) -> Tuple[CheckResult, Optional[str]]:
    """Verify speaker biometric identity against baseline.

    Returns:
        (CheckResult, new_speaker_id_if_enrolled)
    """
    if not audio_path or not Path(audio_path).exists():
        return CheckResult.uncertain(
            "interview_voice_id",
            "No audio track provided in clip",
            score=0.5,
            confidence=0.0
        ), speaker_id

    # Check energy / speech presence
    energy = _compute_audio_energy(Path(audio_path))
    if energy < 0.005:
        return CheckResult.uncertain(
            "interview_voice_id",
            "Audio track is silent or contains insufficient speech activity",
            score=0.5,
            confidence=0.0,
            energy_rms=energy
        ), speaker_id

    # Check Detectif API configuration
    if not settings.detectif_api_key or "your_" in settings.detectif_api_key:
        return CheckResult.uncertain(
            "interview_voice_id",
            "Detectif.ai API key not configured on server",
            score=0.5,
            confidence=0.0,
            service="detectif.ai"
        ), speaker_id

    # Round 1: Voice Enrollment
    if round_num <= 1 and not speaker_id:
        target_spk = f"spk_{interview_id}"
        try:
            res = voice_ai._call_detectif(
                "POST",
                "/v1/speakers/enroll",
                session_id=interview_id,
                settings=settings,
                path=audio_path,
                data_payload={"speaker_id": target_spk}
            )
            return CheckResult.passed(
                "interview_voice_id",
                "Initial speaker voiceprint enrolled successfully",
                score=1.0,
                confidence=0.85,
                speaker_id=target_spk,
                provider="detectif.ai"
            ), target_spk
        except Exception as e:
            logger.warning(f"Voice enrollment failed: {e}")
            return CheckResult.uncertain(
                "interview_voice_id",
                f"Initial voice enrollment unavailable: {e}",
                score=0.5,
                confidence=0.0,
                error=str(e)
            ), None

    # Subsequent rounds: Voice Verification
    if not speaker_id:
        return CheckResult.uncertain(
            "interview_voice_id",
            "Speaker voiceprint was not enrolled in earlier round",
            score=0.5,
            confidence=0.0
        ), None

    try:
        res = voice_ai._call_detectif(
            "POST",
            "/v1/speakers/verify",
            session_id=interview_id,
            settings=settings,
            path=audio_path,
            data_payload={"speaker_id": speaker_id}
        )
    except Exception as e:
        logger.warning(f"Voice verification failed: {e}")
        return CheckResult.uncertain(
            "interview_voice_id",
            f"Speaker verification unavailable: {e}",
            score=0.5,
            confidence=0.0,
            error=str(e)
        ), speaker_id

    match_score = float(res.get("match_score", res.get("similarity", 0.0)))
    is_match = bool(res.get("match", match_score >= 0.70))

    if is_match or match_score >= 0.70:
        return CheckResult.passed(
            "interview_voice_id",
            "Voice matches enrolled candidate voiceprint",
            score=round(match_score, 3),
            confidence=0.88,
            speaker_id=speaker_id,
            provider="detectif.ai"
        ), speaker_id
    elif match_score < 0.40:
        return CheckResult.failed(
            "interview_voice_id",
            "Voice differs significantly from enrolled candidate voiceprint",
            score=round(match_score, 3),
            confidence=0.85,
            speaker_id=speaker_id,
            provider="detectif.ai"
        ), speaker_id
    else:
        return CheckResult.uncertain(
            "interview_voice_id",
            "Speaker verification borderline / inconclusive",
            score=round(match_score, 3),
            confidence=0.50,
            speaker_id=speaker_id,
            provider="detectif.ai"
        ), speaker_id
