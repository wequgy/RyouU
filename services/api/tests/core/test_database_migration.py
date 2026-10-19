"""Test upgrading an old legacy database schema to the latest versioned migration state."""
import sqlite3
import time
from pathlib import Path

from app.migrations.runner import run_migrations, get_applied_migrations


OLD_LEGACY_SCHEMA = """
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


def test_upgrade_legacy_database(tmp_path: Path):
    db_file = tmp_path / "legacy_test.db"
    
    # 1. Initialize legacy schema with existing data
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    conn.executescript(OLD_LEGACY_SCHEMA)
    
    now = time.time()
    conn.execute(
        "INSERT INTO tenants (id, name, api_key_hash, webhook_url, webhook_secret, default_policy, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("legacy_tenant_1", "Legacy Corp", "hash_old_key", "https://old.hook", "old_sec", "lenient", now)
    )
    conn.execute(
        "INSERT INTO verifications (id, tenant_id, reference_id, policy, status, flow_token_hash, expires_at, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("ver_legacy_1", "legacy_tenant_1", "ref_1", "lenient", "created", "hash_flow", now + 600, now, now)
    )
    conn.commit()
    
    # 2. Run versioned migrations
    applied = run_migrations(conn, is_postgres=False)
    assert len(applied) >= 3
    
    # 3. Verify schema migrations table
    applied_stored = get_applied_migrations(conn)
    assert "0001_core_and_products" in applied_stored
    assert "0002_product_tables" in applied_stored
    assert "0003_performance_indexes" in applied_stored
    
    # 4. Verify existing data preserved
    t_row = conn.execute("SELECT * FROM tenants WHERE id='legacy_tenant_1'").fetchone()
    assert t_row is not None
    assert t_row["name"] == "Legacy Corp"
    # Column 'products' should exist
    assert "products" in t_row.keys()
    
    v_row = conn.execute("SELECT * FROM verifications WHERE id='ver_legacy_1'").fetchone()
    assert v_row is not None
    assert v_row["reference_id"] == "ref_1"
    
    # 5. Verify new tables exist and are queryable
    for table in ["api_keys", "audit_log", "consent", "interviews", "interview_clips", "pipeline_jobs", "media_hashes"]:
        cur = conn.execute(f"SELECT COUNT(*) FROM {table}")
        assert cur.fetchone()[0] == 0
        
    conn.close()
