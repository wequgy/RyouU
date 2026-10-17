"""Spoken details vs ID details.

Ask FIXED questions (name, date of birth, last 4 digits of the ID), transcribe each answer, compare to what
the ID says. This proves consistency (and gives random-ish liveness), NOT identity: someone holding a
stolen ID also knows these details. A mismatch can be an ASR error, so policies send it to review, not reject.
"""
from ..models import CheckContext, CheckResult
from ..textutil import name_ratio, parse_date, spoken_to_digits
from .base import register

_WHISPER = None


def transcribe(path, prompt=None) -> str:
    """faster-whisper transcription (lazy import). `prompt` biases spelling toward the expected name."""
    global _WHISPER
    if _WHISPER is None:
        from faster_whisper import WhisperModel
        from ..config import get_settings
        try:
            _WHISPER = WhisperModel(get_settings().whisper_model, device="auto", compute_type="int8")
        except Exception:
            _WHISPER = WhisperModel(get_settings().whisper_model, device="cpu", compute_type="int8")
    try:
        segments, _ = _WHISPER.transcribe(str(path), language="en", initial_prompt=prompt, vad_filter=True)
    except Exception as e:
        if "cublas" in str(e).lower() or "cuda" in str(e).lower():
            from faster_whisper import WhisperModel
            from ..config import get_settings
            _WHISPER = WhisperModel(get_settings().whisper_model, device="cpu", compute_type="int8")
            segments, _ = _WHISPER.transcribe(str(path), language="en", initial_prompt=prompt, vad_filter=True)
        else:
            raise
    return " ".join(seg.text.strip() for seg in segments).strip()


TRANSCRIBER = transcribe  # replaceable in tests

FIELDS = ("name", "dob", "id_last4")


def _answer(ctx: CheckContext, key: str, expected_name):
    """Transcript for one field: provided text wins, otherwise transcribe the uploaded audio."""
    t = ctx.data.get("spoken_transcripts", {}).get(key)
    if t:
        return t
    path = ctx.files.get(f"spoken_{key}")
    if path:
        return TRANSCRIBER(path, expected_name if key == "name" else None)
    shared = ctx.files.get("challenge_audio") or ctx.files.get("phrase_audio")
    if shared:
        shared_t = ctx.data.setdefault("_cached_transcripts", {}).get("shared")
        if not shared_t:
            shared_t = TRANSCRIBER(shared, expected_name)
            ctx.data["_cached_transcripts"]["shared"] = shared_t
        return shared_t
    return None


@register("spoken_details")
def spoken_details(ctx: CheckContext) -> CheckResult:
    expected = ctx.data.get("expected", {}) or {}
    todo = [k for k in FIELDS if expected.get(k)]
    if not todo:
        return CheckResult.skipped("spoken_details", "No expected ID details to compare against")
    matched, mismatched, missing, details = [], [], [], {}
    try:
        for key in todo:
            heard = _answer(ctx, key, expected.get("name"))
            if heard is None:
                missing.append(key)
                continue
            if key == "name":
                ratio = name_ratio(expected["name"], heard)
                ok = ratio >= ctx.settings.name_match_ratio
                details[key] = {"heard": heard, "ratio": ratio}
            elif key == "dob":
                a, b = parse_date(expected["dob"]), parse_date(heard)
                ok = a is not None and a == b
                details[key] = {"heard": heard, "parsed": str(b) if b else None}
            else:
                want = "".join(c for c in expected["id_last4"] if c.isdigit())[-4:]
                got = spoken_to_digits(heard)
                ok = bool(want) and got.endswith(want)
                details[key] = {"heard": heard, "digits": got}
            (matched if ok else mismatched).append(key)
    except ImportError:
        return CheckResult.uncertain("spoken_details", "Whisper not installed (pip install -r requirements-ml.txt)")
    details["missing"] = missing
    if not matched and not mismatched:
        return CheckResult.skipped("spoken_details", "No spoken answers recorded", **details)
    if mismatched:
        return CheckResult("spoken_details", "fail", len(matched) / len(todo), 0.5,
                           f"Spoken answer does not match ID for: {', '.join(mismatched)}", details)
    if missing:
        return CheckResult("spoken_details", "uncertain", len(matched) / len(todo), 0.3,
                           f"Matched {', '.join(matched)}; no answer for {', '.join(missing)}", details)
    return CheckResult("spoken_details", "pass", 1.0, 0.6, "Spoken details match the ID", details)
