"""OTP service (email / phone) plus the checks that read its outcome.

Codes: 6 digits from `secrets`, stored only as salted hashes, single use, expiring, attempt-limited,
send-limited per session. The user types the code into the page. NEVER ask people to read OTPs aloud.
"""
import hashlib
import hmac
import os
import secrets
import smtplib
import time
from abc import ABC, abstractmethod
from email.message import EmailMessage
from typing import Optional

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
        sender_email = s.smtp_from or s.smtp_user
        msg["Subject"] = "Your KYC Verification Code"
        msg["From"] = f"UnClone Identity Verification <{sender_email}>"
        msg["To"] = destination
        msg.set_content(
            f"Hello,\n\n"
            f"Your one-time security verification code for KYC Identity Verification is:\n\n"
            f"    {code}\n\n"
            f"This code will expire in {s.otp_ttl_s // 60} minutes.\n"
            f"If you did not request this verification, please ignore this email.\n\n"
            f"— UnClone KYC Security Team"
        )
        try:
            with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
                smtp.starttls()
                if s.smtp_user and s.smtp_pass:
                    smtp.login(s.smtp_user, s.smtp_pass)
                smtp.send_message(msg)
                print(f"[otp:email] Real email delivered to {destination} via {s.smtp_host}", flush=True)
        except Exception as e:
            print(f"[otp:email] SMTP delivery error: {e}", flush=True)
            raise OtpError(f"Email delivery failed: {e}")


# ---------- Pluggable SMS Provider Interface ----------
class SmsProvider(ABC):
    @abstractmethod
    def send_sms(self, destination: str, code: str, recipient: Optional[str] = None) -> dict:
        """Send an SMS OTP. Returns a dict e.g. {'via': 'sms'} or {'via': 'email_bridge'}."""
        pass


class MockSmsProvider(SmsProvider):
    def __init__(self):
        self.sent_messages = []

    def send_sms(self, destination: str, code: str, recipient: Optional[str] = None) -> dict:
        self.sent_messages.append({"destination": destination, "code": code})
        print(f"[otp:mock_sms] Mock SMS dispatched to {destination}: {code}", flush=True)
        return {"via": "sms"}


class TwilioSmsProvider(SmsProvider):
    def send_sms(self, destination: str, code: str, recipient: Optional[str] = None) -> dict:
        s = get_settings()
        import base64
        import urllib.parse
        import urllib.request
        url = f"https://api.twilio.com/2010-04-01/Accounts/{s.twilio_account_sid}/Messages.json"
        data = urllib.parse.urlencode({
            "To": destination,
            "From": s.twilio_from_number,
            "Body": f"Your KYC verification code is {code}. Valid for 5 minutes."
        }).encode("utf-8")
        auth = base64.b64encode(f"{s.twilio_account_sid}:{s.twilio_auth_token}".encode()).decode()
        req = urllib.request.Request(url, data=data, headers={"Authorization": f"Basic {auth}"})
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                print(f"[otp:sms] Twilio SMS dispatched to {destination}: status {resp.status}", flush=True)
                return {"via": "sms"}
        except Exception as e:
            print(f"[otp:sms] Twilio SMS error: {e}", flush=True)
            raise OtpError(f"SMS delivery failed via Twilio: {e}")


class Fast2SmsProvider(SmsProvider):
    def send_sms(self, destination: str, code: str, recipient: Optional[str] = None) -> dict:
        s = get_settings()
        import json as _json
        import urllib.request
        clean_num = "".join(filter(str.isdigit, destination))[-10:]
        if len(clean_num) != 10:
            clean_num = destination

        url = (f"https://www.fast2sms.com/dev/bulkV2?authorization={s.fast2sms_api_key}"
               f"&route=q&message=Your+KYC+verification+code+is+{code}.+Valid+for+5+minutes."
               f"&language=english&flash=0&numbers={clean_num}")
        req = urllib.request.Request(url, headers={"cache-control": "no-cache"})
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                body = _json.loads(resp.read())
                if body.get("return"):
                    print(f"[otp:sms] Real Fast2SMS dispatched to {clean_num}", flush=True)
                    return {"via": "sms"}
                raise OtpError(f"Fast2SMS error: {body.get('message', body)}")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()
            print(f"[otp:sms] Fast2SMS HTTP {e.code}: {err_body}", flush=True)
            print(f"[otp:sms] Fast2SMS requires prepaid recharge. Auto-routing phone OTP to {recipient or s.smtp_user}...", flush=True)
            EmailBridgeSmsProvider().send_sms(destination, code, recipient=recipient)
            return {"via": "email_bridge", "reason": "Fast2SMS requires prepaid recharge", "email": recipient or s.smtp_user}
        except Exception as e:
            print(f"[otp:sms] Fast2SMS error ({e}). Auto-routing phone OTP to {recipient or s.smtp_user}...", flush=True)
            EmailBridgeSmsProvider().send_sms(destination, code, recipient=recipient)
            return {"via": "email_bridge", "reason": str(e), "email": recipient or s.smtp_user}


