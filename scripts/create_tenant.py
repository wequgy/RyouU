"""Create or update a customer (tenant) and administer credentials.
The API key is shown ONCE; only its SHA-256 hash is stored.

Examples:
  # Create tenant:
  python -m scripts.create_tenant --id acme --name "Acme Bank" --policy strict --webhook-url https://acme.example/kyc-hook

  # Rotate API key:
  python -m scripts.create_tenant --id acme --rotate-key

  # Rotate webhook secret:
  python -m scripts.create_tenant --id acme --rotate-secret

  # Update webhook URL:
  python -m scripts.create_tenant --id acme --webhook-url https://new.acme.example/hook
"""
import argparse
import secrets

from app import db


def main():
    ap = argparse.ArgumentParser(description="Tenant administration and key rotation")
    ap.add_argument("--id", required=True, help="Tenant ID (e.g. acme)")
    ap.add_argument("--name", default=None, help="Tenant display name")
    ap.add_argument("--policy", default=None, choices=["strict", "lenient"], help="Default verification policy")
    ap.add_argument("--webhook-url", default=None, help="Customer webhook endpoint URL")
    ap.add_argument("--rotate-key", action="store_true", help="Rotate the tenant's API key")
    ap.add_argument("--rotate-secret", action="store_true", help="Rotate the tenant's webhook signing secret")

    a = ap.parse_args()
    db.init_db()
    existing = db.tenant_by_id(a.id)

    if a.rotate_key:
        if not existing:
            print(f"Error: Tenant '{a.id}' does not exist.")
            return
        new_key = "kyc_live_" + secrets.token_urlsafe(32)
        db.rotate_tenant_api_key(a.id, new_key)
        print(f"Tenant:         {a.id}")
        print(f"NEW API Key:    {new_key}")
        print("(Store this key now. It cannot be recovered or shown again.)")
        return

    if a.rotate_secret:
        if not existing:
            print(f"Error: Tenant '{a.id}' does not exist.")
            return
        new_secret = "whsec_" + secrets.token_urlsafe(32)
        db.rotate_tenant_webhook_secret(a.id, new_secret)
        print(f"Tenant:             {a.id}")
        print(f"NEW Webhook Secret: {new_secret}")
        return

    if existing and not a.name:
        # Updating existing tenant fields
        if a.webhook_url is not None:
            db.update_tenant_webhook_url(a.id, a.webhook_url)
            print(f"Updated webhook URL for tenant '{a.id}': {a.webhook_url}")
        if a.policy is not None:
            db.update_tenant_policy(a.id, a.policy)
            print(f"Updated default policy for tenant '{a.id}': {a.policy}")
        return

    # Creating or upserting tenant
    name = a.name or (existing["name"] if existing else a.id)
    policy = a.policy or (existing["default_policy"] if existing else "strict")
    webhook_url = a.webhook_url if a.webhook_url is not None else (existing["webhook_url"] if existing else "")
    key = "kyc_live_" + secrets.token_urlsafe(32)
    secret = "whsec_" + secrets.token_urlsafe(32)

    db.upsert_tenant(a.id, name, key, webhook_url, secret, policy)
    print(f"Tenant:          {a.id}")
    print(f"Name:            {name}")
    print(f"Policy:          {policy}")
    print(f"Webhook URL:     {webhook_url or '(none)'}")
    print(f"API Key:         {key}")
    print(f"Webhook Secret:  {secret}")
    print("(Store these credentials now; the API key cannot be shown again.)")


if __name__ == "__main__":
    main()
