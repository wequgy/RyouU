"""KYC verification service API.

Customer (tenant) API:  /v1/...   auth: Authorization: Bearer <api key>
End-user flow API:      /flow/... auth: X-Flow-Token header (token is in the flow URL)
"""
import re
import secrets
import shutil
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

app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


def require_tenant_with_rate_limit(tenant: dict = Depends(require_tenant)) -> dict:
    if not db.check_rate_limit(f"rate:tenant:{tenant['id']}", limit=120, window_s=60):
        raise HTTPException(429, "Tenant rate limit exceeded")
    return tenant


@app.get("/healthz")
def healthz():
    return {"ok": True, "time": time.time()}


@app.get("/flow", response_class=HTMLResponse, include_in_schema=False)
def flow_page():
    """Serve the hosted KYC verification UI. The flow URL opens this page in a WebView."""
    if not _FLOW_HTML.exists():
        raise HTTPException(404, "Flow page not found. Run setup or check app/static/flow.html.")
    return HTMLResponse(_FLOW_HTML.read_text(encoding="utf-8"))


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


@app.get("/flow/{vid}/context")
def flow_context(vid: str, v: dict = Depends(require_flow)):
    tenant = db.tenant_by_id(v["tenant_id"])
    policy = get_policy(v["policy"])
    return {"id": v["id"], "status": v["status"], "customer": tenant["name"], "policy": policy["name"],
            "steps": steps_for(policy), "expires_at": v["expires_at"],
            "uploaded": sorted(v["data"].get("files", {})), "verified": sorted(v["data"].get("verified", {}))}


@app.post("/flow/{vid}/otp/send")
def otp_send(vid: str, body: OtpSend, v: dict = Depends(require_flow)):
    _editable(v)
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
async def upload(vid: str, kind: str, file: UploadFile = File(...), v: dict = Depends(require_flow)):
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
    folder = s.data_dir / "uploads" / vid           # filename is server-chosen: no path traversal
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / f"{kind}{ext}"
    dest.write_bytes(encrypt_bytes(blob))

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
    return {"challenges": challenges.issue(vid), "ttl_s": get_settings().challenge_ttl_s}


@app.post("/flow/{vid}/challenges/result")
def challenge_result(vid: str, body: ChallengeResults, v: dict = Depends(require_flow)):
    _editable(v)
    out = challenges.record_results(vid, [r.model_dump() for r in body.results])
    if out["rejected"]:
        raise HTTPException(400, f"Unknown or already-answered challenge ids: {out['rejected']}")
    return {"stored": len(body.results)}


@app.post("/flow/{vid}/transcripts")
def dev_transcripts(vid: str, body: dict, v: dict = Depends(require_flow)):
    """DEV ONLY: supply spoken transcripts without running Whisper. A client-supplied transcript
    would let an attacker type the 'spoken' answers, so this is disabled outside dev mode."""
    if not get_settings().dev_mode:
        raise HTTPException(403, "Disabled outside dev mode")
    _editable(v)
    clean = {k: str(t)[:500] for k, t in body.items() if k in TRANSCRIPT_KEYS}

    def mut(d):
        d.setdefault("spoken_transcripts", {}).update(clean)
    db.update_data(vid, mut)
    return {"stored": sorted(clean)}


@app.post("/flow/{vid}/submit", status_code=202)
def submit(vid: str, bg: BackgroundTasks, v: dict = Depends(require_flow)):
    if not db.claim_for_processing(vid):
        raise HTTPException(409, f"Verification is '{v['status']}' and cannot be submitted")
    job_id = db.enqueue_pipeline_job(vid, v["tenant_id"])
    bg.add_task(pipeline.process, vid, job_id=job_id)
    return {"status": "processing", "id": vid, "job_id": job_id}
