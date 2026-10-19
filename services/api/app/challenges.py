"""Random liveness challenges. Issued by the server so a pre-recorded or replayed feed can't know them.

Two server challenges:
1. head_turn: Slowly turn head to the left/right, judged server-side via InsightFace.
2. phrase: Spontaneous challenge of 2 random common words + 4 digits, asked twice,
   judged via Whisper and Detectif.
"""
import secrets
import time
import uuid

from . import db

COMMON_WORDS = [
    "amber", "apple", "beacon", "bright", "button", "cactus", "candle", "cherry",
    "cloud", "clover", "coffee", "dragon", "eagle", "forest", "frost", "garden",
    "golden", "harbor", "island", "jungle", "lantern", "lemon", "market", "meadow",
    "monkey", "mountain", "ocean", "orange", "orbit", "planet", "purple", "puzzle",
    "rabbit", "rainbow", "river", "rocket", "shadow", "silver", "sunset", "tiger",
    "timber", "valley", "velvet", "violet", "window", "winter", "wizard", "yellow"
]


def issue(vid: str) -> list:
    now = time.time()
    code = "".join(str(secrets.randbelow(10)) for _ in range(4))
    words = secrets.SystemRandom().sample(COMMON_WORDS, 2)
    turn_dir = secrets.choice(["left", "right"])
    blink_count = secrets.choice([2, 3])
    issued = [
        {"id": "ch_" + uuid.uuid4().hex[:10], "type": "eye_blink", "issued_at": now,
         "count": blink_count, "target_blinks": blink_count,
         "prompt": f"Blink your eyes naturally {blink_count} times while looking at the camera."},
        {"id": "ch_" + uuid.uuid4().hex[:10], "type": "phrase", "issued_at": now,
         "expected_code": code, "expected_digits": code, "expected_words": words,
         "prompt": f"{words[0]} {words[1]} {' '.join(code)}"},
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
            ch["results"][it["id"]] = {
                "metrics": it.get("metrics", {}),
                "prompt_shown_at": it.get("prompt_shown_at", now),
                "answered_at": it.get("answered_at", now)
            }
    db.update_data(vid, mut)
    return {"rejected": rejected}
