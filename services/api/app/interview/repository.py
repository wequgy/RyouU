"""Interview Overlay repository: Interviews, clips, face baseline linkage."""
import json
import time
import uuid
from typing import Any, Dict, List, Optional


def _j(x: Any) -> str:
    return json.dumps(x, separators=(",", ":"))


def _row(row: Any) -> Optional[dict]:
    return dict(row) if row else None


def _parse_interview(row: Any) -> Optional[dict]:
    if not row:
        return None
    d = dict(row)
    for k in ("metadata", "face_baseline"):
        raw = d.get(k)
        if raw:
            try:
                d[k] = json.loads(raw) if isinstance(raw, str) else raw
            except Exception:
                d[k] = None
        else:
            d[k] = None
    return d


def _parse_clip(row: Any) -> Optional[dict]:
    if not row:
        return None
    d = dict(row)
    for k, default in (("metadata", {}), ("results", [])):
        raw = d.get(k)
        if raw:
            try:
                d[k] = json.loads(raw) if isinstance(raw, str) else raw
            except Exception:
                d[k] = default
        else:
            d[k] = default
    return d


def create_interview(conn_fn, tenant_id: str, candidate_id: Optional[str], token_hash: str,
                     ttl_s: float, metadata: dict = None) -> dict:
    iid = "iv_" + uuid.uuid4().hex[:20]
    now = time.time()
    meta = metadata or {}
    with conn_fn() as c:
        c.execute(
            """INSERT INTO interviews (id, tenant_id, candidate_id, token_hash, status, metadata,
               face_baseline, speaker_id, created_at, expires_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (iid, tenant_id, candidate_id, token_hash, "active", _j(meta), None, None, now, now + ttl_s, now)
        )
    return get_interview(conn_fn, iid)


def get_interview(conn_fn, interview_id: str) -> Optional[dict]:
    with conn_fn() as c:
        return _parse_interview(c.execute("SELECT * FROM interviews WHERE id=?", (interview_id,)).fetchone())


def update_interview(conn_fn, interview_id: str, **kwargs) -> Optional[dict]:
    if not kwargs:
        return get_interview(conn_fn, interview_id)
    fields = []
    vals = []
    for k, v in kwargs.items():
        fields.append(f"{k}=?")
        vals.append(_j(v) if isinstance(v, (dict, list)) else v)
    vals.extend([time.time(), interview_id])
    with conn_fn() as c:
        c.execute(f"UPDATE interviews SET {', '.join(fields)}, updated_at=? WHERE id=?", tuple(vals))
    return get_interview(conn_fn, interview_id)


def get_candidate_kyc_face(conn_fn, tenant_id: str, candidate_id: str) -> Optional[List[float]]:
    """Retrieve verified face embedding baseline from KYC session if available."""
    if not candidate_id:
        return None
    with conn_fn() as c:
        row = c.execute(
            """SELECT embedding_json FROM face_embeddings
               WHERE tenant_id=? AND reference_id=?
               ORDER BY created_at DESC LIMIT 1""",
            (tenant_id, candidate_id)
        ).fetchone()
        if row:
            raw = row[0] if isinstance(row, (tuple, list)) else row["embedding_json"]
            try:
                return json.loads(raw)
            except Exception:
                return None
    return None


def create_interview_clip(conn_fn, interview_id: str, round_num: int, metadata: dict,
                          video_path: str = "", audio_path: str = "") -> dict:
    clip_id = "clip_" + uuid.uuid4().hex[:20]
    now = time.time()
    with conn_fn() as c:
        c.execute(
            """INSERT INTO interview_clips (id, interview_id, round, status, metadata, video_path,
               audio_path, results, recommendation, action, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (clip_id, interview_id, round_num, "pending", _j(metadata), video_path, audio_path, _j([]), "processing", "Analyzing clip signals", now)
        )
    return get_interview_clip(conn_fn, clip_id)


def get_interview_clip(conn_fn, clip_id: str) -> Optional[dict]:
    with conn_fn() as c:
        return _parse_clip(c.execute("SELECT * FROM interview_clips WHERE id=?", (clip_id,)).fetchone())


def update_interview_clip(conn_fn, clip_id: str, **kwargs) -> Optional[dict]:
    if not kwargs:
        return get_interview_clip(conn_fn, clip_id)
    fields = []
    vals = []
    for k, v in kwargs.items():
        fields.append(f"{k}=?")
        vals.append(_j(v) if isinstance(v, (dict, list)) else v)
    vals.append(clip_id)
    with conn_fn() as c:
        c.execute(f"UPDATE interview_clips SET {', '.join(fields)} WHERE id=?", tuple(vals))
    return get_interview_clip(conn_fn, clip_id)


def list_interview_clips(conn_fn, interview_id: str) -> List[dict]:
    with conn_fn() as c:
        rows = c.execute("SELECT * FROM interview_clips WHERE interview_id=? ORDER BY round ASC, created_at ASC",
                         (interview_id,)).fetchall()
        return [_parse_clip(r) for r in rows]
