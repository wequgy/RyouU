"""KYC verification service API.

Customer (tenant) API:  /v1/...   auth: Authorization: Bearer <api key>
End-user flow API:      /flow/... auth: X-Flow-Token header (token is in the flow URL)
"""
import hashlib
import os
import re
import secrets
import shutil
import tempfile
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import challenges, db, pipeline, webhooks
from .checks import otp  # noqa: F401  (also registers all checks via package import)
from . import checks  # noqa: F401
from .config import get_settings
from .models import (ChallengeResults, CreateVerification, OtpSend, OtpVerify, ReviewBody, Signals)
from .policies import POLICIES, get_policy, steps_for
from .security import (
    decrypt_bytes,
    encrypt_bytes,
    hash_key,
    new_token,
    require_flow,
    require_tenant,
    sign_evidence_token,
    verify_evidence_token,
)

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".webm", ".avi", ".mkv", ".flv"}
AUDIO_EXT = {".wav", ".mp4", ".m4a", ".webm", ".ogg", ".flac"}
UPLOAD_KINDS = {"id_image": IMAGE_EXT, "selfie": IMAGE_EXT, "challenge_audio": AUDIO_EXT,
                "phrase_audio": AUDIO_EXT, "spoken_name": AUDIO_EXT, "spoken_dob": AUDIO_EXT,
                "spoken_id_last4": AUDIO_EXT, "challenge_video": VIDEO_EXT}
