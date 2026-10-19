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

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, Header, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import challenges, db, pipeline, webhooks
from .checks import otp  # noqa: F401  (also registers all checks via package import)
from . import checks  # noqa: F401
from .config import get_settings
from .models import (
    ChallengeResults,
    ClipMetadata,
    CreateInterview,
    CreateVerification,
    OtpSend,
    OtpVerify,
    ReviewBody,
    Signals,
)
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


def check_system_readiness():
    """Verify operational readiness of every required AI model, database, and Detectif API."""
    s = get_settings()
    models = {}

    # 1. InsightFace buffalo_l
    try:
        from .checks import face_match
        face_match._load_app()
        models["InsightFace (buffalo_l)"] = {"status": "ready", "license": "InsightFace Non-Commercial", "purpose": "Face embeddings and pose yaw"}
    except Exception as e:
        models["InsightFace (buffalo_l)"] = {"status": "error", "error": str(e)}

    # 2. MediaPipe Face Landmarker
    try:
        from .checks import liveness
        liveness._load_face_landmarker()
        models["MediaPipe Face Landmarker (face_landmarker.task)"] = {"status": "ready", "license": "Apache-2.0", "purpose": "Eye blink blendshapes"}
    except Exception as e:
        models["MediaPipe Face Landmarker (face_landmarker.task)"] = {"status": "error", "error": str(e)}

    # 3. MiniFASNet Passive Anti-Spoofing
    try:
        from .checks import anti_spoof
        anti_spoof._load_session()
        models["MiniFASNetV2 (Silent-Face-Anti-Spoofing)"] = {"status": "ready", "license": "Apache-2.0", "purpose": "Passive face anti-spoofing"}
    except Exception as e:
        models["MiniFASNetV2 (Silent-Face-Anti-Spoofing)"] = {"status": "error", "error": str(e)}

    # 4. RapidOCR
    try:
        from .checks import id_details
        id_details._get_ocr()
        models["RapidOCR (onnxruntime)"] = {"status": "ready", "license": "Apache-2.0", "purpose": "ID document text extraction"}
    except Exception as e:
        models["RapidOCR (onnxruntime)"] = {"status": "error", "error": str(e)}

    # 5. Faster-Whisper
    try:
        from faster_whisper import WhisperModel
        models["Faster-Whisper (ASR)"] = {"status": "ready", "model": s.whisper_model, "license": "MIT", "purpose": "Speech transcription"}
    except Exception as e:
        models["Faster-Whisper (ASR)"] = {"status": "error", "error": str(e)}

    # 6. ViT Deepfake Detector
    try:
        from .checks import video_deepfake
        video_deepfake._load_vit_model()
        models["ViT Deepfake Detector (prithivMLmods/Deep-Fake-Detector-v2-Model)"] = {"status": "ready", "license": "Apache-2.0", "purpose": "Visual deepfake classification"}
    except Exception as e:
        models["ViT Deepfake Detector (prithivMLmods/Deep-Fake-Detector-v2-Model)"] = {"status": "error", "error": str(e)}

    # 7. SyncNet Lip-Sync
    try:
        from .checks import lip_sync
        has_w = lip_sync.SYNCNET_WEIGHTS_PATH.exists() and lip_sync.S3FD_WEIGHTS_PATH.exists()
        models["SyncNet (syncnet-python)"] = {
            "status": "ready" if has_w else "uncalibrated",
            "weights_present": has_w,
            "license": "MIT",
            "purpose": "Audio-visual lip synchronization"
        }
    except Exception as e:
        models["SyncNet (syncnet-python)"] = {"status": "error", "error": str(e)}

    # 8. Detectif.ai Voice API
    if s.detectif_api_key:
        models["Detectif.ai (Voice AI)"] = {"status": "configured", "base_url": s.detectif_base_url, "purpose": "Voice cloning & speaker verification"}
    else:
        models["Detectif.ai (Voice AI)"] = {"status": "unconfigured", "error": "DETECTIF_API_KEY not set"}

    # In production strict mode, critical components must be ready
    critical_names = [
        "InsightFace (buffalo_l)",
        "MediaPipe Face Landmarker (face_landmarker.task)",
        "MiniFASNetV2 (Silent-Face-Anti-Spoofing)",
        "RapidOCR (onnxruntime)",
        "Faster-Whisper (ASR)",
        "ViT Deepfake Detector (prithivMLmods/Deep-Fake-Detector-v2-Model)"
    ]
    all_ready = all(models.get(name, {}).get("status") in ("ready", "configured", "uncalibrated") for name in critical_names)
    return all_ready, models


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    s = get_settings()
    if s.seed_demo:
        db.seed_demo_tenants()

    # Fail fast if critical components unavailable under strict production mode
    if s.strict_mode and not s.dev_mode:
        all_ready, models = check_system_readiness()
        if not all_ready or models.get("Detectif.ai (Voice AI)", {}).get("status") != "configured":
            failed = [f"{k}: {v.get('error', 'not ready')}" for k, v in models.items() if v.get("status") not in ("ready", "configured", "uncalibrated")]
            if not s.detectif_api_key:
                failed.append("Detectif.ai: DETECTIF_API_KEY is missing")
            raise RuntimeError(f"Startup aborted under KYC_STRICT=1: {'; '.join(failed)}")

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
    all_ready, models = check_system_readiness()
    status_code = 200 if all_ready else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if all_ready else "not_ready",
            "strict_mode": get_settings().strict_mode,
            "models": models,
        }
    )




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


