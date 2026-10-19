"""Lip-sync check: Audio-visual synchronization using SyncNet (syncnet-python, ffmpeg).

Evaluates whether speech audio in the challenge video matches mouth motion:
- Evaluates temporal offset between mouth movement and audio speech track.
- Calculates SyncNet confidence and LSE (Lip Sync Error) distance.
- Thresholds are marked UNCALIBRATED until validated on benchmark audio-video datasets.
- Signal only: Can return `pass` or flag `uncertain` / review needed, NEVER autonomous uncalibrated `fail`.
- Zero-fallback: If weights, ffmpeg, or audio are missing, logs reason and returns `uncertain`.
"""
import logging
import os
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from ..models import CheckContext, CheckResult
from .base import register

logger = logging.getLogger(__name__)

SYNCNET_WEIGHTS_PATH = Path("models/syncnet_v2.model")
S3FD_WEIGHTS_PATH = Path("models/sfd_face.pth")
_PIPELINE = None

# Uncalibrated decision threshold
SYNCNET_CONF_THRESHOLD = float(os.environ.get("SYNCNET_CONF_THRESHOLD", "3.0"))  # UNCALIBRATED


def _load_syncnet_pipeline():
    """Lazy load SyncNetPipeline from syncnet_python."""
    global _PIPELINE
    if _PIPELINE is None:
        import torch
        # Ensure torch.load defaults to CPU on non-CUDA machines
        orig_load = torch.load
        def safe_load(*args, **kwargs):
            if not torch.cuda.is_available() and "map_location" not in kwargs:
                kwargs["map_location"] = torch.device("cpu")
            return orig_load(*args, **kwargs)
        torch.load = safe_load

        from syncnet_python import SyncNetPipeline
        from syncnet_python.syncnet_pipeline import PipelineConfig

        # Check ffmpeg availability
        if not shutil.which("ffmpeg"):
            raise RuntimeError("ffmpeg executable not found in system PATH (required for SyncNet)")

        if not SYNCNET_WEIGHTS_PATH.exists() or not S3FD_WEIGHTS_PATH.exists():
            raise FileNotFoundError(
                f"SyncNet weights not found at {SYNCNET_WEIGHTS_PATH} and {S3FD_WEIGHTS_PATH}"
            )

        cfg = PipelineConfig(
            s3fd_weights=str(S3FD_WEIGHTS_PATH),
            syncnet_weights=str(SYNCNET_WEIGHTS_PATH),
        )
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _PIPELINE = SyncNetPipeline(cfg, device=device)
    return _PIPELINE


def evaluate_lip_sync(video_path: Optional[Path], audio_path: Optional[Path] = None) -> CheckResult:
    if not video_path or not Path(video_path).exists():
        return CheckResult.skipped("lip_sync", "No challenge video provided")

    try:
        from syncnet_python import safe_syncnet_inference
        pipeline = _load_syncnet_pipeline()
        offsets, confs, dists, min_dist, conf, status_str, is_valid = safe_syncnet_inference(
            pipeline=pipeline,
            video_path=str(video_path),
            audio_path=str(audio_path) if audio_path else None
        )

        details = {
            "model": "SyncNet (syncnet-python)",
            "status_str": status_str,
            "is_valid": is_valid,
            "confidence": round(float(conf), 3),
            "min_distance": round(float(min_dist), 3),
            "offsets": [int(o) for o in offsets[:5]] if offsets else [],
            "confidences": [round(float(c), 3) for c in confs[:5]] if confs else [],
            "threshold": SYNCNET_CONF_THRESHOLD,
            "threshold_state": "UNCALIBRATED",
        }

        # SyncNet confidence: Higher means better sync
        if not is_valid or conf < SYNCNET_CONF_THRESHOLD:
            # Rule: Never hard fail with uncalibrated thresholds; return uncertain / review flag
            return CheckResult(
                name="lip_sync",
                status="uncertain",
                score=0.4,
                confidence=0.3,
                reason=f"Lip-sync uncertainty: SyncNet confidence {conf:.2f} < {SYNCNET_CONF_THRESHOLD:.1f} (UNCALIBRATED)",
                details=details
            )

        trust = min(1.0, 0.5 + (conf / 10.0))
        return CheckResult(
            name="lip_sync",
            status="pass",
            score=round(trust, 3),
            confidence=0.5,
            reason=f"Lip movements synchronize with audio track (SyncNet confidence: {conf:.2f}, UNCALIBRATED)",
            details=details
        )

    except FileNotFoundError as e:
        logger.warning(f"SyncNet weights not found: {e}")
        return CheckResult.uncertain(
            "lip_sync",
            f"SyncNet weights not installed: {e} (UNCALIBRATED)",
            threshold_state="UNCALIBRATED"
        )
    except RuntimeError as e:
        logger.warning(f"SyncNet environment requirement missing: {e}")
        return CheckResult.uncertain(
            "lip_sync",
            f"SyncNet prerequisite missing: {e}",
            threshold_state="UNCALIBRATED"
        )
    except Exception as e:
        logger.error(f"SyncNet inference failed: {e}", exc_info=True)
        return CheckResult.uncertain(
            "lip_sync",
            f"SyncNet processing error: {e}",
            threshold_state="UNCALIBRATED"
        )


@register("lip_sync")
def lip_sync(ctx: CheckContext) -> CheckResult:
    video_path = ctx.files.get("challenge_video")
    audio_path = ctx.files.get("challenge_audio") or ctx.files.get("phrase_audio")
    return evaluate_lip_sync(video_path, audio_path=audio_path)
