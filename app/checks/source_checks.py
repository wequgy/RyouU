"""Camera-source and environment checks from CLIENT signals (hints, not proof).

A browser cannot truly block casting, remote desktop, a second device or a virtual camera. This makes
the obvious ones detectable. A generically named virtual camera will slip through, which is why random
timed challenges and the deepfake checks matter more than this check.
"""
import re

from ..models import CheckContext, CheckResult
from .base import register

VIRTUAL_CAM_PATTERNS = [r"\bobs\b", r"manycam", r"snap camera", r"xsplit", r"droidcam", r"iriun",
                        r"epoccam", r"\bndi\b", r"splitcam", r"vcam", r"virtual", r"e2esoft", r"\bcamo\b"]
_RX = re.compile("|".join(VIRTUAL_CAM_PATTERNS), re.I)


def find_virtual_cams(labels) -> list:
    return [l for l in labels if _RX.search(l or "")]


@register("source_checks")
def source_checks(ctx: CheckContext) -> CheckResult:
    sig = ctx.data.get("signals") or {}
    if not sig:
        return CheckResult.skipped("source_checks", "No client signals received")
    hard, soft = [], []
    cams = find_virtual_cams(sig.get("camera_labels", []))
    if cams:
        hard.append(f"virtual camera detected: {', '.join(cams)}")
    if sig.get("screen_share_attempted"):
        hard.append("screen sharing attempted")
    if sig.get("focus_loss_count", 0) >= ctx.settings.focus_loss_review_count:
        soft.append(f"left the page {sig['focus_loss_count']} times")
    if sig.get("extended_display"):
        soft.append("extended display in use")
    if sig.get("fullscreen_exited"):
        soft.append("exited fullscreen")
    details = {"hard": hard, "soft": soft}
    if hard:
        return CheckResult("source_checks", "fail", 0.0, 0.7, "; ".join(hard), details)
    if soft:
        return CheckResult("source_checks", "uncertain", 0.5, 0.4, "; ".join(soft), details)
    return CheckResult("source_checks", "pass", 1.0, 0.4, "No source or environment red flags", details)
