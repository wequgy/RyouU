import time
from pathlib import Path

import httpx
import numpy as np
import pytest

from app import challenges, db
from app.checks import face_match, liveness, otp, source_checks, spoken_details, voice_ai
from app.config import get_settings
from app.models import CheckContext


def ctx(data=None, files=None):
    return CheckContext("ver_test", data or {}, files or {}, {}, get_settings())


# ---------------- face match ----------------
def _embedder(sim, px=200, faces=1):
    a = np.array([1.0, 0.0]); b = np.array([sim, (1 - sim ** 2) ** 0.5])
    seq = iter([(a, {"face_px": px, "n_faces": 1}), (b, {"face_px": px, "n_faces": faces})])
    return lambda path: next(seq)


@pytest.mark.parametrize("sim,status", [(0.9, "pass"), (0.1, "fail"), (0.32, "uncertain")])
def test_face_thresholds(monkeypatch, sim, status):
    monkeypatch.setattr(face_match, "EMBEDDER", _embedder(sim))
    r = face_match.face_match(ctx(files={"id_image": Path("a"), "selfie": Path("b")}))
    assert r.status == status and 0 <= r.score <= 1


def test_face_edge_cases(monkeypatch):
    files = {"id_image": Path("a"), "selfie": Path("b")}
    assert face_match.face_match(ctx()).status == "skipped"
    monkeypatch.setattr(face_match, "EMBEDDER", _embedder(0.9, px=20))
    assert "too small" in face_match.face_match(ctx(files=files)).reason
    monkeypatch.setattr(face_match, "EMBEDDER", _embedder(0.9, faces=2))
    assert "Multiple faces" in face_match.face_match(ctx(files=files)).reason
    monkeypatch.setattr(face_match, "EMBEDDER", lambda p: (None, {"error": "no face detected"}))
    assert face_match.face_match(ctx(files=files)).status == "uncertain"

    def no_model(p):
        raise ImportError("insightface")
    monkeypatch.setattr(face_match, "EMBEDDER", no_model)
    assert "not installed" in face_match.face_match(ctx(files=files)).reason


# ---------------- source checks ----------------
def test_source_checks():
    run = lambda sig: source_checks.source_checks(ctx({"signals": sig}))
    assert run({}).status == "skipped"
    assert run({"camera_labels": ["FaceTime HD Camera"]}).status == "pass"
    assert run({"camera_labels": ["OBS Virtual Camera"]}).status == "fail"
    assert run({"camera_labels": ["OBSBOT Tiny 2"]}).status == "pass"            # real webcam brand
    assert run({"camera_labels": ["DroidCam Source 3"]}).status == "fail"
    assert run({"screen_share_attempted": True}).status == "fail"
    assert run({"focus_loss_count": 5}).status == "uncertain"
    assert run({"extended_display": True}).status == "uncertain"
    assert run({"focus_loss_count": 1}).status == "pass"


# ---------------- spoken details ----------------
EXPECTED = {"name": "Asha Rao", "dob": "1999-04-12", "id_last4": "4821"}


def test_spoken_details_match_and_mismatch():
    good = {"name": "my name is Asha Rao", "dob": "12 April 1999", "id_last4": "four eight two one"}
    r = spoken_details.spoken_details(ctx({"expected": EXPECTED, "spoken_transcripts": good}))
    assert r.status == "pass"
    bad = dict(good, id_last4="four eight two nine")
    r = spoken_details.spoken_details(ctx({"expected": EXPECTED, "spoken_transcripts": bad}))
    assert r.status == "fail" and "id_last4" in r.reason
    bad = dict(good, name="Rahul Sharma")
    assert spoken_details.spoken_details(ctx({"expected": EXPECTED, "spoken_transcripts": bad})).status == "fail"
    bad = dict(good, dob="3 May 1999")
    assert spoken_details.spoken_details(ctx({"expected": EXPECTED, "spoken_transcripts": bad})).status == "fail"


