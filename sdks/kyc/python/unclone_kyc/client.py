import time
from typing import Any, Dict, List, Optional

import httpx

from .exceptions import (
    AuthenticationError,
    ConflictError,
    KycError,
    NotFoundError,
    RateLimitError,
)
from .models import VerificationResult, VerificationSession
from .webhook import verify_webhook as _verify_webhook


class Client:
    """Unclone KYC Python API Client.

    Example:
        kyc = Client(api_key="kyc_live_...", base_url="https://api.unclone.ai")
        session = kyc.create_verification("user_123", expected={"name": "Alex Smith"})
        print(session.flow_url)
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "http://localhost:8000",
        timeout: float = 10.0,
        max_retries: int = 3,
        http_client: Optional[httpx.Client] = None,
    ):
        if not api_key:
            raise ValueError("api_key must be provided")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self._custom_client = http_client

    def _client(self) -> httpx.Client:
        if self._custom_client is not None:
            return self._custom_client
        return httpx.Client(timeout=self.timeout)

    def _request(
        self,
        method: str,
        path: str,
        json_body: Optional[dict] = None,
        headers: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> httpx.Response:
        url = f"{self.base_url}{path}"
        req_headers = {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "UncloneKycPython/0.1.0",
        }
        if headers:
            req_headers.update(headers)

        last_exc = None
        for attempt in range(1, self.max_retries + 1):
            try:
                client = self._client()
                resp = client.request(method, url, json=json_body, headers=req_headers, params=params)
                def _safe_json():
                    try:
                        return resp.json()
                    except Exception:
                        return {"raw": resp.text}

                if resp.status_code == 401:
                    raise AuthenticationError("Invalid or missing API key", 401, _safe_json())
                if resp.status_code == 404:
                    raise NotFoundError(f"Resource not found: {path}", 404, _safe_json())
                if resp.status_code == 409:
                    raise ConflictError(f"Conflict error: {resp.text}", 409, _safe_json())
                if resp.status_code == 429:
                    raise RateLimitError("Rate limit exceeded", 429, _safe_json())
                if resp.status_code >= 500:
                    if attempt < self.max_retries:
                        time.sleep(0.2 * (2 ** (attempt - 1)))
                        continue
                    raise KycError(f"Server error HTTP {resp.status_code}: {resp.text}", resp.status_code)
                if resp.status_code >= 400:
                    raise KycError(f"API error HTTP {resp.status_code}: {resp.text}", resp.status_code)
                return resp
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    time.sleep(0.2 * (2 ** (attempt - 1)))
                    continue
                raise KycError(f"Network error after {self.max_retries} attempts: {exc}") from exc

        raise KycError(f"Request failed: {last_exc}")

    def create_verification(
        self,
        reference_id: str,
        expected: Optional[dict] = None,
        policy: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> VerificationSession:
        """Create a new verification session.

        Args:
            reference_id: Customer's unique identifier for the user.
            expected: Optional dict of expected user details (e.g. name, dob, id_last4).
            policy: 'strict' or 'lenient' (defaults to tenant default).
            idempotency_key: Optional idempotency key for safe retries.

        Returns:
            VerificationSession with session id and flow_url.
        """
        payload = {
            "reference_id": reference_id,
            "expected": expected or {},
        }
        if policy:
            payload["policy"] = policy

        headers = {}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        resp = self._request("POST", "/v1/verifications", json_body=payload, headers=headers)
        return VerificationSession.from_dict(resp.json())

    def get_verification(self, verification_id: str) -> VerificationResult:
        """Retrieve verification status and decision results."""
        resp = self._request("GET", f"/v1/verifications/{verification_id}")
        return VerificationResult.from_dict(resp.json())

    def list_verifications(self, limit: int = 50) -> List[VerificationResult]:
        """List recent verifications."""
        resp = self._request("GET", "/v1/verifications", params={"limit": limit})
        items = resp.json().get("data", [])
        return [VerificationResult.from_dict(item) for item in items]

    def delete_verification(self, verification_id: str) -> bool:
        """Delete verification record and purge uploaded evidence."""
        self._request("DELETE", f"/v1/verifications/{verification_id}")
        return True

    def review_verification(
        self,
        verification_id: str,
        decision: str,
        note: Optional[str] = None,
    ) -> VerificationResult:
        """Submit a manual human review decision ('approved' or 'rejected')."""
        payload = {"decision": decision}
        if note:
            payload["note"] = note
        resp = self._request("POST", f"/v1/verifications/{verification_id}/review", json_body=payload)
        return VerificationResult.from_dict(resp.json())

    def get_evidence(self, verification_id: str) -> dict:
        """Retrieve signed URLs for verification evidence artifacts."""
        resp = self._request("GET", f"/v1/verifications/{verification_id}/evidence")
        return resp.json()

    @staticmethod
    def verify_webhook(
        body: bytes,
        signature_header: str,
        secret: str,
        tolerance_s: int = 300,
    ) -> dict:
        """Verify an incoming webhook event signature."""
        return _verify_webhook(body, signature_header, secret, tolerance_s=tolerance_s)