TRANSCRIPT_KEYS = {"name", "dob", "id_last4", "phrase"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    if get_settings().seed_demo:
        db.seed_demo_tenants()
    # Process any pending jobs from previous runs
    pending = db.get_pending_pipeline_jobs()
    for job in pending:
        try:
            pipeline.process(job["vid"], job_id=job["id"])
        except Exception:
            pass
    yield


app = FastAPI(title="KYC Verification Service", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"] if get_settings().dev_mode else get_settings().cors_origins,
                   allow_methods=["*"], allow_headers=["*"])

_STATIC_DIR = Path(__file__).parent / "static"
_FLOW_HTML = _STATIC_DIR / "flow.html"
_DASHBOARD_HTML = _STATIC_DIR / "dashboard.html"

app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


def require_tenant_with_rate_limit(tenant: dict = Depends(require_tenant)) -> dict:
    if not db.check_rate_limit(f"rate:tenant:{tenant['id']}", limit=120, window_s=60):
        raise HTTPException(429, "Tenant rate limit exceeded")
    return tenant


@app.get("/healthz")
def healthz():
    return {"ok": True, "time": time.time()}


@app.get("/readyz")
def readyz():
    s = get_settings()
    models_status = {}
    
    # 1. RapidOCR
    try:
        from .checks.id_details import _get_ocr
        _get_ocr()
        models_status["rapidocr"] = "ok"
    except Exception as e:
        models_status["rapidocr"] = f"error: {e}"

    # 2. InsightFace
    try:
        from .checks.face_match import _load_app
        _load_app()
        models_status["insightface"] = "ok"
    except Exception as e:
        models_status["insightface"] = f"error: {e}"

    # 3. Whisper
    try:
        from .checks.spoken_details import _WHISPER
        models_status["whisper"] = "ok"
    except Exception as e:
        models_status["whisper"] = f"error: {e}"

    # 4. Deepfake ViT / GenD
    try:
        from .checks.video_deepfake import _load
        _load()
        models_status["deepfake_vit"] = "ok"
    except Exception as e:
        models_status["deepfake_vit"] = f"error: {e}"

    # 5. Detectif credits / health
    detectif_status = {"status": "ok", "credits": None}
    if s.detectif_api_key:
        try:
            from .checks.voice_ai import get_credits
            cr = get_credits(s)
            detectif_status["credits"] = cr
        except Exception as e:
            detectif_status["status"] = "error"
            detectif_status["error"] = str(e)
    else:
        detectif_status["status"] = "missing_api_key"

    all_ready = all(v == "ok" for v in models_status.values()) and (detectif_status["status"] == "ok")
    resp_body = {
        "status": "ready" if all_ready else "not_ready",
        "models": models_status,
        "detectif": detectif_status
    }

    if os.environ.get("KYC_STRICT") == "1" and not all_ready:
        return JSONResponse(status_code=503, content=resp_body)
    return resp_body


@app.get("/flow", response_class=HTMLResponse, include_in_schema=False)
def flow_page():
    """Serve the hosted KYC verification UI. The flow URL opens this page in a WebView."""
    if not _FLOW_HTML.exists():
        raise HTTPException(404, "Flow page not found. Run setup or check app/static/flow.html.")
    return HTMLResponse(_FLOW_HTML.read_text(encoding="utf-8"))


@app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
def dashboard_page():
    """Serve the KYC Compliance Dashboard UI."""
    if not _DASHBOARD_HTML.exists():
        raise HTTPException(404, "Dashboard page not found.")
    return HTMLResponse(_DASHBOARD_HTML.read_text(encoding="utf-8"))


# ======================= tenant (customer) API =======================
@app.post("/v1/verifications", status_code=201)
def create_verification(request: Request, body: CreateVerification, tenant: dict = Depends(require_tenant_with_rate_limit)):
    s = get_settings()

    # Idempotency check
    idempotency_key = request.headers.get("idempotency-key")
    if idempotency_key:
        cached = db.get_idempotency(tenant["id"], idempotency_key)
        if cached:
            return JSONResponse(status_code=cached["status_code"], content=cached["response_body"])

    policy = body.policy or tenant["default_policy"]
    try:
        get_policy(policy)
    except KeyError:
        raise HTTPException(400, f"Unknown policy '{policy}'. Available: {sorted(POLICIES)}")

    # One active session per reference_id: expire prior active session
    prior = db.get_active_verification_by_ref(tenant["id"], body.reference_id)
    if prior:
        db.set_status(prior["id"], "expired")

    token = new_token()
    v = db.create_verification(tenant["id"], body.reference_id, policy, body.expected.model_dump(),
                               hash_key(token), s.flow_token_ttl_s)
    base = str(request.base_url).rstrip("/")
    flow_base = f"{base}/flow" if "localhost" in s.flow_base_url else s.flow_base_url
    api_base = base if "localhost" in s.public_base_url else s.public_base_url
    resp = {"id": v["id"], "status": v["status"], "policy": policy, "expires_at": v["expires_at"],
            "flow_url": f"{flow_base}?v={v['id']}&t={token}&api={api_base}"}

    if idempotency_key:
        db.save_idempotency(tenant["id"], idempotency_key, 201, resp)

    return resp


@app.get("/v1/verifications")
def list_verifications(limit: int = 50, tenant: dict = Depends(require_tenant_with_rate_limit)):
    limit = max(1, min(limit, 200))
    return {"data": [pipeline.public_view(v) for v in db.list_verifications(tenant["id"], limit)]}


@app.get("/v1/verifications/{vid}")
def get_verification(vid: str, tenant: dict = Depends(require_tenant_with_rate_limit)):
    v = db.get_verification_for_tenant(vid, tenant["id"])
    if not v:
        raise HTTPException(404, "Verification not found")
    return pipeline.public_view(v)


@app.get("/v1/verifications/{vid}/evidence")
def get_verification_evidence(request: Request, vid: str, tenant: dict = Depends(require_tenant_with_rate_limit)):
    """Return signed expiring URLs for all encrypted evidence artifacts."""
    v = db.get_verification_for_tenant(vid, tenant["id"])
    if not v:
        raise HTTPException(404, "Verification not found")
    base = str(request.base_url).rstrip("/")
    api_base = base if "localhost" in get_settings().public_base_url else get_settings().public_base_url
    files = v.get("data", {}).get("files", {})
    manifest = {}
    for kind in sorted(files):
        token = sign_evidence_token(vid, kind, expires_in_s=3600)
        manifest[kind] = {
            "kind": kind,
            "url": f"{api_base}/v1/verifications/{vid}/evidence/{kind}?token={token}",
            "expires_in_s": 3600,
        }
    return {"verification_id": vid, "evidence": manifest}


@app.get("/v1/verifications/{vid}/evidence/{kind}")
def download_evidence(request: Request, vid: str, kind: str, token: Optional[str] = None):
    """Download decrypted evidence using an expiring signed token or tenant API key."""
    v = db.get_verification(vid)
    if not v:
        raise HTTPException(404, "Verification not found")

    authorized = False
    if token and verify_evidence_token(vid, kind, token):
        authorized = True
    else:
        auth_hdr = request.headers.get("authorization", "")
        if auth_hdr.lower().startswith("bearer "):
            tenant = db.tenant_by_api_key(auth_hdr.split(" ", 1)[1].strip())
            if tenant and tenant["id"] == v["tenant_id"]:
                authorized = True

    if not authorized:
        raise HTTPException(401, "Invalid or expired evidence token")

    path_str = v.get("data", {}).get("files", {}).get(kind)
    if not path_str or not Path(path_str).exists():
        raise HTTPException(404, f"Evidence '{kind}' not found")

    encrypted_blob = Path(path_str).read_bytes()
    try:
        content = decrypt_bytes(encrypted_blob)
    except Exception:
        content = encrypted_blob

    ext = Path(path_str).suffix.lower()
    media_map = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
        ".mp4": "video/mp4", ".webm": "video/webm", ".wav": "audio/wav", ".m4a": "audio/mp4"
    }
    return Response(content=content, media_type=media_map.get(ext, "application/octet-stream"))


