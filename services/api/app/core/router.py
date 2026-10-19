"""Core system router: health, readiness, tenant management, and scoped API keys."""
import secrets
import time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app import db
from app.config import get_settings
from app.readiness import check_system_readiness
from app.security import require_tenant

router = APIRouter(tags=["core"])


class WebhookUpdateBody(BaseModel):
    webhook_url: str


class CreateApiKeyBody(BaseModel):
    scopes: List[str] = Field(default_factory=lambda: ["kyc:*"])
    expires_in_s: Optional[float] = None


def require_tenant_with_rate_limit(tenant: dict = Depends(require_tenant)) -> dict:
    if not db.check_rate_limit(f"rate:tenant:{tenant['id']}", limit=120, window_s=60):
        raise HTTPException(429, "Tenant rate limit exceeded")
    return tenant


@router.get("/healthz")
def healthz():
    return {"ok": True, "time": time.time()}


@router.get("/readyz")
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


@router.post("/v1/tenant/rotate-key")
def rotate_api_key(tenant: dict = Depends(require_tenant_with_rate_limit)):
    new_key = "kyc_live_" + secrets.token_urlsafe(32)
    db.rotate_tenant_api_key(tenant["id"], new_key)
    return {"api_key": new_key, "message": "Store this key now. It cannot be shown again."}


@router.post("/v1/tenant/rotate-webhook-secret")
def rotate_webhook_secret(tenant: dict = Depends(require_tenant_with_rate_limit)):
    new_secret = "whsec_" + secrets.token_urlsafe(32)
    db.rotate_tenant_webhook_secret(tenant["id"], new_secret)
    return {"webhook_secret": new_secret}


@router.patch("/v1/tenant/webhook")
def update_webhook(body: WebhookUpdateBody, tenant: dict = Depends(require_tenant_with_rate_limit)):
    db.update_tenant_webhook_url(tenant["id"], body.webhook_url)
    return {"webhook_url": body.webhook_url}


@router.post("/v1/tenant/keys", status_code=201)
def create_tenant_api_key(body: CreateApiKeyBody, tenant: dict = Depends(require_tenant_with_rate_limit)):
    raw_key, meta = db.create_api_key(tenant["id"], body.scopes, body.expires_in_s)
    return {
        "key_id": meta["id"],
        "api_key": raw_key,
        "scopes": meta["scopes"],
        "expires_at": meta["expires_at"],
        "message": "Store this key now. It cannot be shown again."
    }


@router.get("/v1/tenant/keys")
def list_tenant_api_keys(tenant: dict = Depends(require_tenant_with_rate_limit)):
    return {"data": db.list_api_keys(tenant["id"])}


@router.post("/v1/tenant/keys/{key_id}/revoke")
def revoke_tenant_api_key(key_id: str, tenant: dict = Depends(require_tenant_with_rate_limit)):
    ok = db.revoke_api_key(tenant["id"], key_id)
    if not ok:
        raise HTTPException(404, "API key not found or already revoked")
    return {"revoked": True, "key_id": key_id}
