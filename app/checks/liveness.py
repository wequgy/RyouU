"""Liveness: did the user complete the server-issued random challenges, in time?"""
from ..models import CheckContext, CheckResult
from ..textutil import spoken_to_digits
from . import spoken_details as sd
from .base import register


def _judge(item: dict, res: dict, ctx: CheckContext):
    """Return (status, reason) for one challenge."""
    s = ctx.settings
    m = res.get("metrics", {}) or {}
    if res["answered_at"] - item["issued_at"] > s.challenge_ttl_s:
        return "fail", "answered too late"
    kind = item["type"]
    if kind == "head_turn":
        ok = m.get("yaw_range_deg", 0) >= s.head_turn_min_yaw_deg and \
            m.get("face_present_ratio", 0) >= s.min_face_present_ratio
        return ("pass", "head turn ok") if ok else ("fail", "head turn not detected")
    if kind == "hand_wave":
        ok = m.get("occlusion_ratio", 0) >= s.hand_wave_min_occlusion and \
            m.get("face_present_ratio_after", 0) >= s.min_face_present_ratio
        return ("pass", "hand wave ok") if ok else ("fail", "hand wave not detected or face lost")
    if kind == "phrase":
        text = ctx.data.get("spoken_transcripts", {}).get("phrase")
        if not text and ctx.files.get("phrase_audio"):
            text = sd.TRANSCRIBER(ctx.files["phrase_audio"], None)
        if not text:
            return "uncertain", "no phrase audio to check"
        return ("pass", "digits match") if item["expected_code"] in spoken_to_digits(text) \
            else ("fail", "spoken digits do not match")
    return "uncertain", f"unknown challenge type {kind}"


@register("liveness")
def liveness(ctx: CheckContext) -> CheckResult:
    ch = ctx.data.get("challenges") or {}
    issued = ch.get("issued", [])
    if not issued:
        return CheckResult.skipped("liveness", "No challenges issued")
    results, per = ch.get("results", {}), {}
    try:
        for item in issued:
            res = results.get(item["id"])
            per[item["type"]] = ("fail", "not completed") if res is None else _judge(item, res, ctx)
    except ImportError:
        return CheckResult.uncertain("liveness", "Whisper not installed (needed for the phrase challenge)")
    statuses = [v[0] for v in per.values()]
    details = {k: {"status": v[0], "note": v[1]} for k, v in per.items()}
    score = statuses.count("pass") / len(statuses)
    if "fail" in statuses:
        bad = [k for k, v in per.items() if v[0] == "fail"]
        return CheckResult("liveness", "fail", score, 0.6, f"Challenge failed: {', '.join(bad)}", details)
    if "uncertain" in statuses:
        return CheckResult("liveness", "uncertain", score, 0.3, "Some challenges could not be judged", details)
    return CheckResult("liveness", "pass", 1.0, 0.6, "All liveness challenges passed", details)
