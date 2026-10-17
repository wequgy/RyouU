"""AI-generated voice check via Detectif.ai (POST /v1/deepfake/detect).

Upload-based (multipart 'file'), not streaming. Backend only: the API key must never reach the browser.
Detectif's docs list different minimum clip lengths on two pages (4s vs 0.5s): test a short clip.
Results are signals, not proof. Phone-quality audio is less reliable and the model is tuned for English.
"""
import hashlib
import mimetypes
import time
import uuid
from pathlib import Path

import httpx

from ..models import CheckContext, CheckResult
from .base import register

CLIENT_FACTORY = lambda: httpx.Client(timeout=60)  # noqa: E731  (replaceable in tests)

def _call_detectif(method: str, endpoint: str, session_id: str, settings, path=None, data_payload=None, params=None) -> dict:
    url = f"{settings.detectif_base_url}{endpoint}"
    headers = {"Authorization": f"Bearer {settings.detectif_api_key}"}

    file_bytes = None
    file_hash = ""
    if path:
        path = Path(path)
        file_bytes = path.read_bytes()
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        idem = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{session_id}:{file_hash}:{endpoint}"))
        headers["Idempotency-Key"] = idem

    last = ""
    with CLIENT_FACTORY() as client:
        for attempt in range(1, settings.detectif_max_attempts + 1):
            try:
                if path and file_bytes:
                    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                    files = {"file": (path.name, file_bytes, mime)}
                    r = client.request(method, url, headers=headers, files=files, data=data_payload, params=params)
                elif data_payload:
                    r = client.request(method, url, headers=headers, json=data_payload, params=params)
                else:
                    r = client.request(method, url, headers=headers, params=params)
            except httpx.HTTPError as e:
                last = f"network error: {e}"
            else:
                if r.status_code == 200:
                    return r.json()
                if r.status_code in (429, 503):
                    last = f"HTTP {r.status_code} (busy)"
                    wait = float(r.headers.get("Retry-After", "1") or 1)
                    time.sleep(min(wait, settings.detectif_retry_sleep_cap_s))
                    continue
                try:
                    code = r.json().get("error", {}).get("code", "")
                except Exception:
                    code = ""
                raise RuntimeError(f"Detectif HTTP {r.status_code} {code}".strip())
    raise RuntimeError(f"Detectif unavailable after retries ({last})")


def detect(path, session_id: str, settings) -> dict:
    """POST /v1/deepfake/detect."""
    return _call_detectif("POST", "/deepfake/detect", session_id, settings, path=path)


def enroll_speaker(path, session_id: str, settings) -> dict:
    """POST /v1/speakers/enroll."""
    return _call_detectif("POST", "/speakers/enroll", session_id, settings, path=path)


def verify_speaker(path, speaker_id: str, session_id: str, settings) -> dict:
    """POST /v1/speakers/verify."""
    return _call_detectif("POST", "/speakers/verify", session_id, settings, path=path, data_payload={"speaker_id": speaker_id})


def delete_speaker(speaker_id: str, settings) -> dict:
    """DELETE /v1/speakers/{speaker_id}."""
    return _call_detectif("DELETE", f"/speakers/{speaker_id}", "cleanup", settings)


def get_credits(settings) -> dict:
    """GET /v1/credits."""
    return _call_detectif("GET", "/credits", "credits_query", settings)


def send_feedback(operation_id: str, feedback_type: str, settings) -> dict:
    """POST /v1/operations/{operation_id}/feedback."""
    return _call_detectif("POST", f"/operations/{operation_id}/feedback", "feedback", settings, data_payload={"feedback": feedback_type})


@register("voice_ai")
def voice_ai(ctx: CheckContext) -> CheckResult:
    s = ctx.settings
    gates = ctx.data.get("gates", {})
    if gates.get("id_image", {}).get("passed") is False or gates.get("selfie", {}).get("passed") is False:
        return CheckResult.skipped("voice_ai", "Skipped: session failed prior gates")

    phrase_audio = ctx.files.get("phrase_audio")
    challenge_audio = ctx.files.get("challenge_audio")
    enrollment_audio = ctx.files.get("enrollment_audio") or challenge_audio
    audio_path = phrase_audio or challenge_audio

    if not audio_path:
        return CheckResult.skipped("voice_ai", "No challenge audio recorded")
    if not s.detectif_api_key:
        return CheckResult.uncertain("voice_ai", "DETECTIF_API_KEY not set")

    # 1. AI-voice detection
    try:
        body = detect(audio_path, ctx.session_id, s)
        res = body["result"]
        verdict, fake_p = res["verdict"], float(res["score"])
    except (RuntimeError, KeyError, ValueError, TypeError) as e:
        return CheckResult.uncertain("voice_ai", f"Detectif voice check unavailable: {e}")

    details = {
        "verdict": verdict, "fake_score": fake_p, "threshold": res.get("threshold"),
        "duration_seconds": res.get("duration_seconds"), "request_id": body.get("request_id"),
        "operation_id": body.get("operation_id")
    }
    trust = 1.0 - fake_p

    if verdict == "fake":
        return CheckResult("voice_ai", "fail", trust, 0.7, f"Voice likely AI-generated (fake score {fake_p:.2f})", details)

    # 2. Speaker consistency (enrollment vs later clips)
    speaker_id = ctx.data.get("detectif_speaker_id")
    if enrollment_audio and phrase_audio and enrollment_audio != phrase_audio:
        try:
            if not speaker_id:
                enroll_res = enroll_speaker(enrollment_audio, ctx.session_id, s)
                speaker_id = enroll_res.get("speaker_id")
                if speaker_id:
                    ctx.data["detectif_speaker_id"] = speaker_id
            if speaker_id:
                verify_res = verify_speaker(phrase_audio, speaker_id, ctx.session_id, s)
                details["speaker_verify"] = verify_res
                is_match = verify_res.get("match", True)
                if not is_match:
                    return CheckResult("voice_ai", "fail", 0.1, 0.7,
                                       f"Speaker mismatch detected across audio clips (score: {verify_res.get('score', 0):.2f})", details)
        except Exception as e:
            details["speaker_verify_error"] = str(e)
            return CheckResult("voice_ai", "uncertain", 0.5, 0.3, f"Speaker consistency could not be verified: {e}", details)

    if verdict == "real":
        return CheckResult("voice_ai", "pass", trust, 0.7, f"Voice looks genuine (fake score {fake_p:.2f})", details)

    return CheckResult("voice_ai", "uncertain", 0.5, 0.2, "Detector could not judge this audio (try a longer, cleaner clip)", details)
