"""Session authentication, Argon2 password hashing, and CSRF protection for compliance dashboard."""
import hmac
import os
import secrets
import time
from typing import Dict, Any, Optional

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel

ph = PasswordHasher()

# Active in-memory session store: session_id -> session_dict
# session_dict: { "username": str, "role": str, "csrf_token": str, "expires_at": float }
_SESSIONS: Dict[str, Dict[str, Any]] = {}
_LOGIN_ATTEMPTS: Dict[str, list] = {}

DASHBOARD_USERNAME = os.environ.get("DASHBOARD_USERNAME", "reviewer")
# Default password hashed with Argon2 at module load
_DEFAULT_PASS = os.environ.get("DASHBOARD_PASSWORD", "reviewer_kyc_2026")
DASHBOARD_PASSWORD_HASH = os.environ.get(
    "DASHBOARD_PASSWORD_HASH",
    ph.hash(_DEFAULT_PASS)
)

SESSION_COOKIE_NAME = "kyc_session"
SESSION_TTL_S = 3600  # 1 hour short-lived session

router = APIRouter(prefix="/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


def _check_rate_limit(client_ip: str, max_attempts: int = 5, window_s: int = 60) -> bool:
    now = time.time()
    attempts = _LOGIN_ATTEMPTS.setdefault(client_ip, [])
    # Filter attempts within window
    _LOGIN_ATTEMPTS[client_ip] = [t for t in attempts if now - t < window_s]
    if len(_LOGIN_ATTEMPTS[client_ip]) >= max_attempts:
        return False
    _LOGIN_ATTEMPTS[client_ip].append(now)
    return True


def create_session(username: str, role: str = "reviewer") -> tuple[str, str]:
    session_id = secrets.token_urlsafe(32)
    csrf_token = secrets.token_hex(32)
    now = time.time()
    _SESSIONS[session_id] = {
        "username": username,
        "role": role,
        "csrf_token": csrf_token,
        "expires_at": now + SESSION_TTL_S,
        "created_at": now,
    }
    return session_id, csrf_token


def get_session(session_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not session_id or session_id not in _SESSIONS:
        return None
    sess = _SESSIONS[session_id]
    if time.time() > sess["expires_at"]:
        _SESSIONS.pop(session_id, None)
        return None
    return sess


def verify_csrf(request: Request, session: Dict[str, Any]):
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        token_hdr = request.headers.get("X-CSRF-Token") or request.headers.get("x-csrf-token")
        if not token_hdr or not hmac.compare_digest(token_hdr, session["csrf_token"]):
            raise HTTPException(403, "CSRF token missing or invalid")


@router.post("/login")
def login(req: LoginRequest, request: Request, response: Response):
    client_ip = request.client.host if request.client else "127.0.0.1"
    if not _check_rate_limit(client_ip):
        raise HTTPException(429, "Rate limit exceeded on login attempts. Please wait 60 seconds.")

    valid = False
    if req.username == DASHBOARD_USERNAME:
        try:
            valid = ph.verify(DASHBOARD_PASSWORD_HASH, req.password)
        except VerifyMismatchError:
            valid = False
        except Exception:
            valid = False

    if not valid:
        raise HTTPException(401, "Invalid username or password")

    session_id, csrf_token = create_session(req.username, role="reviewer")
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        max_age=SESSION_TTL_S,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/",
    )
    return {
        "ok": True,
        "username": req.username,
        "role": "reviewer",
        "csrf_token": csrf_token,
        "expires_in_s": SESSION_TTL_S,
    }


@router.post("/logout")
def logout(response: Response, session_id: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE_NAME)):
    if session_id:
        _SESSIONS.pop(session_id, None)
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
def me(request: Request, session_id: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE_NAME)):
    sess = get_session(session_id)
    if not sess:
        raise HTTPException(401, "Unauthenticated session")
    return {
        "ok": True,
        "username": sess["username"],
        "role": sess["role"],
        "csrf_token": sess["csrf_token"],
    }