class EmailBridgeSmsProvider(SmsProvider):
    """Delivers the phone OTP via email when no SMS gateway is configured/working."""
    def send_sms(self, destination: str, code: str, recipient: Optional[str] = None) -> dict:
        s = get_settings()
        to_email = recipient or s.smtp_user
        if not (s.smtp_host and s.smtp_user and s.smtp_pass):
            print(f"[otp:phone] (Console fallback) Phone OTP for {destination}: {code}", flush=True)
            return {"via": "email_bridge", "email": to_email}

        msg = EmailMessage()
        sender_email = s.smtp_from or s.smtp_user
        msg["Subject"] = f"Phone Verification Code: {code}"
        msg["From"] = f"UnClone Identity Verification <{sender_email}>"
        msg["To"] = to_email
        msg.set_content(
            f"KYC Phone Number Verification\n\n"
            f"A verification code was requested for mobile number: {destination}\n\n"
            f"Your 6-digit phone OTP code is:\n\n"
            f"    {code}\n\n"
            f"This code expires in {s.otp_ttl_s // 60} minutes.\n"
            f"Enter this code in the 'Verify your phone' step.\n\n"
            f"— UnClone KYC Security Team"
        )
        try:
            with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
                smtp.starttls()
                smtp.login(s.smtp_user, s.smtp_pass)
                smtp.send_message(msg)
                print(f"[otp:phone] Phone OTP {code} delivered to {to_email} for mobile number {destination}", flush=True)
        except Exception as e:
            print(f"[otp:phone] Email bridge error: {e}", flush=True)
            print(f"[otp:phone] Code is: {code}", flush=True)
        return {"via": "email_bridge", "email": to_email}


# Pluggable global provider
_custom_sms_provider: Optional[SmsProvider] = None


def set_sms_provider(provider: Optional[SmsProvider]) -> None:
    global _custom_sms_provider
    _custom_sms_provider = provider


def get_sms_provider() -> SmsProvider:
    global _custom_sms_provider
    if _custom_sms_provider is not None:
        return _custom_sms_provider

    s = get_settings()
    mode = os.environ.get("SMS_PROVIDER", "").lower()
    if mode == "mock":
        return MockSmsProvider()
    if mode == "twilio" or (s.twilio_account_sid and s.twilio_auth_token and mode != "email_bridge"):
        return TwilioSmsProvider()
    if mode == "fast2sms" or (s.fast2sms_api_key and mode != "email_bridge"):
        return Fast2SmsProvider()
    if s.smtp_host and s.smtp_user and s.smtp_pass:
        return EmailBridgeSmsProvider()
    if s.dev_mode:
        return MockSmsProvider()
    return EmailBridgeSmsProvider()


def get_sender(channel: str):
    s = get_settings()
    if channel == "email":
        if s.smtp_host and s.smtp_user and s.smtp_pass:
            return SMTPSender()
        if s.dev_mode:
            return ConsoleSender()  # dev only: no SMTP configured, code is echoed as dev_code
        raise OtpError("SMTP credentials not configured in .env (SMTP_HOST, SMTP_USER, SMTP_PASS)")
    if channel == "phone":
        return get_sms_provider()
    return ConsoleSender()


def issue(vid: str, channel: str, destination: str) -> dict:
    s = get_settings()
    if channel not in ("email", "phone"):
        raise OtpError("channel must be 'email' or 'phone'")
    if db.otp_count(vid, channel) >= s.otp_max_sends:
        raise OtpError("Too many codes requested for this session")
    code = f"{secrets.randbelow(10**6):06d}"
    db.otp_insert(vid, channel, destination, _hash(vid, channel, code, secrets.token_hex(8)),
                  time.time() + s.otp_ttl_s)

    recipient_email = None
    if channel == "phone":
        v = db.get_verification(vid)
        if v:
            recipient_email = v.get("data", {}).get("verified", {}).get("email") or v.get("data", {}).get("expected", {}).get("email")
        if not recipient_email:
            recipient_email = s.smtp_user

    send_info = {}
    if channel == "phone":
        provider = get_sms_provider()
        send_info = provider.send_sms(destination, code, recipient=recipient_email) or {}
    else:
        sender = get_sender(channel)
        sender.send(channel, destination, code)

    out = {"sent": True, "destination": mask(destination), "expires_in_s": s.otp_ttl_s}
    if send_info.get("via") == "email_bridge":
        db.update_data(vid, lambda d: d.setdefault("otp_bridge", {}).__setitem__(channel, True))
        out["fallback"] = "email"
        out["email"] = recipient_email
    if s.dev_mode:
        out["dev_code"] = code
        print(f"[otp:dev] {channel} code for {destination}: {code}", flush=True)
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
        if verified and ctx.data.get("otp_bridge", {}).get(channel):
            return CheckResult.uncertain(name, f"{channel} code was delivered by email, so it does not prove you hold this phone")
        if verified:
            return CheckResult.passed(name, f"{channel} verified ({mask(verified)})", confidence=0.9)
        row = db.otp_latest(ctx.session_id, channel)
        if row and row["attempts"] >= ctx.settings.otp_max_attempts:
            return CheckResult.failed(name, f"Too many wrong {channel} codes", confidence=0.7)
        return CheckResult.skipped(name, f"{channel} not verified")
    return check


register("email_otp")(_otp_check("email"))
register("phone_otp")(_otp_check("phone"))
