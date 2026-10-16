import hashlib
import hmac
import secrets
import time
from typing import Optional

from fastapi import Header, HTTPException

from . import db
from .config import get_settings


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(32)


# ---------- Webhook signing (Stripe-style: t=<ts>,v1=<hex hmac of "<ts>.<body>">) ----------
def sign_payload(secret: str, body: bytes, ts: Optional[int] = None) -> str:
    ts = int(time.time()) if ts is None else int(ts)
    mac = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={ts},v1={mac}"


def verify_signature(secret: str, body: bytes, header: str, tolerance_s: int = 300,
                     now: Optional[float] = None) -> bool:
    """Used by the CUSTOMER's server to verify our webhooks. Rejects tampering and replays."""
    try:
        parts = dict(p.split("=", 1) for p in header.split(","))
        ts = int(parts["t"])
        given = parts["v1"]
    except (KeyError, ValueError):
        return False
    now = time.time() if now is None else now
    if abs(now - ts) > tolerance_s:
        return False
    expected = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, given)


# ---------- FastAPI dependencies ----------
def require_tenant(authorization: Optional[str] = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing bearer API key")
    tenant = db.tenant_by_api_key(authorization.split(" ", 1)[1].strip())
    if not tenant:
        raise HTTPException(401, "Invalid API key")
    return tenant


def require_flow(vid: str, x_flow_token: Optional[str] = Header(default=None)) -> dict:
    """End-user auth for the hosted flow: a per-session token that is only in the flow URL."""
    v = db.get_verification(vid)
    if not v or not x_flow_token:
        raise HTTPException(404, "Verification not found")
    if not hmac.compare_digest(v["flow_token_hash"], hash_key(x_flow_token)):
        raise HTTPException(404, "Verification not found")
    if v["expires_at"] < time.time():
        raise HTTPException(410, "Verification link expired")
    return v
