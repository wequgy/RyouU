"""Random liveness challenges. Issued by the server so a pre-recorded or replayed feed can't know them.

Pass/fail metrics currently come from the client (e.g. MediaPipe in the browser) and are UNTRUSTED:
good enough for a demo, but production should recompute them server-side from uploaded frames.
"""
import secrets
import time
import uuid

from . import db


def issue(vid: str) -> list:
    now = time.time()
    code = "".join(str(secrets.randbelow(10)) for _ in range(4))
    side = secrets.choice(["left", "right"])
    issued = [
        {"id": "ch_" + uuid.uuid4().hex[:10], "type": "head_turn", "issued_at": now,
         "prompt": f"Slowly turn your head to the {side}, then back to the camera."},
        {"id": "ch_" + uuid.uuid4().hex[:10], "type": "hand_wave", "issued_at": now,
         "prompt": "Slowly wave a hand in front of your face for about 5 seconds."},
        {"id": "ch_" + uuid.uuid4().hex[:10], "type": "phrase", "issued_at": now, "expected_code": code,
         "prompt": "Read these digits aloud: " + " ".join(code)},
    ]

    def mut(d):
        d["challenges"] = {"issued": issued, "results": {}}
    db.update_data(vid, mut)
    return issued


def record_results(vid: str, items: list) -> dict:
    """Accept each challenge result once. Unknown ids are rejected (replay / forgery)."""
    now = time.time()
    rejected = []

    def mut(d):
        ch = d.get("challenges") or {}
        known = {c["id"] for c in ch.get("issued", [])}
        for it in items:
            if it["id"] not in known or it["id"] in ch.get("results", {}):
                rejected.append(it["id"])
                continue
            ch["results"][it["id"]] = {"metrics": it.get("metrics", {}), "answered_at": now}
    db.update_data(vid, mut)
    return {"rejected": rejected}
