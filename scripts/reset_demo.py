"""Reset the local KYC database and re-seed demo tenants.

Usage:
  python -m scripts.reset_demo
"""
import shutil
from pathlib import Path
from app import db
from app.config import get_settings


def main():
    s = get_settings()
    print("Resetting database and upload storage...")
    if s.db_path.exists():
        s.db_path.unlink()
        print(f"Removed {s.db_path}")

    uploads_dir = s.data_dir / "uploads"
    if uploads_dir.exists():
        shutil.rmtree(uploads_dir, ignore_errors=True)
        print(f"Cleared {uploads_dir}")

    db.init_db()
    db.seed_demo_tenants()
    print("Database reinitialized and demo tenants reseeded cleanly!")


if __name__ == "__main__":
    main()
