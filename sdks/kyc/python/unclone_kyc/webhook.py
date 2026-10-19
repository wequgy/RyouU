import hashlib
import hmac
import json
import time
from typing import Optional

from .exceptions import WebhookVerificationError


def verify_webhook(body: bytes, signature_header: str, secret: str,
                   tolerance_s: int = 300, now: Optional[float] = None) -> dict:
    """Verify incoming KYC webhook signature and parse the payload.

    Args:
        body: Raw HTTP request body bytes.
        signature_header: The value of the 'X-KYC-Signature' header.
        secret: Customer's webhook signing secret (e.g. 'whsec_...').
        tolerance_s: Maximum allowed time difference in seconds to prevent replay attacks (default 300s).
        now: Optional current timestamp (useful for testing).

    Returns:
        dict: The parsed JSON event object.

    Raises:
        WebhookVerificationError: If the signature is invalid or timestamp expired.
    """
    if not signature_header:
        raise WebhookVerificationError("Missing X-KYC-Signature header")

    try:
        parts = dict(p.split("=", 1) for p in signature_header.split(","))
        ts = int(parts["t"])
        given_mac = parts["v1"]
    except Exception as e:
        raise WebhookVerificationError(f"Malformed signature header: {e}")

    current_time = time.time() if now is None else now
    if abs(current_time - ts) > tolerance_s:
        raise WebhookVerificationError(
            f"Webhook timestamp outside tolerance ({abs(current_time - ts):.1f}s > {tolerance_s}s)"
        )

    expected_mac = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_mac, given_mac):
        raise WebhookVerificationError("Webhook signature verification failed")

    try:
        return json.loads(body.decode("utf-8"))
    except Exception as e:
        raise WebhookVerificationError(f"Failed to decode webhook payload JSON: {e}")
