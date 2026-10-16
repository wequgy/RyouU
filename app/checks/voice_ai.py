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


def detect(path, session_id: str, settings) -> dict:
    """Call Detectif. Returns the parsed JSON body. Raises RuntimeError on terminal failure."""
    path = Path(path)
    data = path.read_bytes()
    # Stable idempotency key: retrying the same file in the same session never double-charges.
    idem = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{session_id}:{hashlib.sha256(data).hexdigest()}"))
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    url = f"{settings.detectif_base_url}/deepfake/detect"
    headers = {"Authorization": f"Bearer {settings.detectif_api_key}", "Idempotency-Key": idem}
    last = ""
    with CLIENT_FACTORY() as client:
        for attempt in range(1, settings.detectif_max_attempts + 1):
            try:
                r = client.post(url, headers=headers, files={"file": (path.name, data, mime)})
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


@register("voice_ai")
def voice_ai(ctx: CheckContext) -> CheckResult:
    s = ctx.settings
    path = ctx.files.get("challenge_audio")
    if not path:
        return CheckResult.skipped("voice_ai", "No challenge audio recorded")
    if not s.detectif_api_key:
        return CheckResult.uncertain("voice_ai", "DETECTIF_API_KEY not set")
    try:
        body = detect(path, ctx.session_id, s)
        res = body["result"]
        verdict, fake_p = res["verdict"], float(res["score"])
    except (RuntimeError, KeyError, ValueError, TypeError) as e:
        return CheckResult.uncertain("voice_ai", f"Voice check unavailable: {e}")
    details = {"verdict": verdict, "fake_score": fake_p, "threshold": res.get("threshold"),
               "duration_seconds": res.get("duration_seconds"), "request_id": body.get("request_id"),
               "operation_id": body.get("operation_id")}
    trust = 1.0 - fake_p
    if verdict == "real":
        return CheckResult("voice_ai", "pass", trust, 0.7, f"Voice looks genuine (fake score {fake_p:.2f})", details)
    if verdict == "fake":
        return CheckResult("voice_ai", "fail", trust, 0.7, f"Voice likely AI-generated (fake score {fake_p:.2f})", details)
    return CheckResult("voice_ai", "uncertain", 0.5, 0.2, "Detector could not judge this audio (try a longer, cleaner clip)", details)
