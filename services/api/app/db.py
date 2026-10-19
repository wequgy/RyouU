"""Database storage layer with SQLite default, Postgres backend, unified migrations, and product repositories."""
import os
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Callable, Dict, List, Optional, Tuple

from .config import get_settings
from .migrations import run_migrations
from .core import repository as core_repo
from .kyc import repository as kyc_repo
from .interview import repository as interview_repo

_lock = threading.RLock()


def is_postgres() -> bool:
    url = os.environ.get("DATABASE_URL", "").lower()
    return url.startswith("postgres://") or url.startswith("postgresql://")


@contextmanager
def conn():
    s = get_settings()
    db_url = os.environ.get("DATABASE_URL")

    if is_postgres() and db_url:
        try:
            import psycopg
            import psycopg.rows
            c = psycopg.connect(db_url, row_factory=psycopg.rows.dict_row)
            class PostgresWrapper:
                def __init__(self, raw_conn):
                    self._c = raw_conn
                def execute(self, sql, params=()):
                    p_sql = sql.replace("?", "%s")
                    return self._c.execute(p_sql, params)
                def executescript(self, sql):
                    with self._c.cursor() as cur:
                        cur.execute(sql)
                def commit(self):
                    self._c.commit()
                def close(self):
                    self._c.close()
            wrapped = PostgresWrapper(c)
            try:
                yield wrapped
                wrapped.commit()
            finally:
                wrapped.close()
        except ImportError:
            import psycopg2
            import psycopg2.extras
            c = psycopg2.connect(db_url)
            c.cursor_factory = psycopg2.extras.RealDictCursor
            class Psycopg2Wrapper:
                def __init__(self, raw_conn):
                    self._c = raw_conn
                def execute(self, sql, params=()):
                    p_sql = sql.replace("?", "%s")
                    cur = self._c.cursor()
                    cur.execute(p_sql, params)
                    return cur
                def executescript(self, sql):
                    with self._c.cursor() as cur:
                        cur.execute(sql)
                def commit(self):
                    self._c.commit()
                def close(self):
                    self._c.close()
            wrapped = Psycopg2Wrapper(c)
            try:
                yield wrapped
                wrapped.commit()
            finally:
                wrapped.close()
    else:
        with _lock:
            s.db_path.parent.mkdir(parents=True, exist_ok=True)
            c = sqlite3.connect(s.db_path, check_same_thread=False)
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA synchronous=NORMAL")
            try:
                yield c
                c.commit()
            finally:
                c.close()


def init_db() -> None:
    """Initialize database and execute all versioned migrations."""
    with conn() as c:
        run_migrations(c, is_postgres=is_postgres())


# ---------------- Core Domain Delegations ----------------
def upsert_tenant(tenant_id, name, api_key, webhook_url, webhook_secret, default_policy="lenient", products=None):
    return core_repo.upsert_tenant(conn, tenant_id, name, api_key, webhook_url, webhook_secret, default_policy, products)

def rotate_tenant_api_key(tenant_id: str, new_api_key: str) -> None:
    return core_repo.rotate_tenant_api_key(conn, tenant_id, new_api_key)

def rotate_tenant_webhook_secret(tenant_id: str, new_secret: str) -> None:
    return core_repo.rotate_tenant_webhook_secret(conn, tenant_id, new_secret)

def update_tenant_webhook_url(tenant_id: str, new_url: str) -> None:
    return core_repo.update_tenant_webhook_url(conn, tenant_id, new_url)

def update_tenant_policy(tenant_id: str, default_policy: str) -> None:
    return core_repo.update_tenant_policy(conn, tenant_id, default_policy)

def tenant_by_api_key(key: str) -> Optional[dict]:
    return core_repo.tenant_by_api_key(conn, key)

def tenant_by_id(tenant_id: str) -> Optional[dict]:
    return core_repo.tenant_by_id(conn, tenant_id)

def seed_demo_tenants() -> None:
    s = get_settings()
    return core_repo.seed_demo_tenants(conn, s.demo_webhook_url, s.demo_webhook_secret)

