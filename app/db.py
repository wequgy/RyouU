"""SQLite storage. Simple on purpose: swap for Postgres later without touching callers."""
import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from typing import Optional

from .config import get_settings

_lock = threading.RLock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS tenants (
  id TEXT PRIMARY KEY, name TEXT, api_key_hash TEXT UNIQUE, webhook_url TEXT,
  webhook_secret TEXT, default_policy TEXT, created_at REAL);
CREATE TABLE IF NOT EXISTS verifications (
  id TEXT PRIMARY KEY, tenant_id TEXT, reference_id TEXT, policy TEXT, status TEXT,
  decision TEXT, flow_token_hash TEXT, expires_at REAL, data TEXT, results TEXT,
  reasons TEXT, trust REAL, review TEXT, webhook TEXT, created_at REAL, updated_at REAL);
CREATE TABLE IF NOT EXISTS otps (
  id INTEGER PRIMARY KEY AUTOINCREMENT, vid TEXT, channel TEXT, destination TEXT,
  code_hash TEXT, expires_at REAL, attempts INTEGER DEFAULT 0, used INTEGER DEFAULT 0,
  created_at REAL);
CREATE INDEX IF NOT EXISTS idx_ver_tenant ON verifications(tenant_id, created_at);
CREATE INDEX IF NOT EXISTS idx_otp ON otps(vid, channel);
"""


@contextmanager
def conn():
    s = get_settings()
    s.data_dir.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(s.db_path), timeout=30)
    c.row_factory = sqlite3.Row
    try:
        with _lock:
            yield c
            c.commit()
    finally:
        c.close()


def init_db() -> None:
    with conn() as c:
        c.executescript(SCHEMA)


def _j(x) -> str:
    return json.dumps(x, separators=(",", ":"))


def _row(row) -> Optional[dict]:
    return dict(row) if row else None


# ---------------- tenants ----------------
def upsert_tenant(tenant_id, name, api_key, webhook_url, webhook_secret, default_policy="lenient"):
    from .security import hash_key
    with conn() as c:
        c.execute(
            """INSERT INTO tenants (id,name,api_key_hash,webhook_url,webhook_secret,default_policy,created_at)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET name=excluded.name, api_key_hash=excluded.api_key_hash,
               webhook_url=excluded.webhook_url, webhook_secret=excluded.webhook_secret,
               default_policy=excluded.default_policy""",
            (tenant_id, name, hash_key(api_key), webhook_url, webhook_secret, default_policy, time.time()),
        )


def tenant_by_api_key(key: str) -> Optional[dict]:
    from .security import hash_key
    with conn() as c:
        return _row(c.execute("SELECT * FROM tenants WHERE api_key_hash=?", (hash_key(key),)).fetchone())


def tenant_by_id(tenant_id: str) -> Optional[dict]:
    with conn() as c:
        return _row(c.execute("SELECT * FROM tenants WHERE id=?", (tenant_id,)).fetchone())


def seed_demo_tenants() -> None:
    s = get_settings()
    upsert_tenant("demo_lenient", "Demo Fintech (lenient policy)", "kyc_demo_lenient_key",
                  s.demo_webhook_url, s.demo_webhook_secret, "lenient")
    upsert_tenant("demo_strict", "Demo Bank (strict policy)", "kyc_demo_strict_key",
                  s.demo_webhook_url, s.demo_webhook_secret, "strict")


# ---------------- verifications ----------------
def _parse_ver(row) -> Optional[dict]:
    if not row:
        return None
    d = dict(row)
    for k, default in (("data", {}), ("results", []), ("reasons", []), ("review", None), ("webhook", None)):
        d[k] = json.loads(d[k]) if d.get(k) else default
    return d


def create_verification(tenant_id, reference_id, policy, expected, flow_token_hash, ttl_s) -> dict:
    vid = "ver_" + uuid.uuid4().hex[:20]
    now = time.time()
    data = {"expected": expected, "files": {}, "verified": {}, "signals": {}, "challenges": {},
            "spoken_transcripts": {}}
    with conn() as c:
        c.execute(
            """INSERT INTO verifications (id,tenant_id,reference_id,policy,status,flow_token_hash,
               expires_at,data,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (vid, tenant_id, reference_id, policy, "created", flow_token_hash, now + ttl_s, _j(data), now, now),
        )
    return get_verification(vid)


