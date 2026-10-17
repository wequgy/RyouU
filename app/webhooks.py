"""Signed webhook delivery with retries and attempt logging. Customers verify with security.verify_signature."""
import json
import time
import uuid

import httpx

from . import db
from .config import get_settings
from .security import sign_payload

CLIENT_FACTORY = lambda: httpx.Client(timeout=10)  # noqa: E731  (replaceable in tests)


def build_event(event_type: str, data: dict) -> dict:
    return {"id": "evt_" + uuid.uuid4().hex[:16], "type": event_type, "created": int(time.time()), "data": data}


def deliver(tenant: dict, event_type: str, data: dict) -> dict:
    """POST the event to the tenant's webhook URL. Returns a delivery status dict (never raises)."""
    s = get_settings()
    if not tenant.get("webhook_url"):
        return {"status": "no_webhook"}
    event = build_event(event_type, data)
    body = json.dumps(event, separators=(",", ":")).encode()
    last = ""
    vid = data.get("id", "")
    with CLIENT_FACTORY() as client:
        for attempt in range(1, s.webhook_max_attempts + 1):
            headers = {"Content-Type": "application/json", "X-KYC-Event": event_type,
                       "X-KYC-Event-Id": event["id"],
                       "X-KYC-Signature": sign_payload(tenant["webhook_secret"], body)}
            t0 = time.time()
            status_code = None
            err = None
            try:
                r = client.post(tenant["webhook_url"], content=body, headers=headers)
                status_code = r.status_code
                duration_ms = int((time.time() - t0) * 1000)
                if 200 <= r.status_code < 300:
                    db.log_webhook_delivery(tenant["id"], vid, event_type, event["id"], attempt, status_code, None, duration_ms)
                    return {"status": "delivered", "attempts": attempt, "event_id": event["id"]}
                last = f"HTTP {r.status_code}"
                err = last
            except httpx.HTTPError as e:
                duration_ms = int((time.time() - t0) * 1000)
                last = str(e)
                err = last
            db.log_webhook_delivery(tenant["id"], vid, event_type, event["id"], attempt, status_code, err, duration_ms)
            if attempt < s.webhook_max_attempts:
                time.sleep(s.webhook_backoff_s * (2 ** (attempt - 1)))
    return {"status": "failed", "attempts": s.webhook_max_attempts, "last_error": last, "event_id": event["id"]}
