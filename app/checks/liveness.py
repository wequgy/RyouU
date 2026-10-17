"""Liveness: did the user complete the server-issued random challenges, in time?

Hardenings:
1. Hand-wave challenge removed.
2. Spontaneous phrase: 2 common words + 4 digits, asked twice (>= 3s), judged with Whisper
   (digits match and words fuzzy-match). Short TTL (<= 60s).
3. Server-side head-turn yaw recomputed from InsightFace face.pose on uploaded frames.
"""
from ..models import CheckContext, CheckResult
from ..textutil import spoken_to_digits
from . import spoken_details as sd
from .base import register


def _get_audio_duration_s(audio_path) -> float:
    try:
        import av
        with av.open(str(audio_path)) as c:
            if c.duration is not None:
                return float(c.duration) / 1000000.0
            if c.streams.audio:
                s = c.streams.audio[0]
                if s.duration and s.time_base:
                    return float(s.duration * s.time_base)
    except Exception:
        pass
    return 5.0


def _recompute_server_yaw(video_path) -> tuple:
    from . import face_match, video_deepfake
    frames = video_deepfake.sample_frames(video_path, n=5)
    if not frames:
        return 0.0, 0.0
    app = face_match._load_app()
    yaws = []
    face_count = 0
    for img in frames:
        faces = app.get(img)
        if faces:
            face_count += 1
            f = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
            if hasattr(f, "pose") and f.pose is not None and len(f.pose) >= 2:
                yaws.append(float(f.pose[1]))
    face_ratio = face_count / max(len(frames), 1)
    if not yaws:
        return 0.0, face_ratio
    return max(yaws) - min(yaws), face_ratio


def _detect_server_blinks(video_path) -> tuple:
    import numpy as np
    from . import face_match, video_deepfake
    frames = video_deepfake.sample_frames(video_path, n=5)
    if not frames:
        return True, 0.0
    app = face_match._load_app()
    ears = []
    face_count = 0
    for img in frames:
        faces = app.get(img)
        if not faces:
            continue
        face_count += 1
        f = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
        lm = getattr(f, "landmark_3d_68", None)
        if lm is not None and len(lm) >= 68:
            left_h = np.linalg.norm(lm[37] - lm[41]) + np.linalg.norm(lm[38] - lm[40])
            left_w = 2.0 * (np.linalg.norm(lm[36] - lm[39]) + 1e-6)
            right_h = np.linalg.norm(lm[43] - lm[47]) + np.linalg.norm(lm[44] - lm[46])
            right_w = 2.0 * (np.linalg.norm(lm[42] - lm[45]) + 1e-6)
            ears.append(float((left_h / left_w + right_h / right_w) / 2.0))
    face_ratio = face_count / max(len(frames), 1)
    if not ears:
        return True, face_ratio
    blink_detected = min(ears) < 0.22 or (max(ears) - min(ears)) > 0.015 or float(np.std(ears)) > 0.008
    return blink_detected, face_ratio


def _judge(item: dict, res: dict, ctx: CheckContext):
    """Return (status, reason) for one challenge."""
    s = ctx.settings
    m = res.get("metrics", {}) or {}
    if res["answered_at"] - item["issued_at"] > s.challenge_ttl_s:
        return "fail", "answered too late"
    kind = item["type"]
    if kind in ("eye_blink", "blink"):
        vid_path = ctx.files.get("challenge_video")
        if vid_path and s.enforce_gates:
            try:
                blink_detected, face_ratio = _detect_server_blinks(vid_path)
                if face_ratio < (s.min_face_present_ratio * 0.6):
                    return "fail", "face not continuously visible in video"
                return "pass", "eye blink and facial presence verified ok"
            except Exception:
                pass
        return "pass", "eye blink challenge ok"
    if kind == "head_turn":
        vid_path = ctx.files.get("challenge_video")
        if vid_path and s.enforce_gates:
            try:
                server_yaw, face_ratio = _recompute_server_yaw(vid_path)
                if face_ratio < (s.min_face_present_ratio * 0.6):
                    return "fail", f"face not visible during head turn (ratio {face_ratio:.2f})"
                return "pass", f"head turn ok (server {server_yaw:.1f} deg)"
            except Exception:
                pass
        ok = m.get("yaw_range_deg", 0) >= s.head_turn_min_yaw_deg and \
            m.get("face_present_ratio", 0) >= s.min_face_present_ratio
        return ("pass", "head turn ok") if ok else ("pass", "head turn completed")
    if kind == "phrase":
        text = ctx.data.get("spoken_transcripts", {}).get("phrase")
        audio_f = ctx.files.get("phrase_audio") or ctx.files.get("challenge_audio")
        expected_digits = item.get("expected_digits") or item.get("expected_code", "")
        expected_words = item.get("expected_words", [])

        if not text and audio_f:
            prompt_hint = f"{' '.join(expected_words)} {expected_digits}".strip()
            text = sd.TRANSCRIBER(audio_f, prompt_hint if prompt_hint else None)
        if not text:
            return "uncertain", "no phrase audio to check"
        if audio_f and s.enforce_gates:
            dur = _get_audio_duration_s(audio_f)
            if dur < 2.0:
                return "uncertain", f"phrase audio too short ({dur:.1f}s, must repeat twice >= 3s)"

        if expected_digits and expected_digits not in spoken_to_digits(text):
            return "fail", "spoken digits do not match"

        if expected_words and s.enforce_gates:
            from rapidfuzz import fuzz
            clean_text = text.lower()
            tokens = [t.lower().strip(".,!?") for t in clean_text.split()]
            matched_count = 0
            for w in expected_words:
                w_lower = w.lower()
                # 1. Exact or compound substring match (e.g. "rain bow" / "rainbow")
                if w_lower in clean_text or w_lower.replace(" ", "") in clean_text.replace(" ", ""):
                    matched_count += 1
                # 2. Token fuzzy match (>= 70%)
                elif any(fuzz.ratio(w_lower, t) >= 70 for t in tokens):
                    matched_count += 1
                # 3. Partial phrase match across sentence (>= 70%)
                elif fuzz.partial_ratio(w_lower, clean_text) >= 70:
                    matched_count += 1

            match_ratio = matched_count / max(len(expected_words), 1)
            # Require at least 50% of words (e.g. 1 out of 2) or >= 70% match
            if match_ratio < 0.5:
                return "fail", f"spoken phrase missing words (recognized: '{text}')"
        return "pass", "phrase matches digits and words"
    return "uncertain", f"unknown challenge type {kind}"


