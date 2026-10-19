"""Unified database migration runner for SQLite and Postgres."""
import logging
import time
from typing import Any, Callable, List, Tuple

logger = logging.getLogger(__name__)


def _is_pg(c: Any) -> bool:
    return getattr(c, "__class__", None).__name__ == "Connection" and "psycopg" in c.__class__.__module__


def ensure_migrations_table(c: Any, is_postgres: bool) -> None:
    time_type = "DOUBLE PRECISION" if is_postgres else "REAL"
    sql = f"""
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version TEXT PRIMARY KEY,
        name TEXT,
        applied_at {time_type}
    );
    """
    if is_postgres:
        c.execute(sql)
    else:
        c.executescript(sql)


# ---------------- Migration Definitions ----------------
def migration_0001_core_and_products(c: Any, is_postgres: bool) -> None:
    real_t = "DOUBLE PRECISION" if is_postgres else "REAL"
    stmts = [
        f"""CREATE TABLE IF NOT EXISTS tenants (
            id TEXT PRIMARY KEY,
            name TEXT,
            api_key_hash TEXT UNIQUE,
            webhook_url TEXT,
            webhook_secret TEXT,
            default_policy TEXT,
            products TEXT,
            created_at {real_t}
        );""",
        f"""CREATE TABLE IF NOT EXISTS api_keys (
            id TEXT PRIMARY KEY,
            tenant_id TEXT,
            key_hash TEXT UNIQUE,
            prefix TEXT,
            scopes TEXT,
            revoked INTEGER DEFAULT 0,
            created_at {real_t},
            expires_at {real_t}
        );""",
        f"""CREATE TABLE IF NOT EXISTS audit_log (
            id TEXT PRIMARY KEY,
            tenant_id TEXT,
            action TEXT,
            resource_type TEXT,
            resource_id TEXT,
            details TEXT,
            created_at {real_t}
        );""",
        f"""CREATE TABLE IF NOT EXISTS consent (
            id TEXT PRIMARY KEY,
            tenant_id TEXT,
            reference_id TEXT,
            consent_type TEXT,
            granted INTEGER DEFAULT 1,
            ip_address TEXT,
            user_agent TEXT,
            created_at {real_t}
        );"""
    ]
    for stmt in stmts:
        if is_postgres:
            c.execute(stmt)
        else:
            c.executescript(stmt)

    # Data migration: Ensure existing tenants table has products column and default values
    if is_postgres:
        try:
            c.execute("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS products TEXT;")
        except Exception:
            pass
        c.execute("UPDATE tenants SET products='[\"kyc\", \"interview\"]' WHERE products IS NULL;")
    else:
        cols = [col[1] for col in c.execute("PRAGMA table_info(tenants)").fetchall()]
        if "products" not in cols:
            c.execute("ALTER TABLE tenants ADD COLUMN products TEXT;")
        c.execute("UPDATE tenants SET products='[\"kyc\", \"interview\"]' WHERE products IS NULL;")