def test_spoken_details_partial_missing_and_no_whisper(monkeypatch):
    only_name = {"name": "Asha Rao"}
    r = spoken_details.spoken_details(ctx({"expected": EXPECTED, "spoken_transcripts": only_name}))
    assert r.status == "uncertain"
    assert spoken_details.spoken_details(ctx({"expected": EXPECTED})).status == "skipped"
    assert spoken_details.spoken_details(ctx({"expected": {}})).status == "skipped"

    def no_whisper(path, prompt=None):
        raise ImportError("faster_whisper")
    monkeypatch.setattr(spoken_details, "TRANSCRIBER", no_whisper)
    r = spoken_details.spoken_details(ctx({"expected": EXPECTED}, files={"spoken_name": Path("x.wav")}))
    assert r.status == "uncertain" and "Whisper" in r.reason


# ---------------- liveness ----------------
def _issued(now):
    return [{"id": "c1", "type": "head_turn", "issued_at": now},
            {"id": "c3", "type": "phrase", "issued_at": now, "expected_code": "4821"}]


def _answers(now, **over):
    r = {"c1": {"metrics": {"yaw_range_deg": 40, "face_present_ratio": 0.95}, "answered_at": now + 5},
         "c3": {"metrics": {}, "answered_at": now + 14}}   # phrase: judged from the transcript
    r.update(over)
    return r


def test_liveness_pass_fail_and_phrase():
    now = time.time()
    data = {"challenges": {"issued": _issued(now), "results": _answers(now)},
            "spoken_transcripts": {"phrase": "four eight two one"}}
    assert liveness.liveness(ctx(data)).status == "pass"
    data["spoken_transcripts"]["phrase"] = "one two three four"
    assert liveness.liveness(ctx(data)).status == "fail"
    data["spoken_transcripts"] = {}
    assert liveness.liveness(ctx(data)).status == "uncertain"              # nothing to judge the phrase with
    late = _answers(now, c1={"metrics": {"yaw_range_deg": 40, "face_present_ratio": 0.95}, "answered_at": now + 999})
    data = {"challenges": {"issued": _issued(now), "results": late}, "spoken_transcripts": {"phrase": "4821"}}
    r = liveness.liveness(ctx(data))
    assert r.status == "fail" and r.details["head_turn"]["note"] == "answered too late"
    missing = _answers(now); del missing["c3"]
    data = {"challenges": {"issued": _issued(now), "results": missing}, "spoken_transcripts": {"phrase": "4821"}}
    assert liveness.liveness(ctx(data)).status == "fail"
    assert liveness.liveness(ctx({})).status == "skipped"


def test_challenges_are_random_and_not_replayable(client):
    tenant = db.tenant_by_api_key("kyc_demo_lenient_key")
    v = db.create_verification(tenant["id"], "r", "lenient", {}, "h", 600)
    first = challenges.issue(v["id"])
    codes = {c["expected_code"] for _ in range(1) for c in first if c["type"] == "phrase"}
    assert len(first) == 2 and len(codes) == 1
    ok = challenges.record_results(v["id"], [{"id": first[0]["id"], "metrics": {}}])
    assert ok["rejected"] == []
    again = challenges.record_results(v["id"], [{"id": first[0]["id"], "metrics": {}}])      # replay
    forged = challenges.record_results(v["id"], [{"id": "ch_forged", "metrics": {}}])
    assert again["rejected"] == [first[0]["id"]] and forged["rejected"] == ["ch_forged"]
    second = challenges.issue(v["id"])
    assert {c["id"] for c in first}.isdisjoint({c["id"] for c in second})


# ---------------- Detectif voice check ----------------
def _wav(tmp_path):
    p = tmp_path / "clip.wav"
    p.write_bytes(b"RIFF....WAVEfmt " + b"\0" * 64)
    return p


def _detectif(monkeypatch, handler):
    monkeypatch.setattr(voice_ai, "CLIENT_FACTORY", lambda: httpx.Client(transport=httpx.MockTransport(handler)))


def _ok(verdict, score):
    return httpx.Response(200, json={"request_id": "r", "operation_id": "o", "result": {
        "verdict": verdict, "score": score, "threshold": 0.62, "duration_seconds": 6.4}})