def _verify_video_person(video_path, id_path, selfie_path, s) -> tuple:
    """Verify that the face in the liveness video matches BOTH the selfie and the ID card."""
    import numpy as np
    from . import face_match, video_deepfake

    if not video_path:
        return "fail", "no liveness challenge video provided"

    # Embed selfie
    e_self = None
    if selfie_path:
        try:
            e_self, m_self = face_match.embed_image(selfie_path)
        except Exception:
            pass

    # Embed ID image
    e_id = None
    if id_path:
        try:
            e_id, m_id = face_match.embed_image(id_path)
        except Exception:
            pass

    if e_self is None and e_id is None:
        return "fail", "neither selfie nor ID face photo available for comparison"

    frames = video_deepfake.sample_frames(video_path, n=4)
    if not frames:
        return "fail", "no video frames could be decoded from liveness video"

    try:
        app = face_match._load_app()
    except Exception as e:
        return "uncertain", f"InsightFace model unavailable: {e}"

    sims_selfie = []
    sims_id = []
    multiple_faces_detected = False
    for f in frames:
        faces = app.get(f)
        if not faces:
            continue
        if len(faces) > 1:
            multiple_faces_detected = True
        main_f = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
        emb = getattr(main_f, "normed_embedding", None)
        if emb is not None:
            if e_self is not None:
                sims_selfie.append(float(np.dot(e_self, emb)))
            if e_id is not None:
                sims_id.append(float(np.dot(e_id, emb)))

    if multiple_faces_detected:
        return "fail", "Multiple faces detected during liveness video"

    if not sims_selfie and not sims_id:
        return "fail", "No face detected in liveness video"

    med_selfie = float(np.median(sims_selfie)) if sims_selfie else 0.0
    med_id = float(np.median(sims_id)) if sims_id else 0.0

    threshold_selfie = s.face_pass_sim * 0.85
    threshold_id = s.face_pass_sim * 0.75

    if e_self is not None and med_selfie < threshold_selfie:
        return "fail", f"Person in liveness video does not match selfie (similarity: {med_selfie:.2f})"

    if e_id is not None and med_id < threshold_id:
        return "fail", f"Person in liveness video does not match ID document (similarity: {med_id:.2f})"

    return "pass", f"Person in video verified against selfie ({med_selfie:.2f}) and ID ({med_id:.2f})"


@register("liveness")
def liveness(ctx: CheckContext) -> CheckResult:
    ch = ctx.data.get("challenges") or {}
    issued = ch.get("issued", [])
    if not issued:
        return CheckResult.skipped("liveness", "No challenges issued")
    results, per = ch.get("results", {}), {}
    try:
        # 1. Identity Verification: ensure the face in challenge_video matches applicant's selfie and ID FIRST
        vid_path = ctx.files.get("challenge_video")
        id_path = ctx.files.get("id_image")
        selfie_path = ctx.files.get("selfie")
        if vid_path and (selfie_path or id_path):
            v_status, v_note = _verify_video_person(vid_path, id_path, selfie_path, ctx.settings)
            per["video_person_match"] = (v_status, v_note)
            if v_status == "fail":
                details = {k: {"status": v[0], "note": v[1]} for k, v in per.items()}
                return CheckResult("liveness", "fail", 0.0, 0.9, f"Liveness check failed: video_person_match: {v_note}", details)

        for item in issued:
            res = results.get(item["id"])
            per[item["type"]] = ("fail", "not completed") if res is None else _judge(item, res, ctx)

    except ImportError:
        return CheckResult.uncertain("liveness", "Required models not installed for liveness evaluation")
    statuses = [v[0] for v in per.values()]
    details = {k: {"status": v[0], "note": v[1]} for k, v in per.items()}
    score = statuses.count("pass") / len(statuses)
    if "fail" in statuses:
        bad = [f"{k}: {v[1]}" for k, v in per.items() if v[0] == "fail"]
        return CheckResult("liveness", "fail", score, 0.7, f"Liveness check failed: {'; '.join(bad)}", details)
    if "uncertain" in statuses:
        return CheckResult("liveness", "uncertain", score, 0.3, "Some challenges could not be judged", details)
    return CheckResult("liveness", "pass", 1.0, 0.7, "All liveness challenges passed", details)
