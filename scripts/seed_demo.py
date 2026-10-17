"""Seed demo tenants and credentials for local evaluation.

Usage:
  python -m scripts.seed_demo
"""
from app import db
from app.config import get_settings


def main():
    s = get_settings()
    db.init_db()
    db.seed_demo_tenants()
    print("=" * 60)
    print("Demo tenants seeded successfully!")
    print("=" * 60)
    print("Tenant 1 (Strict Policy):")
    print("  Tenant ID:   demo_strict")
    print("  API Key:     kyc_demo_strict_key")
    print("  Policy:      strict")
    print("  Webhook:     " + s.demo_webhook_url)
    print()
    print("Tenant 2 (Lenient Policy):")
    print("  Tenant ID:   demo_lenient")
    print("  API Key:     kyc_demo_lenient_key")
    print("  Policy:      lenient")
    print("  Webhook:     " + s.demo_webhook_url)
    print("=" * 60)


if __name__ == "__main__":
    main()