def test_voice_verdicts_map_to_statuses(monkeypatch, tmp_path):
    f = {"challenge_audio": _wav(tmp_path)}
    for verdict, score, status in [("real", 0.07, "pass"), ("fake", 0.95, "fail"), ("not_sure", 0.5, "uncertain")]:
        _detectif(monkeypatch, lambda req, v=verdict, s=score: _ok(v, s))
        r = voice_ai.voice_ai(ctx(files=f))
        assert r.status == status
        if status != "uncertain":
            assert abs(r.score - (1 - score)) < 1e-9                       # trust = 1 - fake probability


def test_voice_sends_auth_idempotency_and_retries_when_busy(monkeypatch, tmp_path):
    seen = []

    def handler(req):
        seen.append(req)
        return httpx.Response(429, headers={"Retry-After": "0"}) if len(seen) == 1 else _ok("real", 0.1)

    _detectif(monkeypatch, handler)
    f = {"challenge_audio": _wav(tmp_path)}
    assert voice_ai.voice_ai(ctx(files=f)).status == "pass"
    assert len(seen) == 2
    assert seen[0].headers["authorization"] == "Bearer test-key"
    assert seen[0].headers["idempotency-key"] == seen[1].headers["idempotency-key"]   # safe retry
    assert str(seen[0].url) == "https://platform.detectif.ai/v1/deepfake/detect"
    voice_ai.voice_ai(ctx(files=f))
    assert seen[2].headers["idempotency-key"] == seen[0].headers["idempotency-key"]   # same file, same key


def test_voice_failure_modes_are_uncertain_never_pass(monkeypatch, tmp_path):
    f = {"challenge_audio": _wav(tmp_path)}
    _detectif(monkeypatch, lambda req: httpx.Response(400, json={"error": {"code": "audio_too_short"}}))
    r = voice_ai.voice_ai(ctx(files=f))
    assert r.status == "uncertain" and "audio_too_short" in r.reason
    _detectif(monkeypatch, lambda req: httpx.Response(503, headers={"Retry-After": "0"}))
    assert voice_ai.voice_ai(ctx(files=f)).status == "uncertain"
    _detectif(monkeypatch, lambda req: httpx.Response(200, json={"unexpected": True}))
    assert voice_ai.voice_ai(ctx(files=f)).status == "uncertain"
    assert voice_ai.voice_ai(ctx()).status == "skipped"
    monkeypatch.setenv("DETECTIF_API_KEY", "")
    assert voice_ai.voice_ai(ctx(files=f)).reason == "DETECTIF_API_KEY not set"


# ---------------- OTP ----------------
def _session():
    tenant = db.tenant_by_api_key("kyc_demo_lenient_key")
    return db.create_verification(tenant["id"], "r", "lenient", {}, "h", 600)["id"]


def test_otp_lifecycle(client):
    vid = _session()
    sent = otp.issue(vid, "email", "asha@example.com")
    code = sent["dev_code"]
    assert sent["destination"] == "a***@example.com" and len(code) == 6
    wrong = "000000" if code != "000000" else "111111"
    assert not otp.verify(vid, "email", wrong)
    assert otp.verify(vid, "email", code)
    assert not otp.verify(vid, "email", code)                                   # single use
    assert db.get_verification(vid)["data"]["verified"]["email"] == "asha@example.com"
    d = db.get_verification(vid)["data"]
    assert otp._otp_check("email")(ctx(d) if False else CheckContext(vid, d, {}, {}, get_settings())).status == "pass"


def test_otp_limits(client, monkeypatch):
    vid = _session()
    for _ in range(3):
        otp.issue(vid, "phone", "+919999999999")
    with pytest.raises(otp.OtpError):
        otp.issue(vid, "phone", "+919999999999")                                # send limit
    vid = _session()
    code = otp.issue(vid, "email", "a@b.co")["dev_code"]
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        otp.verify(vid, "email", wrong)
    assert not otp.verify(vid, "email", code)                                   # locked after 5 attempts
    d = db.get_verification(vid)["data"]
    assert otp._otp_check("email")(CheckContext(vid, d, {}, {}, get_settings())).status == "fail"


def test_otp_expiry(client, monkeypatch):
    monkeypatch.setenv("OTP_TTL_S", "-1")
    vid = _session()
    code = otp.issue(vid, "email", "a@b.co")["dev_code"]
    assert not otp.verify(vid, "email", code)
    with pytest.raises(otp.OtpError):
        otp.issue(vid, "fax", "x")