class FlowDetailsBody(BaseModel):
    name: Optional[str] = None
    dob: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


@app.post("/flow/{vid}/details")
def update_flow_details(vid: str, body: FlowDetailsBody, v: dict = Depends(require_flow)):
    _editable(v)
    def mut(d):
        exp = d.setdefault("expected", {})
        if body.name: exp["name"] = body.name.strip()
        if body.dob: exp["dob"] = body.dob.strip()
        if body.email: exp["email"] = body.email.strip()
        if body.phone: exp["phone"] = body.phone.strip()
    db.update_data(vid, mut)
    return {"updated": True}


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


@app.post("/flow/{vid}/gates/{channel}/send")
def gate_otp_send(request: Request, vid: str, channel: str, body: dict, v: dict = Depends(require_flow)):
    dest = body.get("destination") or body.get("phone") or body.get("email") or ""
    return otp_send(request, vid, OtpSend(channel=channel, destination=dest), v)


@app.post("/flow/{vid}/otp/verify")
def otp_verify(vid: str, body: OtpVerify, v: dict = Depends(require_flow)):
    _editable(v)
    if not otp.verify(vid, body.channel, body.code):
        raise HTTPException(400, "Invalid or expired code")
    return {"verified": True, "channel": body.channel}


@app.post("/flow/{vid}/gates/{channel}/verify")
def gate_otp_verify(vid: str, channel: str, body: dict, v: dict = Depends(require_flow)):
    code = body.get("code") or ""
    return otp_verify(vid, OtpVerify(channel=channel, code=code), v)


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


# ==================== INTERVIEWS (Meeting Overlay) ====================

def _extract_audio_if_needed(video_path: Path, audio_path: Optional[Path]) -> Optional[Path]:
    if audio_path and audio_path.exists() and audio_path.stat().st_size > 0:
        return audio_path
    if not shutil.which("ffmpeg") or not video_path.exists():
        return None
    out_audio = video_path.with_suffix(".wav")
    try:
        import subprocess
        cmd = ["ffmpeg", "-y", "-i", str(video_path), "-vn", "-ac", "1", "-ar", "16000", str(out_audio)]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=15)
        if out_audio.exists() and out_audio.stat().st_size > 0:
            return out_audio
    except Exception:
        pass
    return None


