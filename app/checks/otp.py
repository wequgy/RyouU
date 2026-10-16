"""OTP service (email / phone) plus the checks that read its outcome.

Codes: 6 digits from `secrets`, stored only as salted hashes, single use, expiring, attempt-limited,
send-limited per session. The user types the code into the page. NEVER ask people to read OTPs aloud.
"""
import hashlib
import hmac
import secrets
import smtplib
import time
from email.message import EmailMessage

from .. import db
from ..config import get_settings
from ..models import CheckContext, CheckResult
from .base import register


class OtpError(Exception):
    pass


def _hash(vid: str, channel: str, code: str, salt: str) -> str:
    return salt + "$" + hashlib.sha256(f"{salt}:{vid}:{channel}:{code}".encode()).hexdigest()


def mask(dest: str) -> str:
    if "@" in dest:
        user, host = dest.split("@", 1)
        return f"{user[:1]}***@{host}"
    return "*" * max(len(dest) - 4, 0) + dest[-4:]


class ConsoleSender:
    """Mock sender: prints the code to the server log. Use for demos and tests."""
    def send(self, channel: str, destination: str, code: str) -> None:
        print(f"[otp:{channel}] code for {destination}: {code}", flush=True)


class SMTPSender:
    def send(self, channel: str, destination: str, code: str) -> None:
        s = get_settings()
        msg = EmailMessage()
        msg["Subject"], msg["From"], msg["To"] = "Your verification code", s.smtp_from or s.smtp_user, destination
        msg.set_content(f"Your verification code is {code}. It expires in {s.otp_ttl_s // 60} minutes.")
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
            smtp.starttls()
            if s.smtp_user:
                smtp.login(s.smtp_user, s.smtp_pass)
            smtp.send_message(msg)


def get_sender(channel: str):
    s = get_settings()
    if channel == "email" and s.smtp_host:
        return SMTPSender()
    return ConsoleSender()  # phone: plug a real SMS provider here (India needs DLT registration)


def issue(vid: str, channel: str, destination: str) -> dict:
    s = get_settings()
    if channel not in ("email", "phone"):
        raise OtpError("channel must be 'email' or 'phone'")
    if db.otp_count(vid, channel) >= s.otp_max_sends:
        raise OtpError("Too many codes requested for this session")
    code = f"{secrets.randbelow(10**6):06d}"
    db.otp_insert(vid, channel, destination, _hash(vid, channel, code, secrets.token_hex(8)),
                  time.time() + s.otp_ttl_s)
    get_sender(channel).send(channel, destination, code)
    out = {"sent": True, "destination": mask(destination), "expires_in_s": s.otp_ttl_s}
    if s.dev_mode:
        out["dev_code"] = code  # DEV ONLY
    return out


def verify(vid: str, channel: str, code: str) -> bool:
    s = get_settings()
    row = db.otp_latest(vid, channel)
    if not row or row["used"] or row["expires_at"] < time.time() or row["attempts"] >= s.otp_max_attempts:
        return False
    db.otp_bump_attempts(row["id"])
    salt = row["code_hash"].split("$", 1)[0]
    if not hmac.compare_digest(row["code_hash"], _hash(vid, channel, code.strip(), salt)):
        return False
    db.otp_mark_used(row["id"])
    dest = row["destination"]

    def mut(d):
        d.setdefault("verified", {})[channel] = dest
    db.update_data(vid, mut)
    return True


def _otp_check(channel: str):
    name = f"{channel}_otp"

    def check(ctx: CheckContext) -> CheckResult:
        verified = ctx.data.get("verified", {}).get(channel)
        if verified:
            return CheckResult.passed(name, f"{channel} verified ({mask(verified)})", confidence=0.9)
        row = db.otp_latest(ctx.session_id, channel)
        if row and row["attempts"] >= ctx.settings.otp_max_attempts:
            return CheckResult.failed(name, f"Too many wrong {channel} codes", confidence=0.7)
        return CheckResult.skipped(name, f"{channel} not verified")
    return check


register("email_otp")(_otp_check("email"))
register("phone_otp")(_otp_check("phone"))