def get_verification(vid: str) -> Optional[dict]:
    with conn() as c:
        return _parse_ver(c.execute("SELECT * FROM verifications WHERE id=?", (vid,)).fetchone())


def get_verification_for_tenant(vid: str, tenant_id: str) -> Optional[dict]:
    v = get_verification(vid)
    return v if v and v["tenant_id"] == tenant_id else None


def list_verifications(tenant_id: str, limit: int = 50) -> list:
    with conn() as c:
        rows = c.execute("SELECT * FROM verifications WHERE tenant_id=? ORDER BY created_at DESC LIMIT ?",
                         (tenant_id, limit)).fetchall()
    return [_parse_ver(r) for r in rows]


def update_data(vid: str, mutate) -> dict:
    """Atomically read-modify-write the session data JSON. `mutate(data)` edits in place."""
    with conn() as c:
        row = c.execute("SELECT data FROM verifications WHERE id=?", (vid,)).fetchone()
        data = json.loads(row["data"])
        mutate(data)
        c.execute("UPDATE verifications SET data=?, updated_at=? WHERE id=?", (_j(data), time.time(), vid))
        return data


def set_status(vid: str, status: str) -> None:
    with conn() as c:
        c.execute("UPDATE verifications SET status=?, updated_at=? WHERE id=?", (status, time.time(), vid))


def claim_for_processing(vid: str) -> bool:
    """Move created/in_progress -> processing exactly once (prevents double submits)."""
    with conn() as c:
        cur = c.execute("UPDATE verifications SET status='processing', updated_at=? "
                        "WHERE id=? AND status IN ('created','in_progress')", (time.time(), vid))
        return cur.rowcount == 1


def save_outcome(vid, results, decision, reasons, trust) -> None:
    with conn() as c:
        c.execute("UPDATE verifications SET status='completed', decision=?, results=?, reasons=?, trust=?, "
                  "updated_at=? WHERE id=?", (decision, _j(results), _j(reasons), trust, time.time(), vid))


def save_review(vid, review: dict) -> None:
    with conn() as c:
        c.execute("UPDATE verifications SET status='reviewed', review=?, updated_at=? WHERE id=?",
                  (_j(review), time.time(), vid))


def save_webhook_status(vid, status: dict) -> None:
    with conn() as c:
        c.execute("UPDATE verifications SET webhook=?, updated_at=? WHERE id=?", (_j(status), time.time(), vid))


# ---------------- OTPs ----------------
def otp_insert(vid, channel, destination, code_hash, expires_at) -> None:
    with conn() as c:
        c.execute("INSERT INTO otps (vid,channel,destination,code_hash,expires_at,created_at) VALUES (?,?,?,?,?,?)",
                  (vid, channel, destination, code_hash, expires_at, time.time()))


def otp_count(vid, channel) -> int:
    with conn() as c:
        return c.execute("SELECT COUNT(*) FROM otps WHERE vid=? AND channel=?", (vid, channel)).fetchone()[0]


def otp_latest(vid, channel) -> Optional[dict]:
    with conn() as c:
        return _row(c.execute("SELECT * FROM otps WHERE vid=? AND channel=? ORDER BY id DESC LIMIT 1",
                              (vid, channel)).fetchone())


def otp_bump_attempts(otp_id) -> None:
    with conn() as c:
        c.execute("UPDATE otps SET attempts=attempts+1 WHERE id=?", (otp_id,))


def otp_mark_used(otp_id) -> None:
    with conn() as c:
        c.execute("UPDATE otps SET used=1 WHERE id=?", (otp_id,))


def delete_verification(vid: str) -> None:
    with conn() as c:
        c.execute("DELETE FROM otps WHERE vid=?", (vid,))
        c.execute("DELETE FROM verifications WHERE id=?", (vid,))