@app.post("/v1/verifications/{vid}/review")
def review(vid: str, body: ReviewBody, bg: BackgroundTasks, tenant: dict = Depends(require_tenant_with_rate_limit)):
    """A human reviewer makes the final call. This is how needs_review / rejected_recommended get resolved."""
    v = db.get_verification_for_tenant(vid, tenant["id"])
    if not v:
        raise HTTPException(404, "Verification not found")
    if v["status"] != "completed":
        raise HTTPException(409, f"Cannot review a verification in status '{v['status']}'")
    if body.decision not in ("approved", "rejected"):
        raise HTTPException(400, "decision must be 'approved' or 'rejected'")
    db.save_review(vid, {"decision": body.decision, "note": body.note, "at": time.time()})
    bg.add_task(_notify, vid, "verification.reviewed")
    return pipeline.public_view(db.get_verification(vid))


@app.delete("/v1/verifications/{vid}", status_code=204)
def delete_verification(vid: str, tenant: dict = Depends(require_tenant_with_rate_limit)):
    """Data deletion: removes the record and all uploaded files."""
    if not db.get_verification_for_tenant(vid, tenant["id"]):
        raise HTTPException(404, "Verification not found")
    shutil.rmtree(get_settings().data_dir / "uploads" / vid, ignore_errors=True)
    db.delete_verification(vid)


@app.get("/v1/policies")
def list_policies(tenant: dict = Depends(require_tenant_with_rate_limit)):
    return {"default": tenant["default_policy"], "policies": POLICIES}


# ======================= Tenant Admin / Credentials API =======================
@app.post("/v1/tenant/rotate-key")
def rotate_api_key(tenant: dict = Depends(require_tenant_with_rate_limit)):
    new_key = "kyc_live_" + secrets.token_urlsafe(32)
    db.rotate_tenant_api_key(tenant["id"], new_key)
    return {"api_key": new_key, "message": "Store this key now. It cannot be shown again."}


@app.post("/v1/tenant/rotate-webhook-secret")
def rotate_webhook_secret(tenant: dict = Depends(require_tenant_with_rate_limit)):
    new_secret = "whsec_" + secrets.token_urlsafe(32)
    db.rotate_tenant_webhook_secret(tenant["id"], new_secret)
    return {"webhook_secret": new_secret}


class WebhookUpdateBody(BaseModel):
    webhook_url: str


@app.patch("/v1/tenant/webhook")
def update_webhook(body: WebhookUpdateBody, tenant: dict = Depends(require_tenant_with_rate_limit)):
    db.update_tenant_webhook_url(tenant["id"], body.webhook_url)
    return {"webhook_url": body.webhook_url}


def _notify(vid: str, event: str) -> None:
    v = db.get_verification(vid)
    if v:
        status = webhooks.deliver(db.tenant_by_id(v["tenant_id"]), event, pipeline.public_view(v))
        db.save_webhook_status(vid, status)


# ======================= end-user flow API =======================
def _editable(v: dict) -> dict:
    if v["status"] not in ("created", "in_progress"):
        raise HTTPException(409, f"Verification is '{v['status']}' and can no longer be changed")
    if v["status"] == "created":
        db.set_status(v["id"], "in_progress")
    return v


