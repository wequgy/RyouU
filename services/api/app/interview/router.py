"""Interview integrity router: session creation, token minting, clips, and timeline."""
import hmac
from pathlib import Path
import shutil
import time
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile

from app import db
from app.config import get_settings
from app.models import CreateInterview
from app.security import (
    hash_key,
    new_token,
    require_product,
    require_scope,
    require_tenant,
)

router = APIRouter(tags=["interview"])


def require_interview_tenant(
    tenant: dict = Depends(require_tenant),
    _prod: dict = Depends(require_product("interview")),
    _scope: dict = Depends(require_scope("interview:*")),
) -> dict:
    if not db.check_rate_limit(f"rate:tenant:{tenant['id']}", limit=120, window_s=60):
        raise HTTPException(429, "Tenant rate limit exceeded")
    return tenant


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
    authorization: Optional[str] = Header(default=None),
) -> dict:
    iv = db.get_interview(id)
    if not iv:
        raise HTTPException(404, "Interview session not found")
    if x_interview_token:
        if not hmac.compare_digest(iv["token_hash"], hash_key(x_interview_token)):
            raise HTTPException(401, "Invalid interview session token")
        if iv["expires_at"] < time.time():
            raise HTTPException(410, "Interview session expired")
        return iv
    if authorization and authorization.lower().startswith("bearer "):
        tenant = db.tenant_by_api_key(authorization.split(" ", 1)[1].strip())
        if tenant and tenant["id"] == iv["tenant_id"]:
            # Check tenant product permission
            prods = tenant.get("products") or []
            if "interview" not in prods:
                raise HTTPException(403, f"Tenant does not have access to 'interview' product. Enabled products: {prods}")
            return iv
    raise HTTPException(401, "Missing or invalid authorization credentials")


@router.post("/v1/interviews")
def create_interview_session(body: CreateInterview, tenant: dict = Depends(require_interview_tenant)):
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


@router.post("/v1/interviews/{id}/token")
def mint_interviewer_token(id: str, tenant: dict = Depends(require_interview_tenant)):
    """Mint a short-lived scoped interviewer token for desktop overlay (tenant authorization only)."""
    iv = db.get_interview(id)
    if not iv or iv["tenant_id"] != tenant["id"]:
        raise HTTPException(404, "Interview session not found")
    if iv["status"] == "completed":
        raise HTTPException(400, "Interview session has already completed")
    raw_token = new_token()
    token_hash = hash_key(raw_token)
    new_expires_at = time.time() + 3600  # 1 hour short-lived
    db.update_interview(id, token_hash=token_hash, expires_at=new_expires_at)
    return {
        "interview_id": id,
        "token": raw_token,
        "expires_at": new_expires_at,
        "candidate_id": iv["candidate_id"]
    }


@router.post("/v1/interviews/{id}/refresh")
def refresh_interviewer_token(id: str, iv: dict = Depends(_authenticate_interview)):
    """Refresh a short-lived interviewer token before expiry using the current active token."""
    if iv["status"] == "completed":
        raise HTTPException(400, "Interview session has already completed")
    raw_token = new_token()
    token_hash = hash_key(raw_token)
    new_expires_at = time.time() + 3600  # 1 hour extension
    db.update_interview(id, token_hash=token_hash, expires_at=new_expires_at)
    return {
        "interview_id": id,
        "token": raw_token,
        "expires_at": new_expires_at,
        "candidate_id": iv["candidate_id"]
    }


@router.post("/v1/interviews/{id}/clips")
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

    from app.checks.interview_evaluator import evaluate_interview_clip
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


@router.get("/v1/interviews/{id}/clips/{clip_id}")
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


@router.get("/v1/interviews/{id}/summary")
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

    has_baseline = bool(iv.get("face_baseline"))
    kyc_baseline_status = "verified" if has_baseline else "No KYC baseline"

    return {
        "interview_id": id,
        "candidate_id": iv.get("candidate_id"),
        "status": iv["status"],
        "kyc_baseline_status": kyc_baseline_status,
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


@router.post("/v1/interviews/{id}/end")
def end_interview_session(id: str, iv: dict = Depends(_authenticate_interview)):
    """Finalize an interview session."""
    db.update_interview(id, status="completed")
    return {"id": id, "status": "completed"}
