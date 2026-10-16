"""Run the checks, decide, store, notify."""
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import db, webhooks
from .checks import base as registry
from .config import get_settings
from .models import FAIL, PASS, SKIPPED, UNCERTAIN, CheckContext, CheckResult
from .policies import checks_for, get_policy


def build_context(v: dict, policy: dict) -> CheckContext:
    files = {k: Path(p) for k, p in (v["data"].get("files") or {}).items()}
    return CheckContext(session_id=v["id"], data=v["data"], files=files, policy=policy, settings=get_settings())


def run_one(name: str, ctx: CheckContext) -> CheckResult:
    fn = registry.get(name)
    if fn is None:
        return CheckResult.uncertain(name, "Check is not available on this server")
    t0 = time.time()
    try:
        r = fn(ctx)
    except Exception as e:  # a crashing check must never approve anyone
        traceback.print_exc()
        r = CheckResult.uncertain(name, f"Check crashed: {type(e).__name__}: {e}")
    r.details = dict(r.details or {}, duration_ms=int((time.time() - t0) * 1000))
    return r


def run_checks(ctx: CheckContext, names: list) -> list:
    with ThreadPoolExecutor(max_workers=4) as pool:
        return list(pool.map(lambda n: run_one(n, ctx), names))


def _trust(results: list):
    """Confidence-weighted mean of trust scores over checks that actually ran."""
    live = [r for r in results if r.status != SKIPPED and r.confidence > 0]
    total = sum(r.confidence for r in live)
    return round(sum(r.score * r.confidence for r in live) / total, 4) if total else None


def decide(policy: dict, results: list) -> dict:
    """Map check results to approved / needs_review / rejected_recommended, always with reasons."""
    by = {r.name: r for r in results}
    hard = [f"{n}: {by[n].reason}" for n in policy["reject_on_fail"] if n in by and by[n].status == FAIL]
    if hard:
        return {"decision": "rejected_recommended", "reasons": hard, "trust": _trust(results)}
    other_fails = [f"{r.name}: {r.reason}" for r in results if r.status == FAIL]
    if other_fails:
        return {"decision": "needs_review", "reasons": other_fails, "trust": _trust(results)}
    blockers = [f"{n}: {by[n].reason}" if n in by else f"{n}: missing"
                for n in policy.get("must_pass", []) if n not in by or by[n].status != PASS]
    if blockers:
        return {"decision": "needs_review", "reasons": blockers, "trust": _trust(results)}
    weak = [n for n in policy["required"] if n not in by or by[n].status in (UNCERTAIN, SKIPPED)]
    if len(weak) > policy["max_uncertain_required"]:
        why = [f"{n}: {by[n].reason}" if n in by else f"{n}: missing" for n in weak]
        return {"decision": "needs_review", "reasons": why, "trust": _trust(results)}
    reasons = [f"{n}: {by[n].reason} (accepted as uncertain)" for n in weak]
    return {"decision": "approved", "reasons": reasons, "trust": _trust(results)}


def public_view(v: dict) -> dict:
    """What API customers see. Never includes tokens, file paths or raw uploads."""
    review = v.get("review")
    return {
        "id": v["id"], "reference_id": v["reference_id"], "status": v["status"], "policy": v["policy"],
        "decision": v["decision"], "final_decision": review["decision"] if review else v["decision"],
        "trust": v["trust"], "reasons": v["reasons"], "results": v["results"], "review": review,
        "webhook": v["webhook"], "created_at": v["created_at"], "updated_at": v["updated_at"],
    }


def process(vid: str) -> None:
    """Background entry point (called after /submit)."""
    v = db.get_verification(vid)
    tenant = db.tenant_by_id(v["tenant_id"])
    try:
        policy = get_policy(v["policy"])
        ctx = build_context(v, policy)
        results = run_checks(ctx, checks_for(policy))
        outcome = decide(policy, results)
        db.save_outcome(vid, [r.to_dict() for r in results], outcome["decision"], outcome["reasons"], outcome["trust"])
    except Exception as e:  # never leave a session stuck in 'processing', never approve on error
        traceback.print_exc()
        db.save_outcome(vid, [], "needs_review", [f"internal error: {type(e).__name__}"], None)
    status = webhooks.deliver(tenant, "verification.completed", public_view(db.get_verification(vid)))
    db.save_webhook_status(vid, status)