def _authenticate_interview(
    id: str,
    x_interview_token: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None)
) -> dict:
    iv = db.get_interview(id)
    if not iv:
        raise HTTPException(404, "Interview session not found")
    if x_interview_token:
        import hmac
        if not hmac.compare_digest(iv["token_hash"], hash_key(x_interview_token)):
            raise HTTPException(401, "Invalid interview session token")
        if iv["expires_at"] < time.time():
            raise HTTPException(410, "Interview session expired")
        return iv
    if authorization and authorization.lower().startswith("bearer "):
        tenant = db.tenant_by_api_key(authorization.split(" ", 1)[1].strip())
        if tenant and tenant["id"] == iv["tenant_id"]:
            return iv
    raise HTTPException(401, "Missing or invalid authorization credentials")


@app.post("/v1/interviews")
def create_interview_session(body: CreateInterview, tenant: dict = Depends(require_tenant)):
    """Create a new interview verification session for an interviewer."""
    raw_token = new_token()
    token_hash = hash_key(raw_token)
    ttl_s = (body.ttl_hours or 24) * 3600
    iv = db.create_interview(
        tenant_id=tenant["id"],
        candidate_id=body.candidate_id,
        token_hash=token_hash,
        ttl_s=ttl_s,
        metadata=body.metadata
    )
    if body.candidate_id:
        kyc_face = db.get_candidate_kyc_face(tenant["id"], body.candidate_id)
        if kyc_face:
            db.update_interview(iv["id"], face_baseline=kyc_face)
    return {
        "id": iv["id"],
        "token": raw_token,
        "expires_at": iv["expires_at"],
        "candidate_id": iv["candidate_id"]
    }


@app.post("/v1/interviews/{id}/clips")
async def upload_interview_clip(
    id: str,
    video: UploadFile = File(...),
    audio: Optional[UploadFile] = File(default=None),
    round: int = Form(default=1),
    meeting_app: Optional[str] = Form(default=None),
    resolution: Optional[str] = Form(default=None),
    fps: Optional[float] = Form(default=None),
    timestamp: Optional[float] = Form(default=None),
    iv: dict = Depends(_authenticate_interview)
):
    """Upload interview video + audio clip chunk (25s) and evaluate all checks."""
    s = get_settings()
    if iv["status"] == "completed":
        raise HTTPException(400, "Interview session has already been completed")

    clip_dir = s.data_dir / "interviews" / id
    clip_dir.mkdir(parents=True, exist_ok=True)

    ts_slug = int(timestamp or time.time())
    v_ext = Path(video.filename or "clip.webm").suffix or ".webm"
    video_path = clip_dir / f"round_{round}_{ts_slug}_video{v_ext}"

    v_bytes = await video.read()
    video_path.write_bytes(v_bytes)

    audio_path = None
    if audio:
        a_ext = Path(audio.filename or "clip.wav").suffix or ".wav"
        raw_audio_path = clip_dir / f"round_{round}_{ts_slug}_audio{a_ext}"
        a_bytes = await audio.read()
        if len(a_bytes) > 0:
            raw_audio_path.write_bytes(a_bytes)
            wav_path = clip_dir / f"round_{round}_{ts_slug}_audio.wav"
            try:
                import subprocess
                cmd = ["ffmpeg", "-y", "-i", str(raw_audio_path), "-vn", "-ac", "1", "-ar", "16000", str(wav_path)]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
                if wav_path.exists() and wav_path.stat().st_size > 0:
                    audio_path = wav_path
                else:
                    audio_path = raw_audio_path
            except Exception:
                audio_path = raw_audio_path

    if not audio_path or not audio_path.exists() or audio_path.stat().st_size == 0:
        audio_path = _extract_audio_if_needed(video_path, None)

    metadata = {
        "round": round,
        "meeting_app": meeting_app,
        "resolution": resolution,
        "fps": fps,
        "timestamp": timestamp or time.time(),
        "video_file": video_path.name,
        "audio_file": audio_path.name if audio_path else None
    }

    clip = db.create_interview_clip(
        interview_id=id,
        round_num=round,
        metadata=metadata,
        video_path=str(video_path),
        audio_path=str(audio_path) if audio_path else ""
    )

    from .checks.interview_evaluator import evaluate_interview_clip
    results, recommendation, action, new_face_baseline, new_speaker_id = evaluate_interview_clip(
        video_path=video_path,
        audio_path=audio_path,
        interview_id=id,
        round_num=round,
        face_baseline=iv.get("face_baseline"),
        speaker_id=iv.get("speaker_id"),
        settings=s
    )

    updates = {}
    if new_face_baseline and new_face_baseline != iv.get("face_baseline"):
        updates["face_baseline"] = new_face_baseline
    if new_speaker_id and new_speaker_id != iv.get("speaker_id"):
        updates["speaker_id"] = new_speaker_id
    if updates:
        db.update_interview(id, **updates)

    res_dicts = [r.to_dict() for r in results]
    db.update_interview_clip(
        clip["id"],
        status="completed",
        results=res_dicts,
        recommendation=recommendation,
        action=action
    )

    return {
        "clip_id": clip["id"],
        "interview_id": id,
        "round": round,
        "status": "completed",
        "checks": res_dicts,
        "overall_recommendation": recommendation,
        "interviewer_action": action,
        "created_at": clip["created_at"]
    }


