"""Video deepfake detection: planned for the end of the build (CLIP ViT-L/14 + light tuning).

Until then it returns 'uncertain' so it can never silently pass anyone. Plug the model in `score_frames`.
"""
from ..models import CheckContext, CheckResult
from .base import register


def score_frames(frames) -> float:  # pragma: no cover - placeholder
    raise NotImplementedError("video deepfake model not built yet")


@register("video_deepfake")
def video_deepfake(ctx: CheckContext) -> CheckResult:
    return CheckResult.uncertain("video_deepfake", "Not implemented yet (planned: CLIP-based face deepfake head)")
