import base64
import hashlib
import hmac
import os
import secrets
import time
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet
from fastapi import Depends, Header, HTTPException

from . import db
from .config import get_settings


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(32)


# ---------- Encryption at rest (Fernet authenticated AES-128-CBC) ----------
_fernet_instance: Optional[Fernet] = None


def get_cipher() -> Fernet:
    global _fernet_instance
    if _fernet_instance is not None:
        return _fernet_instance

    key = os.environ.get("KYC_ENCRYPTION_KEY")
    if key:
        try:
            _fernet_instance = Fernet(key.encode() if isinstance(key, str) else key)
            return _fernet_instance
        except Exception:
            pass

    # Fallback to key file in data dir or stable derive
    key_file = get_settings().data_dir / ".encryption_key"
    try:
        if key_file.exists():
            k = key_file.read_bytes().strip()
            _fernet_instance = Fernet(k)
            return _fernet_instance
        key_file.parent.mkdir(parents=True, exist_ok=True)
        k = Fernet.generate_key()
        key_file.write_bytes(k)
        _fernet_instance = Fernet(k)
        return _fernet_instance
    except Exception:
        # In-memory fallback (e.g. read-only tmp)
        derived = base64.urlsafe_b64encode(hashlib.sha256(b"unclone-kyc-default-dev-seed").digest())
        _fernet_instance = Fernet(derived)
        return _fernet_instance


def encrypt_bytes(data: bytes) -> bytes:
    return get_cipher().encrypt(data)


def decrypt_bytes(token: bytes) -> bytes:
    return get_cipher().decrypt(token)


# ---------- Signed evidence URLs ----------
def sign_evidence_token(vid: str, kind: str, expires_in_s: int = 3600) -> str:
    """Issue a signed expiring token for downloading uploaded evidence."""
    expires_at = int(time.time() + expires_in_s)
    msg = f"{vid}:{kind}:{expires_at}".encode()
    mac = hmac.new(get_cipher()._signing_key, msg, hashlib.sha256).hexdigest()
    raw = f"{expires_at}:{mac}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def verify_evidence_token(vid: str, kind: str, token_str: str) -> bool:
    """Verify an expiring evidence access token."""
    try:
        raw = base64.urlsafe_b64decode(token_str.encode()).decode()
        expires_at_str, mac = raw.split(":", 1)
        expires_at = int(expires_at_str)
        if time.time() > expires_at:
            return False
        msg = f"{vid}:{kind}:{expires_at}".encode()
        expected = hmac.new(get_cipher()._signing_key, msg, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, mac)
    except Exception:
        return False


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


def require_product(product: str):
    """Dependency factory ensuring tenant has access to the requested product."""
    def dep(tenant: dict = Depends(require_tenant)) -> dict:
        prods = tenant.get("products") or []
        if product not in prods:
            raise HTTPException(403, f"Tenant does not have access to '{product}' product. Enabled products: {prods}")
        return tenant
    return dep


def require_scope(scope: str):
    """Dependency factory ensuring tenant's API key has the required scope."""
    def dep(tenant: dict = Depends(require_tenant)) -> dict:
        scopes = tenant.get("key_scopes") or []
        has_scope = False
        for s in scopes:
            if s == "*" or s == "admin:*":
                has_scope = True
                break
            if s == scope:
                has_scope = True
                break
            if s.endswith(":*") and scope.startswith(s[:-1]):
                has_scope = True
                break
            if scope.endswith(":*") and s.startswith(scope[:-1]):
                has_scope = True
                break
        if not has_scope:
            raise HTTPException(403, f"API key lacks required scope '{scope}'. Key scopes: {scopes}")
        return tenant
    return dep


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


def require_interview(interview_id: str, x_interview_token: Optional[str] = Header(default=None)) -> dict:
    """Interviewer desktop overlay auth: per-session token issued on session creation."""
    iv = db.get_interview(interview_id)
    if not iv or not x_interview_token:
        raise HTTPException(404, "Interview session not found")
    if not hmac.compare_digest(iv["token_hash"], hash_key(x_interview_token)):
        raise HTTPException(401, "Invalid interview session token")
    if iv["expires_at"] < time.time():
        raise HTTPException(410, "Interview session expired")
    return iv