@app.get("/v1/interviews/{id}/clips/{clip_id}")
def get_interview_clip_result(id: str, clip_id: str, iv: dict = Depends(_authenticate_interview)):
    """Fetch results of a specific interview clip."""
    clip = db.get_interview_clip(clip_id)
    if not clip or clip["interview_id"] != id:
        raise HTTPException(404, "Clip not found")
    return {
        "clip_id": clip["id"],
        "interview_id": id,
        "round": clip["round"],
        "status": clip["status"],
        "checks": clip.get("results", []),
        "overall_recommendation": clip.get("recommendation", "unavailable"),
        "interviewer_action": clip.get("action", ""),
        "metadata": clip.get("metadata", {}),
        "created_at": clip["created_at"]
    }


@app.get("/v1/interviews/{id}/summary")
def get_interview_summary(id: str, iv: dict = Depends(_authenticate_interview)):
    """Aggregate all clips into a timeline and overall session summary."""
    clips = db.list_interview_clips(id)
    total_clips = len(clips)

    clear_count = sum(1 for c in clips if c.get("recommendation") == "clear")
    caution_count = sum(1 for c in clips if c.get("recommendation") == "caution")
    flagged_count = sum(1 for c in clips if c.get("recommendation") == "flagged")

    overall_rec = "clear"
    suggested_action = "All signals across interview rounds consistent. Continue normally."

    if flagged_count > 0:
        overall_rec = "flagged"
        for c in reversed(clips):
            if c.get("recommendation") == "flagged":
                suggested_action = c.get("action")
                break
    elif caution_count > 0:
        overall_rec = "caution"
        for c in reversed(clips):
            if c.get("recommendation") == "caution":
                suggested_action = c.get("action")
                break
    elif total_clips == 0:
        overall_rec = "unavailable"
        suggested_action = "No clips recorded yet. Start monitoring in overlay."

    timeline = [
        {
            "clip_id": c["id"],
            "round": c["round"],
            "timestamp": c.get("metadata", {}).get("timestamp", c["created_at"]),
            "recommendation": c.get("recommendation", "unknown"),
            "action": c.get("action", ""),
            "checks": c.get("results", [])
        }
        for c in clips
    ]

    return {
        "interview_id": id,
        "candidate_id": iv.get("candidate_id"),
        "status": iv["status"],
        "total_clips": total_clips,
        "clear_count": clear_count,
        "caution_count": caution_count,
        "flagged_count": flagged_count,
        "overall_recommendation": overall_rec,
        "suggested_action": suggested_action,
        "timeline": timeline,
        "created_at": iv["created_at"],
        "expires_at": iv["expires_at"]
    }


@app.post("/v1/interviews/{id}/end")
def end_interview_session(id: str, iv: dict = Depends(_authenticate_interview)):
    """Finalize an interview session."""
    db.update_interview(id, status="completed")
    return {"id": id, "status": "completed"}

