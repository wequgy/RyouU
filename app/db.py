"""Database storage layer with SQLite default and optional Postgres backend."""
import json
import os
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

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
CREATE TABLE IF NOT EXISTS pipeline_jobs (
  id TEXT PRIMARY KEY, vid TEXT, tenant_id TEXT, status TEXT, attempts INTEGER DEFAULT 0,
  error TEXT, created_at REAL, updated_at REAL);
CREATE TABLE IF NOT EXISTS webhook_deliveries (
  id TEXT PRIMARY KEY, tenant_id TEXT, vid TEXT, event_type TEXT, event_id TEXT,
  attempt INTEGER, status_code INTEGER, error TEXT, duration_ms INTEGER, created_at REAL);
CREATE TABLE IF NOT EXISTS idempotency_keys (
  tenant_id TEXT, idempotency_key TEXT, status_code INTEGER, response_body TEXT,
  created_at REAL, PRIMARY KEY (tenant_id, idempotency_key));
CREATE TABLE IF NOT EXISTS rate_limits (
  key TEXT PRIMARY KEY, count INTEGER, window_start REAL);
CREATE TABLE IF NOT EXISTS media_hashes (
  tenant_id TEXT, file_hash TEXT, media_kind TEXT, vid TEXT, created_at REAL,
  PRIMARY KEY (tenant_id, file_hash));
CREATE TABLE IF NOT EXISTS face_embeddings (
  id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id TEXT, reference_id TEXT, vid TEXT,
  embedding_json TEXT, face_hash TEXT, created_at REAL);
CREATE INDEX IF NOT EXISTS idx_ver_tenant ON verifications(tenant_id, created_at);
CREATE INDEX IF NOT EXISTS idx_otp ON otps(vid, channel);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON pipeline_jobs(status);
CREATE INDEX IF NOT EXISTS idx_media_hashes ON media_hashes(tenant_id, file_hash);
CREATE INDEX IF NOT EXISTS idx_face_emb ON face_embeddings(tenant_id, reference_id);
"""

PG_SCHEMA = """
CREATE TABLE IF NOT EXISTS tenants (
  id TEXT PRIMARY KEY, name TEXT, api_key_hash TEXT UNIQUE, webhook_url TEXT,
  webhook_secret TEXT, default_policy TEXT, created_at DOUBLE PRECISION);
CREATE TABLE IF NOT EXISTS verifications (
  id TEXT PRIMARY KEY, tenant_id TEXT, reference_id TEXT, policy TEXT, status TEXT,
  decision TEXT, flow_token_hash TEXT, expires_at DOUBLE PRECISION, data TEXT, results TEXT,
  reasons TEXT, trust DOUBLE PRECISION, review TEXT, webhook TEXT, created_at DOUBLE PRECISION, updated_at DOUBLE PRECISION);
CREATE TABLE IF NOT EXISTS otps (
  id SERIAL PRIMARY KEY, vid TEXT, channel TEXT, destination TEXT,
  code_hash TEXT, expires_at DOUBLE PRECISION, attempts INTEGER DEFAULT 0, used INTEGER DEFAULT 0,
  created_at DOUBLE PRECISION);
CREATE TABLE IF NOT EXISTS pipeline_jobs (
  id TEXT PRIMARY KEY, vid TEXT, tenant_id TEXT, status TEXT, attempts INTEGER DEFAULT 0,
  error TEXT, created_at DOUBLE PRECISION, updated_at DOUBLE PRECISION);
CREATE TABLE IF NOT EXISTS webhook_deliveries (
  id TEXT PRIMARY KEY, tenant_id TEXT, vid TEXT, event_type TEXT, event_id TEXT,
  attempt INTEGER, status_code INTEGER, error TEXT, duration_ms INTEGER, created_at DOUBLE PRECISION);
CREATE TABLE IF NOT EXISTS idempotency_keys (
  tenant_id TEXT, idempotency_key TEXT, status_code INTEGER, response_body TEXT,
  created_at DOUBLE PRECISION, PRIMARY KEY (tenant_id, idempotency_key));
