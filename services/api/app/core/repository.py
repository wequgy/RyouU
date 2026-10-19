"""Core repository: Tenants, API keys, audit log, and consent."""
import json
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple


def _j(x: Any) -> str:
    return json.dumps(x, separators=(",", ":"))


def _j_load(val: Any, default=None):
    if val is None:
        return default
    if isinstance(val, (list, dict)):
        return val
    try:
        return json.loads(val)
    except Exception:
        return default


def _row(row: Any) -> Optional[dict]:
    return dict(row) if row else None


# ---------------- Tenants ----------------
def upsert_tenant(conn_fn, tenant_id: str, name: str, api_key: str, webhook_url: Optional[str],
                  webhook_secret: Optional[str], default_policy: str = "lenient",
                  products: Optional[List[str]] = None) -> None:
    from app.security import hash_key
    prods = products or ["kyc", "interview"]
    with conn_fn() as c:
        c.execute(
            """INSERT INTO tenants (id, name, api_key_hash, webhook_url, webhook_secret, default_policy, products, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET name=excluded.name, api_key_hash=excluded.api_key_hash,
               webhook_url=excluded.webhook_url, webhook_secret=excluded.webhook_secret,
               default_policy=excluded.default_policy, products=excluded.products""",
            (tenant_id, name, hash_key(api_key), webhook_url, webhook_secret, default_policy, _j(prods), time.time()),
        )


def rotate_tenant_api_key(conn_fn, tenant_id: str, new_api_key: str) -> None:
    from app.security import hash_key
    with conn_fn() as c:
        c.execute("UPDATE tenants SET api_key_hash=? WHERE id=?", (hash_key(new_api_key), tenant_id))


def rotate_tenant_webhook_secret(conn_fn, tenant_id: str, new_secret: str) -> None:
    with conn_fn() as c:
        c.execute("UPDATE tenants SET webhook_secret=? WHERE id=?", (new_secret, tenant_id))


def update_tenant_webhook_url(conn_fn, tenant_id: str, new_url: str) -> None:
    with conn_fn() as c:
        c.execute("UPDATE tenants SET webhook_url=? WHERE id=?", (new_url, tenant_id))


def update_tenant_policy(conn_fn, tenant_id: str, default_policy: str) -> None:
    with conn_fn() as c:
        c.execute("UPDATE tenants SET default_policy=? WHERE id=?", (default_policy, tenant_id))


def tenant_by_api_key(conn_fn, key: str) -> Optional[dict]:
    from app.security import hash_key
    h = hash_key(key)
    now = time.time()
    with conn_fn() as c:
        # 1. Scoped api_keys table check
        row_key = c.execute(
            "SELECT * FROM api_keys WHERE key_hash=? AND revoked=0 AND (expires_at IS NULL OR expires_at > ?)",
            (h, now)
        ).fetchone()
        if row_key:
            parsed_key = _row(row_key)
            t = _row(c.execute("SELECT * FROM tenants WHERE id=?", (parsed_key["tenant_id"],)).fetchone())
            if t:
                t["key_scopes"] = _j_load(parsed_key.get("scopes")) or []
                t["api_key_id"] = parsed_key["id"]
                t["products"] = _j_load(t.get("products")) or ["kyc", "interview"]
                return t

        # 2. Primary / Legacy tenant key
        t_row = c.execute("SELECT * FROM tenants WHERE api_key_hash=?", (h,)).fetchone()
        if t_row:
            t = _row(t_row)
            t["key_scopes"] = ["admin:*", "kyc:*", "interview:*"]
            t["api_key_id"] = "primary"
            t["products"] = _j_load(t.get("products")) or ["kyc", "interview"]
            return t
        return None


def tenant_by_id(conn_fn, tenant_id: str) -> Optional[dict]:
    with conn_fn() as c:
        t = _row(c.execute("SELECT * FROM tenants WHERE id=?", (tenant_id,)).fetchone())
        if t:
            t["products"] = _j_load(t.get("products")) or ["kyc", "interview"]
            t.setdefault("key_scopes", ["admin:*", "kyc:*", "interview:*"])
        return t


def seed_demo_tenants(conn_fn, demo_webhook_url: str, demo_webhook_secret: str) -> None:
    upsert_tenant(conn_fn, "demo_lenient", "Demo Fintech (lenient policy)", "kyc_demo_lenient_key",
                  demo_webhook_url, demo_webhook_secret, "lenient", ["kyc", "interview"])
    upsert_tenant(conn_fn, "demo_strict", "Demo Bank (strict policy)", "kyc_demo_strict_key",
                  demo_webhook_url, demo_webhook_secret, "strict", ["kyc", "interview"])


# ---------------- Scoped API Keys ----------------
def create_api_key(conn_fn, tenant_id: str, scopes: List[str], expires_in_s: Optional[float] = None) -> Tuple[str, dict]:
    from app.security import new_token, hash_key
    raw_key = "unclone_" + new_token()
    h = hash_key(raw_key)
    prefix = raw_key[:12] + "..."
    now = time.time()
    expires_at = (now + expires_in_s) if expires_in_s else None
    key_id = "key_" + uuid.uuid4().hex[:16]
    with conn_fn() as c:
        c.execute(
            """INSERT INTO api_keys (id, tenant_id, key_hash, prefix, scopes, revoked, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?, 0, ?, ?)""",
            (key_id, tenant_id, h, prefix, _j(scopes), now, expires_at)
        )
    return raw_key, get_api_key(conn_fn, key_id)


def revoke_api_key(conn_fn, tenant_id: str, key_id: str) -> bool:
    with conn_fn() as c:
        cur = c.execute("UPDATE api_keys SET revoked=1 WHERE id=? AND tenant_id=?", (key_id, tenant_id))
        return bool(cur.rowcount > 0)


def get_api_key(conn_fn, key_id: str) -> Optional[dict]:
    with conn_fn() as c:
        r = c.execute("SELECT * FROM api_keys WHERE id=?", (key_id,)).fetchone()
        if not r:
            return None
        d = _row(r)
        d["scopes"] = _j_load(d.get("scopes")) or []
        return d


def list_api_keys(conn_fn, tenant_id: str) -> List[dict]:
    with conn_fn() as c:
        rows = c.execute(
            "SELECT id, tenant_id, prefix, scopes, revoked, created_at, expires_at FROM api_keys WHERE tenant_id=?",
            (tenant_id,)
        ).fetchall()
        result = []
        for r in rows:
            d = _row(r)
            d["scopes"] = _j_load(d.get("scopes")) or []
            result.append(d)
        return result


# ---------------- Audit Log & Consent ----------------
def record_audit(conn_fn, tenant_id: str, action: str, resource_type: str, resource_id: str, details: dict = None) -> str:
    audit_id = "aud_" + uuid.uuid4().hex[:16]
    now = time.time()
    with conn_fn() as c:
        c.execute(
            """INSERT INTO audit_log (id, tenant_id, action, resource_type, resource_id, details, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (audit_id, tenant_id, action, resource_type, resource_id, _j(details or {}), now)
        )
    return audit_id


def record_consent(conn_fn, tenant_id: str, reference_id: str, consent_type: str, granted: bool = True,
                   ip_address: str = "", user_agent: str = "") -> str:
    consent_id = "cst_" + uuid.uuid4().hex[:16]
    now = time.time()
    with conn_fn() as c:
        c.execute(
            """INSERT INTO consent (id, tenant_id, reference_id, consent_type, granted, ip_address, user_agent, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (consent_id, tenant_id, reference_id, consent_type, 1 if granted else 0, ip_address, user_agent, now)
        )
    return consent_id
