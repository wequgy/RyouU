"""KYC Product repository: Verifications, OTPs, pipeline jobs, webhooks, media hashes, face embeddings."""
import json
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple


def _j(x: Any) -> str:
    return json.dumps(x, separators=(",", ":"))


def _row(row: Any) -> Optional[dict]:
    return dict(row) if row else None


def _parse_ver(row: Any) -> Optional[dict]:
    if not row:
        return None
    d = dict(row)
    for k, default in (("data", {}), ("results", []), ("reasons", []), ("review", None), ("webhook", None)):
        raw = d.get(k)
        if raw:
            try:
                d[k] = json.loads(raw) if isinstance(raw, str) else raw
            except Exception:
                d[k] = default
        else:
            d[k] = default
    return d


def create_verification(conn_fn, tenant_id: str, reference_id: Optional[str], policy: str, expected: dict,
                        flow_token_hash: str, ttl_s: float) -> dict:
    vid = "ver_" + uuid.uuid4().hex[:20]
    now = time.time()
    data = {"expected": expected, "files": {}, "verified": {}, "signals": {}, "challenges": {},
            "spoken_transcripts": {}}
    with conn_fn() as c:
        c.execute(
            """INSERT INTO verifications (id,tenant_id,reference_id,policy,status,flow_token_hash,
               expires_at,data,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (vid, tenant_id, reference_id, policy, "created", flow_token_hash, now + ttl_s, _j(data), now, now),
        )
    return get_verification(conn_fn, vid)


def get_verification(conn_fn, vid: str) -> Optional[dict]:
    with conn_fn() as c:
        return _parse_ver(c.execute("SELECT * FROM verifications WHERE id=?", (vid,)).fetchone())


def get_verification_for_tenant(conn_fn, vid: str, tenant_id: str) -> Optional[dict]:
    if tenant_id in ("*", "reviewer", "all"):
        return get_verification(conn_fn, vid)
    with conn_fn() as c:
        return _parse_ver(c.execute("SELECT * FROM verifications WHERE id=? AND tenant_id=?", (vid, tenant_id)).fetchone())


def get_active_verification_by_ref(conn_fn, tenant_id: str, reference_id: Optional[str]) -> Optional[dict]:
    if not reference_id:
        return None
    now = time.time()
    with conn_fn() as c:
        row = c.execute(
            """SELECT * FROM verifications WHERE tenant_id=? AND reference_id=?
               AND status NOT IN ('passed', 'failed', 'expired') AND expires_at > ?
               ORDER BY created_at DESC LIMIT 1""",
            (tenant_id, reference_id, now)
        ).fetchone()
        return _parse_ver(row)


def update_data(conn_fn, vid: str, mutator: Callable[[dict], None]) -> dict:
    with conn_fn() as c:
        v = get_verification(conn_fn, vid)
        if not v:
            raise KeyError(f"verification {vid} not found")
        data = v["data"]
        mutator(data)
        now = time.time()
        c.execute("UPDATE verifications SET data=?, updated_at=? WHERE id=?", (_j(data), now, vid))
        return get_verification(conn_fn, vid)


def set_status(conn_fn, vid: str, status: str) -> None:
    now = time.time()
    with conn_fn() as c:
        c.execute("UPDATE verifications SET status=?, updated_at=? WHERE id=?", (status, now, vid))


def claim_for_processing(conn_fn, vid: str) -> bool:
    """Move created/in_progress -> processing exactly once (prevents double submits)."""
    now = time.time()
    with conn_fn() as c:
        cur = c.execute(
            """UPDATE verifications SET status='processing', updated_at=?
               WHERE id=? AND status IN ('created', 'in_progress', 'initiated')""",
            (now, vid)
        )
        return bool(cur.rowcount == 1)


def find_cross_session_face(conn_fn, tenant_id: str, reference_id: str, embedding: list, threshold: float = 0.85) -> Optional[dict]:
    if not embedding:
        return None
    import numpy as np
    emb_a = np.array(embedding, dtype=np.float32)
    norm_a = np.linalg.norm(emb_a)
    if norm_a == 0:
        return None
    emb_a = emb_a / norm_a

    with conn_fn() as c:
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


def save_review(conn_fn, vid: str, review: dict) -> None:
    now = time.time()
    with conn_fn() as c:
        c.execute("UPDATE verifications SET status='reviewed', review=?, updated_at=? WHERE id=?", (_j(review), now, vid))


def save_outcome(conn_fn, vid: str, results: list, decision: str, reasons: list, trust: Optional[float]) -> None:
    now = time.time()
    with conn_fn() as c:
        c.execute(
            """UPDATE verifications SET status='completed', decision=?, results=?, reasons=?,
               trust=?, updated_at=? WHERE id=?""",
            (decision, _j(results), _j(reasons), trust, now, vid),
        )


def save_webhook_status(conn_fn, vid: str, status: dict) -> None:
    now = time.time()
    with conn_fn() as c:
        c.execute("UPDATE verifications SET webhook=?, updated_at=? WHERE id=?", (_j(status), now, vid))


def list_verifications(conn_fn, tenant_id: str, limit: int = 50) -> List[dict]:
    with conn_fn() as c:
        if tenant_id in ("*", "reviewer", "all"):
            rows = c.execute("SELECT * FROM verifications ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        else:
            rows = c.execute("SELECT * FROM verifications WHERE tenant_id=? ORDER BY created_at DESC LIMIT ?",
                             (tenant_id, limit)).fetchall()
        return [_parse_ver(r) for r in rows]


def delete_verification(conn_fn, vid: str, tenant_id: Optional[str] = None) -> bool:
    with conn_fn() as c:
        if tenant_id:
            cur = c.execute("DELETE FROM verifications WHERE id=? AND tenant_id=?", (vid, tenant_id))
        else:
            cur = c.execute("DELETE FROM verifications WHERE id=?", (vid,))
        c.execute("DELETE FROM otps WHERE vid=?", (vid,))
        c.execute("DELETE FROM pipeline_jobs WHERE vid=?", (vid,))
        return bool(cur.rowcount > 0)


def get_expired_verifications(conn_fn, max_age_s: float) -> List[str]:
    cutoff = time.time() - max_age_s
    with conn_fn() as c:
        rows = c.execute("SELECT id FROM verifications WHERE created_at < ?", (cutoff,)).fetchall()
        return [r["id"] if isinstance(r, dict) or hasattr(r, "__getitem__") else r[0] for r in rows]


# ---------------- OTPs ----------------
def create_otp(conn_fn, vid: str, channel: str, destination: str, code_hash: str, ttl_s: float) -> dict:
    now = time.time()
    with conn_fn() as c:
        c.execute(
            """INSERT INTO otps (vid,channel,destination,code_hash,expires_at,attempts,used,created_at)
               VALUES (?,?,?,?,?,0,0,?)""",
            (vid, channel, destination, code_hash, now + ttl_s, now),
        )
    return get_otp(conn_fn, vid, channel)


def get_otp(conn_fn, vid: str, channel: str) -> Optional[dict]:
    with conn_fn() as c:
        return _row(c.execute("SELECT * FROM otps WHERE vid=? AND channel=? ORDER BY id DESC LIMIT 1",
                              (vid, channel)).fetchone())


def record_otp_attempt(conn_fn, otp_id: int) -> None:
    with conn_fn() as c:
        c.execute("UPDATE otps SET attempts = attempts + 1 WHERE id=?", (otp_id,))


def mark_otp_used(conn_fn, otp_id: int) -> None:
    with conn_fn() as c:
        c.execute("UPDATE otps SET used=1 WHERE id=?", (otp_id,))


def count_recent_otp_sends(conn_fn, vid: str, channel: str, window_s: float = 300) -> int:
    cutoff = time.time() - window_s
    with conn_fn() as c:
        row = c.execute("SELECT COUNT(*) as n FROM otps WHERE vid=? AND channel=? AND created_at > ?",
                        (vid, channel, cutoff)).fetchone()
        return row[0] if isinstance(row, (tuple, list)) else row["n"]


# Legacy aliases for OTP callers
def otp_insert(conn_fn, vid: str, channel: str, destination: str, code_hash: str, expires_at: float) -> None:
    now = time.time()
    with conn_fn() as c:
        c.execute(
            """INSERT INTO otps (vid,channel,destination,code_hash,expires_at,attempts,used,created_at)
               VALUES (?,?,?,?,?,0,0,?)""",
            (vid, channel, destination, code_hash, expires_at, now),
        )

otp_count = count_recent_otp_sends
otp_latest = get_otp
otp_bump_attempts = record_otp_attempt
otp_mark_used = mark_otp_used


# ---------------- Pipeline Jobs ----------------
def queue_pipeline_job(conn_fn, vid: str, tenant_id: str) -> str:
    jid = "job_" + uuid.uuid4().hex[:16]
    now = time.time()
    with conn_fn() as c:
        c.execute(
            """INSERT INTO pipeline_jobs (id, vid, tenant_id, status, attempts, created_at, updated_at)
               VALUES (?, ?, ?, 'pending', 0, ?, ?)""",
            (jid, vid, tenant_id, now, now)
        )
    return jid

enqueue_pipeline_job = queue_pipeline_job


def get_pending_pipeline_jobs(conn_fn, limit: int = 10) -> List[dict]:
    with conn_fn() as c:
        rows = c.execute("SELECT * FROM pipeline_jobs WHERE status='pending' ORDER BY created_at ASC LIMIT ?",
                         (limit,)).fetchall()
        return [_row(r) for r in rows]


def mark_pipeline_job(conn_fn, job_id: str, status: str, error: Optional[str] = None) -> None:
    now = time.time()
    with conn_fn() as c:
        c.execute(
            "UPDATE pipeline_jobs SET status=?, error=?, attempts=attempts+1, updated_at=? WHERE id=?",
            (status, error, now, job_id)
        )


# ---------------- Webhook Deliveries ----------------
def record_webhook_delivery(conn_fn, tenant_id: str, vid: str, event_type: str, event_id: str,
                            attempt: int, status_code: Optional[int], error: Optional[str], duration_ms: int) -> str:
    did = "del_" + uuid.uuid4().hex[:16]
    now = time.time()
    with conn_fn() as c:
        c.execute(
            """INSERT INTO webhook_deliveries
               (id, tenant_id, vid, event_type, event_id, attempt, status_code, error, duration_ms, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (did, tenant_id, vid, event_type, event_id, attempt, status_code, error, duration_ms, now)
        )
    return did


# ---------------- Idempotency & Rate Limiting ----------------
def save_idempotency(conn_fn, tenant_id: str, idempotency_key: str, status_code: int, response_body: dict) -> None:
    now = time.time()
    with conn_fn() as c:
        c.execute(
            """INSERT INTO idempotency_keys (tenant_id, idempotency_key, status_code, response_body, created_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(tenant_id, idempotency_key) DO NOTHING""",
            (tenant_id, idempotency_key, status_code, _j(response_body), now)
        )


def get_idempotency(conn_fn, tenant_id: str, idempotency_key: str) -> Optional[dict]:
    with conn_fn() as c:
        row = c.execute(
            "SELECT * FROM idempotency_keys WHERE tenant_id=? AND idempotency_key=?",
            (tenant_id, idempotency_key)
        ).fetchone()
        if not row:
            return None
        d = _row(row)
        d["response_body"] = json.loads(d["response_body"])
        return d


def check_rate_limit(conn_fn, key: str, limit: int = 60, window_s: float = 60) -> bool:
    now = time.time()
    with conn_fn() as c:
        row = c.execute("SELECT * FROM rate_limits WHERE key=?", (key,)).fetchone()
        if not row:
            c.execute("INSERT INTO rate_limits (key, count, window_start) VALUES (?, 1, ?)", (key, now))
            return True
        r = _row(row)
        if now - r["window_start"] > window_s:
            c.execute("UPDATE rate_limits SET count=1, window_start=? WHERE key=?", (now, key))
            return True
        if r["count"] >= limit:
            return False
        c.execute("UPDATE rate_limits SET count=count+1 WHERE key=?", (key,))
        return True


# ---------------- Media Hashes & Face Embeddings ----------------
def record_media_hash(conn_fn, tenant_id: str, file_hash: str, media_kind: str, vid: str) -> None:
    now = time.time()
    with conn_fn() as c:
        c.execute(
            """INSERT INTO media_hashes (tenant_id, file_hash, media_kind, vid, created_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(tenant_id, file_hash) DO NOTHING""",
            (tenant_id, file_hash, media_kind, vid, now)
        )


def has_seen_media_hash(conn_fn, tenant_id: str, file_hash: str) -> Optional[dict]:
    with conn_fn() as c:
        return _row(c.execute("SELECT * FROM media_hashes WHERE tenant_id=? AND file_hash=?", (tenant_id, file_hash)).fetchone())


def record_face_embedding(conn_fn, tenant_id: str, reference_id: Optional[str], vid: str,
                          embedding: list, face_hash: str) -> None:
    now = time.time()
    with conn_fn() as c:
        c.execute(
            """INSERT INTO face_embeddings (tenant_id, reference_id, vid, embedding_json, face_hash, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (tenant_id, reference_id, vid, _j(embedding), face_hash, now)
        )


def find_matching_face_embedding(conn_fn, tenant_id: str, current_vid: str,
                                 embedding: list, threshold: float = 0.70) -> Optional[dict]:
    import numpy as np
    emb_a = np.array(embedding, dtype=np.float32)
    norm_a = np.linalg.norm(emb_a)
    if norm_a == 0:
        return None
    emb_a = emb_a / norm_a

    with conn_fn() as c:
        rows = c.execute(
            "SELECT * FROM face_embeddings WHERE tenant_id=? AND vid!=? ORDER BY created_at DESC LIMIT 100",
            (tenant_id, current_vid)
        ).fetchall()

    for r in rows:
        d = _row(r)
        try:
            stored_emb = np.array(json.loads(d["embedding_json"]), dtype=np.float32)
            norm_b = np.linalg.norm(stored_emb)
            if norm_b > 0:
                sim = float(np.dot(emb_a, stored_emb / norm_b))
                if sim >= threshold:
                    d["similarity"] = sim
                    return d
        except Exception:
            continue
    return None


get_media_hash = has_seen_media_hash
log_webhook_delivery = record_webhook_delivery

