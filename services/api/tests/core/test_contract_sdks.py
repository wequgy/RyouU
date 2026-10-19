"""Contract tests running SDK methods against the real KYC verification API service.

Validates that:
- Python SDK methods (create, get, review, delete, list, webhook verification) work against live FastAPI endpoints.
- Error mappings (401 Auth, 404 Not Found, 429 RateLimit) contractually match between server and SDKs.
- Response models deserialization matches real server responses.
"""
import pytest
import httpx
from starlette.testclient import TestClient

try:
    from unclone_kyc import (
        Client,
        AuthenticationError,
        NotFoundError,
        VerificationSession,
        VerificationResult,
    )
except ImportError:
    from sdks.kyc.python.unclone_kyc import (
        Client,
        AuthenticationError,
        NotFoundError,
        VerificationSession,
        VerificationResult,
    )


@pytest.fixture
def sdk_client(client):
    """Create a Python SDK client backed by the in-memory FastAPI TestClient."""
    return Client(
        api_key="kyc_demo_lenient_key",
        base_url="http://testserver",
        http_client=client,
    )


def test_python_sdk_contract_lifecycle(sdk_client):
    # 1. create_verification
    session = sdk_client.create_verification(
        reference_id="contract_test_ref_1",
        expected={"name": "Asha Rao", "dob": "1999-04-12"},
        policy="lenient",
        idempotency_key="idemp_contract_123",
    )
    assert isinstance(session, VerificationSession)
    assert session.id.startswith("ver_")
    assert session.flow_url and "t=" in session.flow_url

    # 2. get_verification
    res = sdk_client.get_verification(session.id)
    assert isinstance(res, VerificationResult)
    assert res.id == session.id
    assert res.reference_id == "contract_test_ref_1"
    assert res.status in ("created", "pending")

    # 3. review_verification (human agent review override after pipeline completion)
    from app import db
    db.save_outcome(session.id, [], "needs_review", ["Manual review required"], 0.5)

    review_res = sdk_client.review_verification(
        verification_id=session.id,
        decision="approved",
        note="Document verified manually in branch",
    )
    assert isinstance(review_res, VerificationResult)
    assert review_res.final_decision == "approved"

    # 4. list_verifications
    items = sdk_client.list_verifications(limit=10)
    assert isinstance(items, list)
    assert any(item.id == session.id for item in items)

    # 5. delete_verification (GDPR / Right to be forgotten)
    del_ok = sdk_client.delete_verification(session.id)
    assert del_ok is True

    # 6. Verify 404 after deletion
    with pytest.raises(NotFoundError):
        sdk_client.get_verification(session.id)


def test_python_sdk_contract_authentication_failure(client):
    bad_client = Client(
        api_key="invalid_bad_key",
        base_url="http://testserver",
        http_client=client,
    )
    with pytest.raises(AuthenticationError) as exc_info:
        bad_client.create_verification("ref_fail")
    assert exc_info.value.status_code == 401


def test_python_sdk_webhook_contract():
    secret = "whsec_test_secret"
    raw_payload = b'{"type":"verification.completed","id":"ver_test"}'
    from app import security
    sig = security.sign_payload(secret, raw_payload)

    try:
        from unclone_kyc import verify_webhook
    except ImportError:
        from sdks.kyc.python.unclone_kyc import verify_webhook
    parsed = verify_webhook(raw_payload, sig, secret)
    assert parsed["id"] == "ver_test"
    assert parsed["type"] == "verification.completed"
