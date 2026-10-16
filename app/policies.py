"""Per-tenant policy: which checks run and how results map to a decision.

Decisions are RECOMMENDATIONS. 'rejected_recommended' still goes to a human.

reject_on_fail:         a FAIL on any of these -> rejected_recommended
must_pass:              anything other than PASS here (uncertain, skipped, missing) -> needs_review
max_uncertain_required: how many OTHER required checks may be uncertain/skipped and still approve
"""

POLICIES = {
    "lenient": {
        "name": "lenient",
        "required": ["face_match", "email_otp"],
        "optional": ["voice_ai", "spoken_details", "liveness", "source_checks", "phone_otp", "video_deepfake"],
        "reject_on_fail": ["face_match"],
        "must_pass": ["face_match"],          # never approve on 'uncertain'/'skipped' for these
        "max_uncertain_required": 1,
    },
    "strict": {
        "name": "strict",
        "required": ["face_match", "email_otp", "phone_otp", "voice_ai", "spoken_details",
                     "liveness", "source_checks"],
        "optional": ["video_deepfake"],
        "reject_on_fail": ["face_match", "voice_ai", "source_checks"],
        "must_pass": ["face_match", "email_otp", "phone_otp", "voice_ai", "spoken_details",
                      "liveness", "source_checks"],
        "max_uncertain_required": 0,
    },
}

# Which flow-page steps each check needs (the page builds its screens from this)
CHECK_STEPS = {
    "face_match": ["upload_id_image", "upload_selfie"],
    "email_otp": ["email_otp"],
    "phone_otp": ["phone_otp"],
    "voice_ai": ["record_challenge_audio"],
    "spoken_details": ["record_spoken_answers"],
    "liveness": ["liveness_challenges"],
    "source_checks": ["client_signals"],
    "video_deepfake": [],
}


def get_policy(name: str) -> dict:
    if name not in POLICIES:
        raise KeyError(name)
    return POLICIES[name]


def checks_for(policy: dict) -> list:
    return list(dict.fromkeys(policy["required"] + policy["optional"]))


def steps_for(policy: dict) -> list:
    steps = []
    for name in checks_for(policy):
        for s in CHECK_STEPS.get(name, []):
            if s not in steps:
                steps.append(s)
    return steps