def _get_gates(v: dict) -> dict:
    return (v.get("data") or {}).get("gates") or {}


def _check_gate_lock(gates: dict, gate_name: str):
    g = gates.get(gate_name, {})
    if g.get("locked") or g.get("attempts", 0) >= 3:
        raise HTTPException(429, f"Too many failed attempts for {gate_name}. Verification session is locked.")


def _record_gate_attempt(vid: str, gate_name: str, passed: bool, reason: str, extra: dict = None):
    def mut(d):
        gates = d.setdefault("gates", {})
        g = gates.setdefault(gate_name, {"passed": False, "attempts": 0, "locked": False, "reason": ""})
        g["attempts"] = g.get("attempts", 0) + 1
        g["passed"] = passed
        g["reason"] = reason
        if extra:
            g.update(extra)
        if not passed and g["attempts"] >= 3:
            g["locked"] = True
    db.update_data(vid, mut)


def check_container_timestamp(blob: bytes, ext: str, session_start: float) -> tuple:
    """Check if media container timestamp predates session start."""
    if ext in (".mp4", ".webm", ".wav", ".m4a"):
        try:
            import io, av, dateparser
            with av.open(io.BytesIO(blob)) as container:
                meta = container.metadata or {}
                c_time = meta.get("creation_time") or meta.get("date")
                if not c_time and container.streams.video:
                    c_time = container.streams.video[0].metadata.get("creation_time")
                if c_time:
                    dt = dateparser.parse(c_time)
                    if dt:
                        ts = dt.timestamp()
                        if ts < (session_start - 30.0):
                            return False, f"Media container timestamp ({c_time}) predates session start (replay rejected)"
        except Exception:
            pass
    return True, "ok"


@app.get("/flow/{vid}/context")
def flow_context(vid: str, v: dict = Depends(require_flow)):
    tenant = db.tenant_by_id(v["tenant_id"])
    policy = get_policy(v["policy"])
    review = v.get("review")
    final_decision = review["decision"] if review else v.get("decision")
    return {
        "id": v["id"],
        "status": v["status"],
        "customer": tenant["name"],
        "policy": policy["name"],
        "decision": v.get("decision"),
        "final_decision": final_decision,
        "gates": _get_gates(v),
        "results": v.get("results"),
        "reasons": v.get("reasons"),
        "steps": steps_for(policy),
        "expires_at": v["expires_at"],
        "uploaded": sorted(v["data"].get("files", {})),
        "verified": sorted(v["data"].get("verified", {})),
    }


@app.post("/flow/{vid}/otp/send")
def otp_send(request: Request, vid: str, body: OtpSend, v: dict = Depends(require_flow)):
    _editable(v)
    client_ip = request.client.host if request.client else "unknown"
    if not db.check_rate_limit(f"rate:ip_otp:{client_ip}", limit=10, window_s=60):
        raise HTTPException(429, "Too many OTP requests from this IP. Please wait.")
    try:
        return otp.issue(vid, body.channel, body.destination)
    except otp.OtpError as e:
        raise HTTPException(429 if "Too many" in str(e) else 400, str(e))


@app.post("/flow/{vid}/otp/verify")
def otp_verify(vid: str, body: OtpVerify, v: dict = Depends(require_flow)):
    _editable(v)
    if not otp.verify(vid, body.channel, body.code):
        raise HTTPException(400, "Invalid or expired code")
    return {"verified": True, "channel": body.channel}