def create_api_key(tenant_id: str, scopes: List[str], expires_in_s: Optional[float] = None) -> Tuple[str, dict]:
    return core_repo.create_api_key(conn, tenant_id, scopes, expires_in_s)

def revoke_api_key(tenant_id: str, key_id: str) -> bool:
    return core_repo.revoke_api_key(conn, tenant_id, key_id)

def get_api_key(key_id: str) -> Optional[dict]:
    return core_repo.get_api_key(conn, key_id)

def list_api_keys(tenant_id: str) -> List[dict]:
    return core_repo.list_api_keys(conn, tenant_id)

def record_audit(tenant_id: str, action: str, resource_type: str, resource_id: str, details: dict = None) -> str:
    return core_repo.record_audit(conn, tenant_id, action, resource_type, resource_id, details)

def record_consent(tenant_id: str, reference_id: str, consent_type: str, granted: bool = True,
                   ip_address: str = "", user_agent: str = "") -> str:
    return core_repo.record_consent(conn, tenant_id, reference_id, consent_type, granted, ip_address, user_agent)


# ---------------- KYC Product Delegations ----------------
def create_verification(tenant_id, reference_id, policy, expected, flow_token_hash, ttl_s) -> dict:
    return kyc_repo.create_verification(conn, tenant_id, reference_id, policy, expected, flow_token_hash, ttl_s)

def get_verification(vid: str) -> Optional[dict]:
    return kyc_repo.get_verification(conn, vid)

def get_verification_for_tenant(vid: str, tenant_id: str) -> Optional[dict]:
    return kyc_repo.get_verification_for_tenant(conn, vid, tenant_id)

def get_active_verification_by_ref(tenant_id: str, reference_id: Optional[str]) -> Optional[dict]:
    return kyc_repo.get_active_verification_by_ref(conn, tenant_id, reference_id)

def update_data(vid: str, mutator: Callable[[dict], None]) -> dict:
    return kyc_repo.update_data(conn, vid, mutator)

def set_status(vid: str, status: str) -> None:
    return kyc_repo.set_status(conn, vid, status)

def claim_for_processing(vid: str) -> bool:
    return kyc_repo.claim_for_processing(conn, vid)

def find_cross_session_face(tenant_id: str, reference_id: str, embedding: list, threshold: float = 0.85) -> Optional[dict]:
    return kyc_repo.find_cross_session_face(conn, tenant_id, reference_id, embedding, threshold)

def save_review(vid: str, review: dict) -> None:
    return kyc_repo.save_review(conn, vid, review)

def save_outcome(vid: str, results: list, decision: str, reasons: list, trust: Optional[float]) -> None:
    return kyc_repo.save_outcome(conn, vid, results, decision, reasons, trust)

def save_webhook_status(vid: str, status: dict) -> None:
    return kyc_repo.save_webhook_status(conn, vid, status)

def list_verifications(tenant_id: str, limit: int = 50) -> List[dict]:
    return kyc_repo.list_verifications(conn, tenant_id, limit)

def delete_verification(vid: str, tenant_id: Optional[str] = None) -> bool:
    return kyc_repo.delete_verification(conn, vid, tenant_id)

def get_expired_verifications(max_age_s: float) -> List[str]:
    return kyc_repo.get_expired_verifications(conn, max_age_s)

def create_otp(vid: str, channel: str, destination: str, code_hash: str, ttl_s: float) -> dict:
    return kyc_repo.create_otp(conn, vid, channel, destination, code_hash, ttl_s)

def get_otp(vid: str, channel: str) -> Optional[dict]:
    return kyc_repo.get_otp(conn, vid, channel)

def record_otp_attempt(otp_id: int) -> None:
    return kyc_repo.record_otp_attempt(conn, otp_id)

def mark_otp_used(otp_id: int) -> None:
    return kyc_repo.mark_otp_used(conn, otp_id)

def count_recent_otp_sends(vid: str, channel: str, window_s: float = 300) -> int:
    return kyc_repo.count_recent_otp_sends(conn, vid, channel, window_s)

