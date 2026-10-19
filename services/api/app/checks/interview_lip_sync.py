"""Interview lip-sync check.

Evaluates audio-visual synchronization using SyncNet (syncnet-python, ffmpeg).
If weights, ffmpeg, or audio track are missing, reports reason and returns 'uncertain'.
Thresholds are explicitly marked UNCALIBRATED.
"""
import logging
from pathlib import Path
from typing import Optional

from ..models import CheckResult
from . import lip_sync

logger = logging.getLogger(__name__)


def evaluate_interview_lip_sync(video_path: Optional[Path], audio_path: Optional[Path] = None) -> CheckResult:
    """Evaluate candidate mouth movements against speech audio track."""
    if not video_path or not Path(video_path).exists():
        return CheckResult.uncertain(
            "interview_lip_sync",
            "No video clip provided for lip sync evaluation",
            score=0.5,
            confidence=0.0,
            threshold_status="UNCALIBRATED"
        )

    # Use evaluate_lip_sync from kyc checks
    try:
        res = lip_sync.evaluate_lip_sync(video_path, audio_path)
        # Wrap as interview_lip_sync name
        details = dict(res.details)
        details["threshold_status"] = "UNCALIBRATED"
        details["model"] = "SyncNet"
        return CheckResult(
            name="interview_lip_sync",
            status=res.status,
            score=res.score,
            confidence=res.confidence,
            reason=res.reason,
            details=details
        )
    except Exception as e:
        logger.debug(f"Lip-sync evaluation exception: {e}")
        return CheckResult.uncertain(
            "interview_lip_sync",
            f"Lip sync evaluation unavailable: {e}",
            score=0.5,
            confidence=0.0,
            threshold_status="UNCALIBRATED"
        )