def migration_0002_product_tables(c: Any, is_postgres: bool) -> None:
    real_t = "DOUBLE PRECISION" if is_postgres else "REAL"
    auto_id = "SERIAL PRIMARY KEY" if is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"
    stmts = [
        # KYC product tables
        f"""CREATE TABLE IF NOT EXISTS verifications (
            id TEXT PRIMARY KEY,
            tenant_id TEXT,
            reference_id TEXT,
            policy TEXT,
            status TEXT,
            decision TEXT,
            flow_token_hash TEXT,
            expires_at {real_t},
            data TEXT,
            results TEXT,
            reasons TEXT,
            trust {real_t},
            review TEXT,
            webhook TEXT,
            created_at {real_t},
            updated_at {real_t}
        );""",
        f"""CREATE TABLE IF NOT EXISTS otps (
            id {auto_id},
            vid TEXT,
            channel TEXT,
            destination TEXT,
            code_hash TEXT,
            expires_at {real_t},
            attempts INTEGER DEFAULT 0,
            used INTEGER DEFAULT 0,
            created_at {real_t}
        );""",
        f"""CREATE TABLE IF NOT EXISTS pipeline_jobs (
            id TEXT PRIMARY KEY,
            vid TEXT,
            tenant_id TEXT,
            status TEXT DEFAULT 'pending',
            attempts INTEGER DEFAULT 0,
            error TEXT,
            created_at {real_t},
            updated_at {real_t}
        );""",
        f"""CREATE TABLE IF NOT EXISTS webhook_deliveries (
            id TEXT PRIMARY KEY,
            tenant_id TEXT,
            vid TEXT,
            event_type TEXT,
            event_id TEXT,
            attempt INTEGER,
            status_code INTEGER,
            error TEXT,
            duration_ms INTEGER,
            created_at {real_t}
        );""",
        f"""CREATE TABLE IF NOT EXISTS idempotency_keys (
            tenant_id TEXT,
            idempotency_key TEXT,
            status_code INTEGER,
            response_body TEXT,
            created_at {real_t},
            PRIMARY KEY (tenant_id, idempotency_key)
        );""",
        f"""CREATE TABLE IF NOT EXISTS rate_limits (
            key TEXT PRIMARY KEY,
            count INTEGER DEFAULT 1,
            window_start {real_t}
        );""",
        f"""CREATE TABLE IF NOT EXISTS media_hashes (
            tenant_id TEXT,
            file_hash TEXT,
            media_kind TEXT,
            vid TEXT,
            created_at {real_t},
            PRIMARY KEY (tenant_id, file_hash)
        );""",
        f"""CREATE TABLE IF NOT EXISTS face_embeddings (
            id {auto_id},
            tenant_id TEXT,
            reference_id TEXT,
            vid TEXT,
            face_hash TEXT,
            embedding_json TEXT,
            created_at {real_t}
        );""",
        # Interview product tables
        f"""CREATE TABLE IF NOT EXISTS interviews (
            id TEXT PRIMARY KEY,
            tenant_id TEXT,
            candidate_id TEXT,
            token_hash TEXT,
            expires_at {real_t},
            status TEXT DEFAULT 'active',
            face_baseline TEXT,
            speaker_id TEXT,
            metadata TEXT,
            created_at {real_t},
            updated_at {real_t}
        );""",
        f"""CREATE TABLE IF NOT EXISTS interview_clips (
            id TEXT PRIMARY KEY,
            interview_id TEXT,
            round INTEGER,
            status TEXT DEFAULT 'processing',
            results TEXT,
            recommendation TEXT,
            action TEXT,
            metadata TEXT,
            video_path TEXT,
            audio_path TEXT,
            created_at {real_t}
        );"""
    ]
    for stmt in stmts:
        if is_postgres:
            c.execute(stmt)
        else:
            c.executescript(stmt)


def migration_0003_performance_indexes(c: Any, is_postgres: bool) -> None:
    stmts = [
        "CREATE INDEX IF NOT EXISTS idx_ver_tenant ON verifications(tenant_id, created_at);",
        "CREATE INDEX IF NOT EXISTS idx_ver_ref ON verifications(tenant_id, reference_id);",
        "CREATE INDEX IF NOT EXISTS idx_otp_vid ON otps(vid, channel);",
        "CREATE INDEX IF NOT EXISTS idx_pipe_status ON pipeline_jobs(status, created_at);",
        "CREATE INDEX IF NOT EXISTS idx_face_emb ON face_embeddings(tenant_id, reference_id);",
        "CREATE INDEX IF NOT EXISTS idx_interview_tenant ON interviews(tenant_id, created_at);",
        "CREATE INDEX IF NOT EXISTS idx_clip_interview ON interview_clips(interview_id, round);",
        "CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash);",
        "CREATE INDEX IF NOT EXISTS idx_api_keys_tenant ON api_keys(tenant_id);"
    ]
    for stmt in stmts:
        if is_postgres:
            c.execute(stmt)
        else:
            c.executescript(stmt)


MIGRATIONS: List[Tuple[str, str, Callable]] = [
    ("0001", "core_and_products", migration_0001_core_and_products),
    ("0002", "product_tables", migration_0002_product_tables),
    ("0003", "performance_indexes", migration_0003_performance_indexes),
]


def run_migrations(c: Any, is_postgres: bool = False) -> List[str]:
    """Run all pending versioned migrations in order."""
    ensure_migrations_table(c, is_postgres)

    if is_postgres:
        applied_rows = c.execute("SELECT version FROM schema_migrations;").fetchall()
    else:
        applied_rows = c.execute("SELECT version FROM schema_migrations").fetchall()

    applied = {row[0] if isinstance(row, (list, tuple)) else row["version"] for row in applied_rows}
    newly_applied = []

    now = time.time()
    for version, name, fn in MIGRATIONS:
        if version not in applied:
            logger.info(f"Applying database migration {version}_{name}...")
            fn(c, is_postgres)
            c.execute(
                "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                (version, name, now)
            )
            newly_applied.append(f"{version}_{name}")

    return newly_applied


def get_applied_migrations(c: Any) -> List[str]:
    """Return all applied migration version_name identifiers."""
    rows = c.execute("SELECT version, name FROM schema_migrations ORDER BY version ASC").fetchall()
    return [f"{r[0]}_{r[1]}" if isinstance(r, (list, tuple)) else f"{r['version']}_{r['name']}" for r in rows]