@app.post("/flow/{vid}/upload/{kind}")
async def upload(request: Request, vid: str, kind: str, file: UploadFile = File(...), v: dict = Depends(require_flow)):
    _editable(v)
    allowed = UPLOAD_KINDS.get(kind)
    if allowed is None:
        raise HTTPException(400, f"Unknown upload kind. Allowed: {sorted(UPLOAD_KINDS)}")
    ext = Path(file.filename or "").suffix.lower()
    if not ext:
        ct = (file.content_type or "").lower()
        if "png" in ct:
            ext = ".png"
        elif "webp" in ct:
            ext = ".webp"
        elif "jpeg" in ct or "jpg" in ct:
            ext = ".jpeg"
        elif "webm" in ct:
            ext = ".webm"
        elif "mp4" in ct:
            ext = ".mp4"
        elif "wav" in ct:
            ext = ".wav"
    if not ext or ext not in allowed:
        raise HTTPException(415, f"File type {ext or '(none)'} not allowed for {kind}")
    s = get_settings()
    limit = s.max_upload_mb * 1024 * 1024
    blob = await file.read(limit + 1)
    if len(blob) > limit:
        raise HTTPException(413, f"File larger than {s.max_upload_mb} MB")
    if not blob:
        raise HTTPException(400, "Empty file")

    # Rate limits per IP and session
    client_ip = request.client.host if request.client else "unknown"
    if not db.check_rate_limit(f"rate:ip_upload:{client_ip}", limit=30, window_s=60):
        raise HTTPException(429, "Too many uploads from this IP. Please wait.")
    if not db.check_rate_limit(f"rate:vid_upload:{vid}", limit=20, window_s=60):
        raise HTTPException(429, "Too many uploads for this session. Please wait.")

    # Replay protection: check sha256 per tenant
    file_hash = hashlib.sha256(blob).hexdigest()
    if s.enforce_gates and kind in ("selfie", "challenge_video", "challenge_audio", "phrase_audio"):
        prior_hash = db.get_media_hash(v["tenant_id"], file_hash)
        if prior_hash and prior_hash["vid"] != vid:
            raise HTTPException(422, f"Media replay detected: this {kind} was already used in verification {prior_hash['vid']}")
        
        # Container timestamp check
        c_ok, c_msg = check_container_timestamp(blob, ext, v["created_at"])
        if not c_ok:
            raise HTTPException(422, c_msg)

    gates = _get_gates(v)
    if s.enforce_gates:
        if kind not in ("id_image", "selfie"):
            if not (gates.get("id_image", {}).get("passed") and gates.get("selfie", {}).get("passed")):
                raise HTTPException(403, "Both ID and Selfie gates must pass before uploading other files")

        if kind == "selfie":
            if not gates.get("id_image", {}).get("passed"):
                raise HTTPException(403, "ID image must be uploaded and pass verification before selfie")
            _check_gate_lock(gates, "selfie")

        if kind == "id_image":
            _check_gate_lock(gates, "id_image")
            from .checks.id_details import verify_id_details
            expected = (v.get("data") or {}).get("expected") or {}
            ok, reason, details = verify_id_details(blob, expected)
            if not ok:
                _record_gate_attempt(vid, "id_image", False, reason, {"ocr_details": details})
                raise HTTPException(422, reason)
            _record_gate_attempt(vid, "id_image", True, reason, {"ocr_details": details})

        if kind == "selfie":
            from .checks.face_match import verify_face_match
            id_encrypted_path = (v.get("data") or {}).get("files", {}).get("id_image")
            if not id_encrypted_path or not Path(id_encrypted_path).exists():
                raise HTTPException(403, "ID image not found")

            temp_dir = Path(tempfile.mkdtemp(prefix=f"kyc_gate_{vid}_"))
            try:
                decrypted_id = decrypt_bytes(Path(id_encrypted_path).read_bytes())
                tmp_id = temp_dir / "id_image.jpg"
                tmp_id.write_bytes(decrypted_id)
                tmp_selfie = temp_dir / f"selfie{ext}"
                tmp_selfie.write_bytes(blob)

                res = verify_face_match(tmp_id, tmp_selfie, s)
                if res.status != "pass":
                    reason = f"Face verification did not pass: {res.reason}"
                    _record_gate_attempt(vid, "selfie", False, reason, {"face_match_details": res.details})
                    raise HTTPException(422, reason)
                _record_gate_attempt(vid, "selfie", True, res.reason, {"face_match_details": res.details})

                # Cross-session face check
                selfie_details = res.details.get("selfie", {})
                if "embedding" in selfie_details:
                    emb = selfie_details["embedding"]
                    prior_face = db.find_cross_session_face(v["tenant_id"], v["reference_id"], emb)
                    if prior_face:
                        flag_msg = f"Face matches prior verification {prior_face['vid']} with reference_id '{prior_face['reference_id']}'"
                        def mut_flag(d):
                            d["cross_session_flag"] = flag_msg
                        db.update_data(vid, mut_flag)
                    db.record_face_embedding(v["tenant_id"], v["reference_id"], vid, emb, file_hash)
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

    folder = s.data_dir / "uploads" / vid           # filename is server-chosen: no path traversal
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / f"{kind}{ext}"
    dest.write_bytes(encrypt_bytes(blob))

    if s.enforce_gates and kind in ("selfie", "challenge_video", "challenge_audio", "phrase_audio"):
        db.record_media_hash(v["tenant_id"], file_hash, kind, vid)

    def mut(d):
        d.setdefault("files", {})[kind] = str(dest)
    db.update_data(vid, mut)
    return {"stored": kind, "bytes": len(blob)}


