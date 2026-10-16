from app import pipeline, security
from app.models import CheckResult
from app.policies import POLICIES


def test_signature_roundtrip_tamper_and_replay():
    body = b'{"x":1}'
    h = security.sign_payload("sec", body, ts=1000)
    assert security.verify_signature("sec", body, h, now=1100)
    assert not security.verify_signature("sec", b'{"x":2}', h, now=1100)      # tampered body
    assert not security.verify_signature("other", body, h, now=1100)          # wrong secret
    assert not security.verify_signature("sec", body, h, now=1000 + 3600)     # replay too old
    assert not security.verify_signature("sec", body, "garbage", now=1100)


def R(name, status, score=0.5, conf=0.5):
    return CheckResult(name, status, score, conf, f"{name} {status}")


def all_pass(policy):
    return [R(n, "pass", 1.0) for n in policy["required"] + policy["optional"]]


def test_all_pass_is_approved():
    for p in POLICIES.values():
        res = [r for r in all_pass(p) if r.name != "video_deepfake"]
        assert pipeline.decide(p, res)["decision"] == "approved"


def test_face_fail_is_rejected_recommended_in_both_policies():
    for p in POLICIES.values():
        res = [R("face_match", "fail", 0.0)] + [R(n, "pass", 1.0) for n in p["required"] if n != "face_match"]
        out = pipeline.decide(p, res)
        assert out["decision"] == "rejected_recommended" and "face_match" in out["reasons"][0]


def test_voice_fail_differs_by_policy():
    def results(p):
        return [R("voice_ai", "fail", 0.0)] + [R(n, "pass") for n in p["required"] if n != "voice_ai"]
    assert pipeline.decide(POLICIES["strict"], results(POLICIES["strict"]))["decision"] == "rejected_recommended"
    lenient = POLICIES["lenient"]
    assert pipeline.decide(lenient, results(lenient) + [])["decision"] == "needs_review"


def test_uncertain_required_budget():
    strict, lenient = POLICIES["strict"], POLICIES["lenient"]
    res = [R(n, "pass") for n in strict["required"] if n != "liveness"] + [R("liveness", "uncertain")]
    assert pipeline.decide(strict, res)["decision"] == "needs_review"          # strict tolerates 0
    res_l = [R("face_match", "pass"), R("email_otp", "uncertain")]
    out = pipeline.decide(lenient, res_l)                                       # lenient tolerates 1
    assert out["decision"] == "approved" and "accepted as uncertain" in out["reasons"][0]
    res_2 = [R("face_match", "uncertain"), R("email_otp", "uncertain")]
    assert pipeline.decide(lenient, res_2)["decision"] == "needs_review"


def test_uncertain_or_skipped_face_never_approves_in_any_policy():
    for p in POLICIES.values():
        for status in ("uncertain", "skipped"):
            res = [R("face_match", status)] + [R(n, "pass") for n in p["required"] if n != "face_match"]
            out = pipeline.decide(p, res)
            assert out["decision"] == "needs_review" and "face_match" in out["reasons"][0], (p["name"], status)
        assert pipeline.decide(p, [R(n, "pass") for n in p["required"] if n != "face_match"])["decision"] == "needs_review"


def test_missing_required_check_is_never_approved():
    assert pipeline.decide(POLICIES["strict"], [R("face_match", "pass")])["decision"] == "needs_review"


def test_trust_is_confidence_weighted_and_ignores_skipped():
    res = [R("a", "pass", 1.0, 1.0), R("b", "fail", 0.0, 1.0), CheckResult.skipped("c", "n/a")]
    assert pipeline._trust(res) == 0.5
    assert pipeline._trust([CheckResult.skipped("c", "n/a")]) is None


def test_crashing_check_becomes_uncertain_not_pass():
    from app.checks import base
    from app.models import CheckContext
    base.REGISTRY["boom"] = lambda ctx: 1 / 0
    try:
        r = pipeline.run_one("boom", CheckContext("s", {}, {}, {}, None))
    finally:
        del base.REGISTRY["boom"]
    assert r.status == "uncertain" and "crashed" in r.reason
    assert pipeline.run_one("does_not_exist", CheckContext("s", {}, {}, {}, None)).status == "uncertain"
