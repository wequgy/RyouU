class KycError(Exception):
    """Base exception for Unclone KYC SDK errors."""
    def __init__(self, message: str, status_code: int = None, details: dict = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class AuthenticationError(KycError):
    """Raised when an API key is missing or invalid (HTTP 401)."""
    pass


class NotFoundError(KycError):
    """Raised when a verification or resource does not exist (HTTP 404)."""
    pass


class ConflictError(KycError):
    """Raised when an operation conflicts with the current resource state (HTTP 409)."""
    pass


class RateLimitError(KycError):
    """Raised when rate limits are exceeded (HTTP 429)."""
    pass


class WebhookVerificationError(KycError):
    """Raised when a webhook signature fails verification or has expired."""
    pass
