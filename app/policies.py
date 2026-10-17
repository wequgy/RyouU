"""Per-tenant policy: which checks run and how results map to a decision.

Decisions are RECOMMENDATIONS. 'rejected_recommended' still goes to a human.

reject_on_fail:         a FAIL on any of these -> rejected_recommended
must_pass:              anything other than PASS here (uncertain, skipped, missing) -> needs_review
max_uncertain_required: how many OTHER required checks may be uncertain/skipped and still approve
"""

POLICIES = {
    "lenient": {
        "name": "lenient",
        "required": ["id_details", "face_match", "email_otp"],
        "optional": ["voice_ai", "spoken_details", "liveness", "source_checks", "phone_otp", "video_deepfake", "scene_integrity", "lip_sync"],
        "reject_on_fail": ["id_details", "face_match"],
        "must_pass": ["id_details", "face_match"],          # never approve on 'uncertain'/'skipped' for these
        "max_uncertain_required": 1,
    },
    "strict": {
        "name": "strict",
        "required": ["id_details", "face_match", "email_otp", "voice_ai",
                     "liveness", "source_checks"],
        "optional": ["phone_otp", "video_deepfake", "scene_integrity", "lip_sync", "spoken_details"],
        "reject_on_fail": ["id_details", "face_match", "voice_ai", "source_checks", "scene_integrity", "lip_sync", "liveness"],
        "must_pass": ["id_details", "face_match", "email_otp", "voice_ai",
                      "liveness", "source_checks"],
        "max_uncertain_required": 0,
    },
}

# Which flow-page steps each check needs (the page builds its screens from this)
CHECK_STEPS = {
    "id_details": ["upload_id_image"],
    "face_match": ["upload_id_image", "upload_selfie"],
    "email_otp": ["email_otp"],
    "phone_otp": ["phone_otp"],
    "voice_ai": ["record_challenge_audio"],
    "spoken_details": ["record_spoken_answers"],
    "liveness": ["liveness_challenges"],
    "source_checks": ["client_signals"],
    "scene_integrity": ["record_challenge_video"],
    "lip_sync": ["record_challenge_video"],
    "video_deepfake": ["record_challenge_video"],
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