def otp_insert(vid: str, channel: str, destination: str, code_hash: str, expires_at: float) -> None:
    return kyc_repo.otp_insert(conn, vid, channel, destination, code_hash, expires_at)

otp_count = count_recent_otp_sends
otp_latest = get_otp
otp_bump_attempts = record_otp_attempt
otp_mark_used = mark_otp_used

def queue_pipeline_job(vid: str, tenant_id: str) -> str:
    return kyc_repo.queue_pipeline_job(conn, vid, tenant_id)

enqueue_pipeline_job = queue_pipeline_job

def get_pending_pipeline_jobs(limit: int = 10) -> List[dict]:
    return kyc_repo.get_pending_pipeline_jobs(conn, limit)

def mark_pipeline_job(job_id: str, status: str, error: Optional[str] = None) -> None:
    return kyc_repo.mark_pipeline_job(conn, job_id, status, error)

def record_webhook_delivery(tenant_id: str, vid: str, event_type: str, event_id: str,
                            attempt: int, status_code: Optional[int], error: Optional[str], duration_ms: int) -> str:
    return kyc_repo.record_webhook_delivery(conn, tenant_id, vid, event_type, event_id, attempt, status_code, error, duration_ms)

log_webhook_delivery = record_webhook_delivery

def save_idempotency(tenant_id: str, idempotency_key: str, status_code: int, response_body: dict) -> None:
    return kyc_repo.save_idempotency(conn, tenant_id, idempotency_key, status_code, response_body)

def get_idempotency(tenant_id: str, idempotency_key: str) -> Optional[dict]:
    return kyc_repo.get_idempotency(conn, tenant_id, idempotency_key)

def check_rate_limit(key: str, limit: int = 60, window_s: float = 60) -> bool:
    return kyc_repo.check_rate_limit(conn, key, limit, window_s)

def record_media_hash(tenant_id: str, file_hash: str, media_kind: str, vid: str) -> None:
    return kyc_repo.record_media_hash(conn, tenant_id, file_hash, media_kind, vid)

def has_seen_media_hash(tenant_id: str, file_hash: str) -> Optional[dict]:
    return kyc_repo.has_seen_media_hash(conn, tenant_id, file_hash)

get_media_hash = has_seen_media_hash

def record_face_embedding(tenant_id: str, reference_id: Optional[str], vid: str,
                          embedding: list, face_hash: str) -> None:
    return kyc_repo.record_face_embedding(conn, tenant_id, reference_id, vid, embedding, face_hash)

def find_matching_face_embedding(tenant_id: str, current_vid: str,
                                 embedding: list, threshold: float = 0.70) -> Optional[dict]:
    return kyc_repo.find_matching_face_embedding(conn, tenant_id, current_vid, embedding, threshold)


# ---------------- Interview Product Delegations ----------------
def create_interview(tenant_id: str, candidate_id: Optional[str], token_hash: str,
                     ttl_s: float, metadata: dict = None) -> dict:
    return interview_repo.create_interview(conn, tenant_id, candidate_id, token_hash, ttl_s, metadata)

def get_interview(interview_id: str) -> Optional[dict]:
    return interview_repo.get_interview(conn, interview_id)

def update_interview(interview_id: str, **kwargs) -> Optional[dict]:
    return interview_repo.update_interview(conn, interview_id, **kwargs)

def get_candidate_kyc_face(tenant_id: str, candidate_id: str) -> Optional[List[float]]:
    return interview_repo.get_candidate_kyc_face(conn, tenant_id, candidate_id)

def create_interview_clip(interview_id: str, round_num: int, metadata: dict,
                          video_path: str = "", audio_path: str = "") -> dict:
    return interview_repo.create_interview_clip(conn, interview_id, round_num, metadata, video_path, audio_path)

def get_interview_clip(clip_id: str) -> Optional[dict]:
    return interview_repo.get_interview_clip(conn, clip_id)

def update_interview_clip(clip_id: str, **kwargs) -> Optional[dict]:
    return interview_repo.update_interview_clip(conn, clip_id, **kwargs)

def list_interview_clips(interview_id: str) -> List[dict]:
    return interview_repo.list_interview_clips(conn, interview_id)