@app.post("/flow/{vid}/signals")
def post_signals(vid: str, body: Signals, v: dict = Depends(require_flow)):
    _editable(v)

    def mut(d):
        d["signals"] = body.model_dump()
    db.update_data(vid, mut)
    return {"stored": True}


@app.post("/flow/{vid}/challenges")
def issue_challenges(vid: str, v: dict = Depends(require_flow)):
    _editable(v)
    if get_settings().enforce_gates:
        gates = _get_gates(v)
        if not (gates.get("id_image", {}).get("passed") and gates.get("selfie", {}).get("passed")):
            raise HTTPException(403, "Both ID and Selfie gates must pass before proceeding to challenges")
    return {"challenges": challenges.issue(vid), "ttl_s": get_settings().challenge_ttl_s}


@app.post("/flow/{vid}/challenges/result")
def challenge_result(vid: str, body: ChallengeResults, v: dict = Depends(require_flow)):
    _editable(v)
    if get_settings().enforce_gates:
        gates = _get_gates(v)
        if not (gates.get("id_image", {}).get("passed") and gates.get("selfie", {}).get("passed")):
            raise HTTPException(403, "Both ID and Selfie gates must pass before recording challenge results")
    out = challenges.record_results(vid, [r.model_dump() for r in body.results])
    if out["rejected"]:
        raise HTTPException(400, f"Unknown or already-answered challenge ids: {out['rejected']}")
    return {"stored": len(body.results)}


@app.post("/flow/{vid}/transcripts")
def dev_transcripts(vid: str, body: dict, v: dict = Depends(require_flow)):
    """DEV ONLY: supply spoken transcripts without running Whisper."""
    if not get_settings().dev_mode:
        raise HTTPException(403, "Disabled outside dev mode")
    _editable(v)
    if get_settings().enforce_gates:
        gates = _get_gates(v)
        if not (gates.get("id_image", {}).get("passed") and gates.get("selfie", {}).get("passed")):
            raise HTTPException(403, "Both ID and Selfie gates must pass before submitting transcripts")
    clean = {k: str(t)[:500] for k, t in body.items() if k in TRANSCRIPT_KEYS}

    def mut(d):
        d.setdefault("spoken_transcripts", {}).update(clean)
    db.update_data(vid, mut)
    return {"stored": sorted(clean)}


@app.post("/flow/{vid}/submit", status_code=202)
def submit(vid: str, bg: BackgroundTasks, v: dict = Depends(require_flow)):
    if get_settings().enforce_gates:
        gates = _get_gates(v)
        if not (gates.get("id_image", {}).get("passed") and gates.get("selfie", {}).get("passed")):
            raise HTTPException(403, "Both ID and Selfie gates must pass before submitting verification")
    if not db.claim_for_processing(vid):
        raise HTTPException(409, f"Verification is '{v['status']}' and cannot be submitted")
    job_id = db.enqueue_pipeline_job(vid, v["tenant_id"])
    bg.add_task(pipeline.process, vid, job_id=job_id)
    return {"status": "processing", "id": vid, "job_id": job_id}


class OperationFeedback(BaseModel):
    feedback: str = "false_alarm"


@app.post("/v1/operations/{operation_id}/feedback")
def submit_operation_feedback(operation_id: str, body: OperationFeedback, tenant: dict = Depends(require_tenant_with_rate_limit)):
    """Wire dashboard false alarm button to Detectif feedback endpoint."""
    s = get_settings()
    try:
        from .checks.voice_ai import send_feedback
        res = send_feedback(operation_id, body.feedback, s)
        return {"status": "success", "result": res}
    except Exception as e:
        return {"status": "error", "message": str(e)}
