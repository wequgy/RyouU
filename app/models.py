from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from pydantic import BaseModel, Field

# Check statuses
PASS, FAIL, UNCERTAIN, SKIPPED = "pass", "fail", "uncertain", "skipped"


@dataclass
class CheckResult:
    """The contract every check returns. The decision engine reads only this.

    score:      TRUST score. 1.0 = strongly genuine, 0.0 = strongly suspicious.
                (Detectif returns a fake-probability, so we store 1 - that.)
    confidence: how much to trust the score itself (0..1).
    """

    name: str
    status: str
    score: float
    confidence: float
    reason: str
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def passed(cls, name, reason, score=1.0, confidence=0.8, **details):
        return cls(name, PASS, float(score), float(confidence), reason, details)

    @classmethod
    def failed(cls, name, reason, score=0.0, confidence=0.8, **details):
        return cls(name, FAIL, float(score), float(confidence), reason, details)

    @classmethod
    def uncertain(cls, name, reason, score=0.5, confidence=0.2, **details):
        return cls(name, UNCERTAIN, float(score), float(confidence), reason, details)

    @classmethod
    def skipped(cls, name, reason, **details):
        return cls(name, SKIPPED, 0.5, 0.0, reason, details)


@dataclass
class CheckContext:
    session_id: str
    data: dict          # session data: expected, signals, verified, challenges...
    files: dict         # kind -> Path of uploaded files
    policy: dict
    settings: Any


# ---------- API request models ----------
class Expected(BaseModel):
    """Details the tenant already knows (or OCR extracted) to compare spoken answers against."""
    name: Optional[str] = None
    dob: Optional[str] = None         # e.g. 1999-04-12
    id_last4: Optional[str] = None


class CreateVerification(BaseModel):
    reference_id: Optional[str] = Field(default=None, max_length=128)
    policy: Optional[str] = None
    redirect_url: Optional[str] = None
    expected: Expected = Field(default_factory=Expected)


class OtpSend(BaseModel):
    channel: str                      # email | phone
    destination: str = Field(max_length=254)


class OtpVerify(BaseModel):
    channel: str
    code: str = Field(max_length=12)


class ChallengeResultItem(BaseModel):
    id: str
    metrics: dict = Field(default_factory=dict)


class ChallengeResults(BaseModel):
    results: list[ChallengeResultItem]


class Signals(BaseModel):
    """Client-side signals from the verification page. UNTRUSTED: treat as hints, not proof."""
    camera_labels: list[str] = Field(default_factory=list)
    screen_share_attempted: bool = False
    focus_loss_count: int = 0
    extended_display: bool = False
    fullscreen_exited: bool = False
    camera_settings: dict = Field(default_factory=dict)


class ReviewBody(BaseModel):
    decision: str                     # approved | rejected
    note: Optional[str] = Field(default=None, max_length=1000)
