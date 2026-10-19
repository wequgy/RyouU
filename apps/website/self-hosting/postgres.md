---
title: PostgreSQL & Database Migrations
description: Configuring relational storage with PostgreSQL, Alembic schema migrations, and backup strategies.
---

While RyouU can run locally on SQLite for lightweight testing, production deployments require PostgreSQL 14+ for connection pooling, concurrent verification locks, and high availability.

---

## 1. Connecting to PostgreSQL

Set the `DATABASE_URL` environment variable:

```ini
DATABASE_URL=postgresql://kyc_user:secure_password@postgres.internal:5432/kyc_production
```

---

## 2. Applying Schema Migrations

RyouU manages database schemas using Alembic. Apply pending schema migrations before starting the API server:

```bash
# Run database migrations up to the latest revision
alembic upgrade head
```

To verify the current migration state:

```bash
alembic current
```

---

## 3. Database Schema Overview

Key tables in the RyouU schema:

- **`tenants`**: Registered customer organizations, Argon2-hashed API keys, and webhook signing secrets.
- **`verifications`**: Core verification sessions, expected profile inputs, current statuses, decision recommendations, and `final_decision` overrides.
- **`verification_checks`**: Individual check execution results (`pass`, `fail`, `uncertain`, `skipped`), continuous scores, and diagnostic reasons.
- **`verification_evidence`**: Metadata, SHA-256 hashes, and storage paths for captured document and selfie assets.
- **`audit_logs`**: Immutable, append-only logs recording reviewer actions, IP addresses, and state changes.

---

## 4. Backups and High Availability

- **Automated Snapshots**: Schedule daily `pg_dump` backups or utilize managed cloud backups (AWS RDS, GCP Cloud SQL, Supabase).
- **WAL Archiving**: For enterprise recovery point objectives (RPO &lt; 5 minutes), enable continuous Write-Ahead Log (WAL) archiving to an isolated storage bucket.