CREATE TABLE IF NOT EXISTS rate_limits (
  key TEXT PRIMARY KEY, count INTEGER, window_start DOUBLE PRECISION);
CREATE TABLE IF NOT EXISTS media_hashes (
  tenant_id TEXT, file_hash TEXT, media_kind TEXT, vid TEXT, created_at DOUBLE PRECISION,
  PRIMARY KEY (tenant_id, file_hash));
CREATE TABLE IF NOT EXISTS face_embeddings (
  id SERIAL PRIMARY KEY, tenant_id TEXT, reference_id TEXT, vid TEXT,
  embedding_json TEXT, face_hash TEXT, created_at DOUBLE PRECISION);
CREATE INDEX IF NOT EXISTS idx_ver_tenant ON verifications(tenant_id, created_at);
CREATE INDEX IF NOT EXISTS idx_otp ON otps(vid, channel);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON pipeline_jobs(status);
CREATE INDEX IF NOT EXISTS idx_media_hashes ON media_hashes(tenant_id, file_hash);
CREATE INDEX IF NOT EXISTS idx_face_emb ON face_embeddings(tenant_id, reference_id);
"""

_pg_pool = None


def is_postgres() -> bool:
    url = os.environ.get("DATABASE_URL", "")
    return url.startswith("postgres://") or url.startswith("postgresql://")


def _get_pg_conn():
    global _pg_pool
    url = os.environ["DATABASE_URL"]
    try:
        import psycopg
        from psycopg.rows import dict_row
        return psycopg.connect(url, row_factory=dict_row)
    except ImportError:
        try:
            import psycopg2
            import psycopg2.extras
            conn = psycopg2.connect(url)
            conn.cursor_factory = psycopg2.extras.RealDictCursor
            return conn
        except ImportError:
            raise RuntimeError("Postgres database requested in DATABASE_URL but neither 'psycopg' nor 'psycopg2' is installed.")


class CursorWrapper:
    """Wrapper that translates '?' placeholders to '%s' for Postgres compatibility."""
    def __init__(self, raw_cursor, is_pg: bool):
        self._cur = raw_cursor
        self._is_pg = is_pg

    def execute(self, sql: str, params: tuple = ()):
        if self._is_pg:
            sql = sql.replace("?", "%s")
        return self._cur.execute(sql, params)

    def executescript(self, script: str):
        if self._is_pg:
            return self._cur.execute(script)
        return self._cur.executescript(script)

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    @property
    def rowcount(self):
        return self._cur.rowcount


class ConnectionWrapper:
    def __init__(self, raw_conn, is_pg: bool):
        self._conn = raw_conn
        self._is_pg = is_pg

    def execute(self, sql: str, params: tuple = ()):
        cur = self._conn.cursor()
        wrapped = CursorWrapper(cur, self._is_pg)
        wrapped.execute(sql, params)
        return wrapped

    def executescript(self, script: str):
        if self._is_pg:
            cur = self._conn.cursor()
            cur.execute(script)
            return cur
        return self._conn.executescript(script)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


@contextmanager
def conn():
    s = get_settings()
    if is_postgres():
        c = _get_pg_conn()
        wrapped = ConnectionWrapper(c, is_pg=True)
        try:
            yield wrapped
            wrapped.commit()
        except Exception:
            wrapped.rollback()
            raise
        finally:
            wrapped.close()
    else:
        s.data_dir.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(str(s.db_path), timeout=30)
        c.row_factory = sqlite3.Row
        wrapped = ConnectionWrapper(c, is_pg=False)
        try:
            with _lock:
                yield wrapped
                wrapped.commit()
        finally:
            wrapped.close()


def init_db() -> None:
    with conn() as c:
        if is_postgres():
            c.executescript(PG_SCHEMA)
        else:
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


def rotate_tenant_api_key(tenant_id: str, new_api_key: str) -> None:
    from .security import hash_key
    with conn() as c:
        c.execute("UPDATE tenants SET api_key_hash=? WHERE id=?", (hash_key(new_api_key), tenant_id))


def rotate_tenant_webhook_secret(tenant_id: str, new_secret: str) -> None:
    with conn() as c:
        c.execute("UPDATE tenants SET webhook_secret=? WHERE id=?", (new_secret, tenant_id))


def update_tenant_webhook_url(tenant_id: str, new_url: str) -> None:
    with conn() as c:
        c.execute("UPDATE tenants SET webhook_url=? WHERE id=?", (new_url, tenant_id))


def update_tenant_policy(tenant_id: str, default_policy: str) -> None:
    with conn() as c:
        c.execute("UPDATE tenants SET default_policy=? WHERE id=?", (default_policy, tenant_id))


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


# ---------------- Idempotency Keys ----------------
def get_idempotency(tenant_id: str, key: str) -> Optional[dict]:
    with conn() as c:
        row = c.execute("SELECT * FROM idempotency_keys WHERE tenant_id=? AND idempotency_key=?",
                        (tenant_id, key)).fetchone()
        if not row:
            return None
        r = dict(row)
        r["response_body"] = json.loads(r["response_body"])
        return r


def save_idempotency(tenant_id: str, key: str, status_code: int, response_data: dict) -> None:
    with conn() as c:
        c.execute(
            """INSERT INTO idempotency_keys (tenant_id, idempotency_key, status_code, response_body, created_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(tenant_id, idempotency_key) DO UPDATE SET
               status_code=excluded.status_code, response_body=excluded.response_body""",
            (tenant_id, key, status_code, _j(response_data), time.time()),
        )


# ---------------- Rate Limiting ----------------
def check_rate_limit(key: str, limit: int = 60, window_s: int = 60) -> bool:
    """Returns True if within rate limit, False if limit exceeded."""
    now = time.time()
    with conn() as c:
        row = c.execute("SELECT * FROM rate_limits WHERE key=?", (key,)).fetchone()
        if not row:
            c.execute("INSERT INTO rate_limits (key, count, window_start) VALUES (?, 1, ?)", (key, now))
            return True
        r = dict(row)
        if now - r["window_start"] > window_s:
            c.execute("UPDATE rate_limits SET count=1, window_start=? WHERE key=?", (now, key))
            return True
        if r["count"] >= limit:
            return False
        c.execute("UPDATE rate_limits SET count=count+1 WHERE key=?", (key,))
        return True


# ---------------- Pipeline Durability (DB-backed queue) ----------------
def enqueue_pipeline_job(vid: str, tenant_id: str) -> str:
    job_id = "job_" + uuid.uuid4().hex[:16]
    now = time.time()
    with conn() as c:
        c.execute(
            "INSERT INTO pipeline_jobs (id, vid, tenant_id, status, attempts, created_at, updated_at) "
            "VALUES (?, ?, ?, 'pending', 0, ?, ?)",
            (job_id, vid, tenant_id, now, now),
        )
    return job_id


def get_pending_pipeline_jobs() -> List[dict]:
    with conn() as c:
        rows = c.execute("SELECT * FROM pipeline_jobs WHERE status IN ('pending', 'processing') "
                         "ORDER BY created_at ASC LIMIT 100").fetchall()
    return [dict(r) for r in rows]


def mark_pipeline_job(job_id: str, status: str, error: Optional[str] = None) -> None:
    with conn() as c:
        c.execute("UPDATE pipeline_jobs SET status=?, attempts=attempts+1, error=?, updated_at=? WHERE id=?",
                  (status, error, time.time(), job_id))


# ---------------- Webhook Deliveries Log ----------------
def log_webhook_delivery(tenant_id: str, vid: str, event_type: str, event_id: str,
                         attempt: int, status_code: Optional[int], error: Optional[str],
                         duration_ms: int) -> None:
    delivery_id = "whdel_" + uuid.uuid4().hex[:16]
    with conn() as c:
        c.execute(
            "INSERT INTO webhook_deliveries (id, tenant_id, vid, event_type, event_id, attempt, "
            "status_code, error, duration_ms, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (delivery_id, tenant_id, vid, event_type, event_id, attempt, status_code, error, duration_ms, time.time()),
        )


def get_webhook_deliveries(vid: str) -> List[dict]:
    with conn() as c:
        rows = c.execute("SELECT * FROM webhook_deliveries WHERE vid=? ORDER BY attempt ASC", (vid,)).fetchall()
    return [dict(r) for r in rows]


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


# ---------------- Retention & Deletion ----------------
def get_expired_verifications(max_age_s: float) -> List[str]:
    cutoff = time.time() - max_age_s
    with conn() as c:
        rows = c.execute("SELECT id FROM verifications WHERE created_at < ?", (cutoff,)).fetchall()
    return [r["id"] for r in rows]


def delete_verification(vid: str) -> None:
    with conn() as c:
        c.execute("DELETE FROM otps WHERE vid=?", (vid,))
        c.execute("DELETE FROM pipeline_jobs WHERE vid=?", (vid,))
        c.execute("DELETE FROM webhook_deliveries WHERE vid=?", (vid,))
        c.execute("DELETE FROM media_hashes WHERE vid=?", (vid,))
        c.execute("DELETE FROM face_embeddings WHERE vid=?", (vid,))
        c.execute("DELETE FROM verifications WHERE id=?", (vid,))


# ---------------- Media Replay / Reuse Protection ----------------
def record_media_hash(tenant_id: str, file_hash: str, media_kind: str, vid: str) -> bool:
    """Store sha256 of media per tenant. Returns True if stored, False if already exists."""
    now = time.time()
    with conn() as c:
        try:
            c.execute("INSERT INTO media_hashes (tenant_id, file_hash, media_kind, vid, created_at) VALUES (?, ?, ?, ?, ?)",
                      (tenant_id, file_hash, media_kind, vid, now))
            return True
        except Exception:
            return False


def get_media_hash(tenant_id: str, file_hash: str) -> Optional[dict]:
    with conn() as c:
        return _row(c.execute("SELECT * FROM media_hashes WHERE tenant_id=? AND file_hash=?",
                              (tenant_id, file_hash)).fetchone())


# ---------------- Cross-Session Fraud (Face Embeddings) ----------------
def record_face_embedding(tenant_id: str, reference_id: str, vid: str, embedding: list, face_hash: str = "") -> None:
    now = time.time()
    emb_json = json.dumps([round(float(x), 5) for x in embedding])
    with conn() as c:
        c.execute("INSERT INTO face_embeddings (tenant_id, reference_id, vid, embedding_json, face_hash, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                  (tenant_id, reference_id, vid, emb_json, face_hash, now))


def find_cross_session_face(tenant_id: str, reference_id: str, embedding: list, threshold: float = 0.85) -> Optional[dict]:
    """Check if the same face embedding appears under a different reference_id in this tenant."""
    if not embedding:
        return None
    import numpy as np
    emb_a = np.array(embedding, dtype=np.float32)
    norm_a = np.linalg.norm(emb_a)
    if norm_a == 0:
        return None
    emb_a = emb_a / norm_a

    with conn() as c:
        rows = c.execute("SELECT * FROM face_embeddings WHERE tenant_id=? AND reference_id != ?",
                         (tenant_id, reference_id)).fetchall()
        for r in rows:
            d = _row(r)
            if not d or not d.get("embedding_json"):
                continue
            try:
                cand = np.array(json.loads(d["embedding_json"]), dtype=np.float32)
                norm_c = np.linalg.norm(cand)
                if norm_c > 0:
                    cand = cand / norm_c
                    sim = float(np.dot(emb_a, cand))
                    if sim >= threshold:
                        d["similarity"] = sim
                        return d
            except Exception:
                continue
    return None


def get_active_verification_by_ref(tenant_id: str, reference_id: str) -> Optional[dict]:
    """Get active (unexpired, not completed) verification for tenant and reference_id."""
    now = time.time()
    with conn() as c:
        rows = c.execute("SELECT * FROM verifications WHERE tenant_id=? AND reference_id=? AND status NOT IN ('completed', 'failed', 'expired') AND expires_at > ? ORDER BY created_at DESC LIMIT 1",
                         (tenant_id, reference_id, now)).fetchall()
        if rows:
            return _parse_ver(_row(rows[0]))
    return None

