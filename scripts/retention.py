"""CLI tool to execute data retention cleanup.

  python -m scripts.retention --max-age-days 30
"""
import argparse

from app import db, retention


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-age-days", type=float, default=30.0, help="Maximum age in days")
    ap.add_argument("--max-age-seconds", type=float, default=None, help="Maximum age in seconds")
    args = ap.parse_args()

    db.init_db()
    max_age_s = args.max_age_seconds if args.max_age_seconds is not None else args.max_age_days * 86400
    cleaned = retention.cleanup_expired_verifications(max_age_s)
    print(f"Retention cleanup complete: {cleaned} expired verifications removed.")


if __name__ == "__main__":
    main()
