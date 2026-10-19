"""Interview voice authenticity check via Detectif.ai (/v1/deepfake/detect).

Attributes speech audio to candidate with VAD / energy silence gating.
Returns CheckResult(name='interview_voice_auth', status, score, confidence, reason, details).
"""
import logging
from pathlib import Path
from typing import Optional
import wave
import numpy as np

from ..models import CheckResult
from . import voice_ai

logger = logging.getLogger(__name__)


def _compute_audio_energy(audio_path: Path) -> float:
    """Compute normalized RMS energy from wav or audio file."""
    try:
        import soundfile as sf
        data, sr = sf.read(str(audio_path))
        if len(data) == 0:
            return 0.0
        if len(data.shape) > 1:
            data = data.mean(axis=1)
        rms = float(np.sqrt(np.mean(data ** 2)))
        return rms
    except Exception:
        # Fallback to wave module if soundfile not present
        try:
            with wave.open(str(audio_path), 'rb') as wf:
                n = wf.getnframes()
                if n == 0:
                    return 0.0
                frames = wf.readframes(n)
                samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
                return float(np.sqrt(np.mean(samples ** 2)))
        except Exception as e:
            logger.debug(f"Could not compute audio energy: {e}")
            return 0.05  # assume non-zero if readable as other container


def evaluate_interview_voice_auth(audio_path: Optional[Path], interview_id: str, settings) -> CheckResult:
    """Evaluate audio track for synthetic/AI-generated speech."""
    if not audio_path or not Path(audio_path).exists():
        return CheckResult.uncertain(
            "interview_voice_auth",
            "No audio track provided in clip",
            score=0.5,
            confidence=0.0
        )

    # 1. Silence / VAD gating
    energy = _compute_audio_energy(Path(audio_path))
    if energy < 0.005:
        return CheckResult.uncertain(
            "interview_voice_auth",
            "Audio track is silent or contains insufficient speech activity",
            score=0.5,
            confidence=0.0,
            energy_rms=energy
        )

    # 2. Check Detectif API configuration
    if not settings.detectif_api_key or "your_" in settings.detectif_api_key:
        return CheckResult.uncertain(
            "interview_voice_auth",
            "Detectif.ai API key not configured on server",
            score=0.5,
            confidence=0.0,
            service="detectif.ai"
        )

    # 3. Call Detectif /v1/deepfake/detect
    try:
        res = voice_ai._call_detectif(
            "POST",
            "/v1/deepfake/detect",
            session_id=interview_id,
            settings=settings,
            path=audio_path
        )
    except Exception as e:
        logger.warning(f"Detectif API error during interview voice auth: {e}")
        return CheckResult.uncertain(
            "interview_voice_auth",
            f"Detectif voice analysis unavailable: {e}",
            score=0.5,
            confidence=0.0,
            error=str(e)
        )

    fake_prob = float(res.get("fake_probability", res.get("deepfake_score", 0.0)))
    # Score is TRUST score (1.0 = genuine, 0.0 = fake)
    trust_score = round(max(0.0, min(1.0, 1.0 - fake_prob)), 3)

    if fake_prob >= 0.65:
        return CheckResult.failed(
            "interview_voice_auth",
            "Possible synthetic or AI-generated voice characteristics detected",
            score=trust_score,
            confidence=0.85,
            fake_probability=fake_prob,
            provider="detectif.ai"
        )
    elif fake_prob <= 0.35:
        return CheckResult.passed(
            "interview_voice_auth",
            "No synthetic voice markers detected; natural acoustic harmonics",
            score=trust_score,
            confidence=0.90,
            fake_probability=fake_prob,
            provider="detectif.ai"
        )
    else:
        return CheckResult.uncertain(
            "interview_voice_auth",
            "Voice authenticity analysis inconclusive (borderline score)",
            score=trust_score,
            confidence=0.50,
            fake_probability=fake_prob,
            provider="detectif.ai"
        )
