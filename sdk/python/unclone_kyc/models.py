from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class VerificationSession:
    id: str
    status: str
    policy: str
    expires_at: float
    flow_url: str

    @classmethod
    def from_dict(cls, data: dict) -> "VerificationSession":
        return cls(
            id=data["id"],
            status=data["status"],
            policy=data["policy"],
            expires_at=float(data["expires_at"]),
            flow_url=data["flow_url"],
        )


@dataclass
class VerificationResult:
    id: str
    reference_id: str
    status: str
    policy: str
    decision: Optional[str]
    final_decision: Optional[str]
    trust: Optional[float]
    reasons: List[str] = field(default_factory=list)
    results: List[Dict[str, Any]] = field(default_factory=list)
    review: Optional[Dict[str, Any]] = None
    webhook: Optional[Dict[str, Any]] = None
    created_at: float = 0.0
    updated_at: float = 0.0

    @classmethod
    def from_dict(cls, data: dict) -> "VerificationResult":
        return cls(
            id=data["id"],
            reference_id=data.get("reference_id", ""),
            status=data.get("status", ""),
            policy=data.get("policy", ""),
            decision=data.get("decision"),
            final_decision=data.get("final_decision") or data.get("decision"),
            trust=data.get("trust"),
            reasons=data.get("reasons") or [],
            results=data.get("results") or [],
            review=data.get("review"),
            webhook=data.get("webhook"),
            created_at=float(data.get("created_at", 0.0)),
            updated_at=float(data.get("updated_at", 0.0)),
        )
