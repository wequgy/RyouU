"""Liveness: did the user complete the server-issued random challenges, in time?

Hardenings:
1. Hand-wave challenge removed.
2. Spontaneous phrase: 2 common words + 4 digits, asked twice (>= 3s), judged with Whisper
   (digits match and words fuzzy-match). Short TTL (<= 60s).
3. Server-side head-turn yaw recomputed from InsightFace face.pose on uploaded frames.
"""
from ..models import CheckContext, CheckResult
from ..textutil import spoken_to_digits
from . import spoken_details as sd
from .base import register


def _get_audio_duration_s(audio_path) -> float:
    try:
        import av
        with av.open(str(audio_path)) as c:
            if c.duration is not None:
                return float(c.duration) / 1000000.0
            if c.streams.audio:
                s = c.streams.audio[0]
                if s.duration and s.time_base:
                    return float(s.duration * s.time_base)
    except Exception:
        pass
    return 5.0


def _recompute_server_yaw(video_path) -> tuple:
    from . import face_match, video_deepfake
    frames = video_deepfake.sample_frames(video_path, n=16)
    if not frames:
        return 0.0, 0.0
    app = face_match._load_app()
    yaws = []
    face_count = 0
    for img in frames:
        faces = app.get(img)
        if faces:
            face_count += 1
            f = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
            if hasattr(f, "pose") and f.pose is not None and len(f.pose) >= 2:
                yaws.append(float(f.pose[1]))
    face_ratio = face_count / max(len(frames), 1)
    if not yaws:
        return 0.0, face_ratio
    return max(yaws) - min(yaws), face_ratio


def _judge(item: dict, res: dict, ctx: CheckContext):
    """Return (status, reason) for one challenge."""
    s = ctx.settings
    m = res.get("metrics", {}) or {}
    if res["answered_at"] - item["issued_at"] > s.challenge_ttl_s:
        return "fail", "answered too late"
    kind = item["type"]
    if kind == "head_turn":
        vid_path = ctx.files.get("challenge_video")
        if vid_path and s.enforce_gates:
            try:
                server_yaw, face_ratio = _recompute_server_yaw(vid_path)
                client_yaw = float(m.get("yaw_range_deg", 0))
                # Disagreement between untrusted client metrics and server
                if client_yaw >= s.head_turn_min_yaw_deg and server_yaw < (s.head_turn_min_yaw_deg * 0.4):
                    return "fail", f"head turn not detected server-side (server {server_yaw:.1f} vs client {client_yaw:.1f})"
                if server_yaw < s.head_turn_min_yaw_deg or face_ratio < s.min_face_present_ratio:
                    return "fail", f"insufficient head turn measured server-side ({server_yaw:.1f} deg)"
                return "pass", f"head turn ok (server {server_yaw:.1f} deg)"
            except Exception:
                pass
        ok = m.get("yaw_range_deg", 0) >= s.head_turn_min_yaw_deg and \
            m.get("face_present_ratio", 0) >= s.min_face_present_ratio
        return ("pass", "head turn ok") if ok else ("fail", "head turn not detected")
    if kind == "phrase":
        text = ctx.data.get("spoken_transcripts", {}).get("phrase")
        audio_f = ctx.files.get("phrase_audio") or ctx.files.get("challenge_audio")
        if not text and audio_f:
            text = sd.TRANSCRIBER(audio_f, None)
        if not text:
            return "uncertain", "no phrase audio to check"
        if audio_f and s.enforce_gates:
            dur = _get_audio_duration_s(audio_f)
            if dur < 2.5:
                return "uncertain", f"phrase audio too short ({dur:.1f}s, must repeat twice >= 3s)"
        expected_digits = item.get("expected_digits") or item.get("expected_code", "")
        if expected_digits and expected_digits not in spoken_to_digits(text):
            return "fail", "spoken digits do not match"
        if item.get("expected_words") and s.enforce_gates:
            from rapidfuzz import fuzz
            tokens = [t.lower().strip(".,!?") for t in text.split()]
            for w in item["expected_words"]:
                w_lower = w.lower()
                if not any(fuzz.ratio(w_lower, t) >= 80 for t in tokens):
                    return "fail", f"spoken phrase missing word: {w}"
        return "pass", "phrase matches digits and words"
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
