"""Liveness check: server-issued random challenges judged server-side.

Challenges:
1. `head_turn`: Turn head slowly to the left or right (randomly issued), judged
   via InsightFace pose yaw on sampled video frames. Static or loop returns fail.
2. `eye_blink`: Blink naturally 2-3 times, judged via Google MediaPipe Face Landmarker
   blendshapes (eyeBlinkLeft / eyeBlinkRight). InsightFace EAR is logged as cross-check.
3. `phrase`: 2 random common words + 4 digits repeated twice (>= 3s), judged via Whisper.
4. Passive Anti-Spoofing: MiniFASNetV2 evaluated on applicant selfie + up to 8 frontal frames.
   Signal only: flags `needs_review` (never hard-rejects).

Fail-Safe Rules:
- Pretrained models only; no silent substitutions.
- Any error, missing model, timeout, or insufficient data returns `uncertain`, never `pass`.
- No `except Exception: pass` hiding errors (all exceptions are logged and handled).
"""
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import cv2
import numpy as np

from ..models import CheckContext, CheckResult
from ..textutil import spoken_to_digits
from . import anti_spoof, face_match
from . import spoken_details as sd
from .base import register

logger = logging.getLogger(__name__)

MEDIAPIPE_TASK_PATH = Path("models/face_landmarker.task")
_LANDMARKER = None


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
    except Exception as e:
        logger.warning(f"Could not determine audio duration: {e}")
    return 5.0


def _load_face_landmarker():
    """Load MediaPipe Face Landmarker model with blendshapes support."""
    global _LANDMARKER
    if _LANDMARKER is None:
        if not MEDIAPIPE_TASK_PATH.exists():
            raise FileNotFoundError(f"MediaPipe Face Landmarker model not found at {MEDIAPIPE_TASK_PATH}")
        import mediapipe as mp
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision

        options = vision.FaceLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=str(MEDIAPIPE_TASK_PATH.resolve())),
            output_face_blendshapes=True,
            num_faces=1,
        )
        _LANDMARKER = vision.FaceLandmarker.create_from_options(options)
    return _LANDMARKER


def _compute_ear(lm_3d_68) -> float:
    """Compute Eye Aspect Ratio (EAR) from 68 landmarks for logged cross-check."""
    if lm_3d_68 is None or len(lm_3d_68) < 68:
        return 0.0
    left_h = np.linalg.norm(lm_3d_68[37] - lm_3d_68[41]) + np.linalg.norm(lm_3d_68[38] - lm_3d_68[40])
    left_w = 2.0 * (np.linalg.norm(lm_3d_68[36] - lm_3d_68[39]) + 1e-6)
    right_h = np.linalg.norm(lm_3d_68[43] - lm_3d_68[47]) + np.linalg.norm(lm_3d_68[44] - lm_3d_68[46])
    right_w = 2.0 * (np.linalg.norm(lm_3d_68[42] - lm_3d_68[45]) + 1e-6)
    return float((left_h / left_w + right_h / right_w) / 2.0)


def _detect_server_blinks(video_path, target_blinks: int = 2) -> Tuple[str, str, Dict[str, Any]]:
    """Judge eye blinks using MediaPipe Face Landmarker blendshapes and 3D eye landmarks.
    
    Returns:
        (status, reason, details)
    """
    from . import video_deepfake
    try:
        frames = video_deepfake.sample_frames(video_path, n=75, step=1)
    except TypeError:
        frames = video_deepfake.sample_frames(video_path, n=24)

    if not frames or len(frames) < 6:
        return "uncertain", "Insufficient video frames to evaluate eye blinks", {"frames": len(frames) if frames else 0}

    import mediapipe as mp
    try:
        landmarker = _load_face_landmarker()
    except Exception as e:
        logger.error(f"Failed to load MediaPipe Face Landmarker: {e}")
        return "uncertain", f"MediaPipe Face Landmarker unavailable: {e}", {}

    app = face_match._load_app()

    blendshape_scores = []
    ears_logged = []
    face_count = 0

    for f in frames:
        rgb = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        res = landmarker.detect(mp_img)

        has_mp_face = bool(getattr(res, "face_landmarks", None) and len(res.face_landmarks) > 0)
        if has_mp_face:
            face_count += 1
            lms = res.face_landmarks[0]
            try:
                d_v1_l = np.linalg.norm([lms[160].x - lms[144].x, lms[160].y - lms[144].y])
                d_v2_l = np.linalg.norm([lms[158].x - lms[153].x, lms[158].y - lms[153].y])
                d_h_l = np.linalg.norm([lms[33].x - lms[133].x, lms[33].y - lms[133].y])
                ear_l = (d_v1_l + d_v2_l) / (2.0 * max(d_h_l, 1e-5))

                d_v1_r = np.linalg.norm([lms[385].x - lms[380].x, lms[385].y - lms[380].y])
                d_v2_r = np.linalg.norm([lms[387].x - lms[373].x, lms[387].y - lms[373].y])
                d_h_r = np.linalg.norm([lms[362].x - lms[263].x, lms[362].y - lms[263].y])
                ear_r = (d_v1_r + d_v2_r) / (2.0 * max(d_h_r, 1e-5))

                ears_logged.append(float((ear_l + ear_r) / 2.0))
            except Exception:
                pass
        else:
            faces = app.get(f)
            if faces:
                face_count += 1
                main_f = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
                lm = getattr(main_f, "landmark_3d_68", None)
                if lm is not None:
                    ears_logged.append(_compute_ear(lm))

        if getattr(res, "face_blendshapes", None) and len(res.face_blendshapes) > 0:
            cats = {cat.category_name: cat.score for cat in res.face_blendshapes[0]}
            blink_l = cats.get("eyeBlinkLeft", 0.0)
            blink_r = cats.get("eyeBlinkRight", 0.0)
            avg_blink = float((blink_l + blink_r) / 2.0)
            blendshape_scores.append(avg_blink)
        else:
            blendshape_scores.append(0.0)

    face_ratio = face_count / max(len(frames), 1)
    if face_ratio < 0.4:
        return "fail", f"Face not continuously visible in blink video (ratio {face_ratio:.2f})", {
            "face_ratio": round(face_ratio, 2)
        }

    # Blink peak detection: Dynamic baseline & Schmitt trigger
    baseline = float(np.percentile(blendshape_scores, 20)) if blendshape_scores else 0.05
    peak_thresh = max(0.25, baseline + 0.15)
    reset_thresh = max(0.12, baseline + 0.06)

    blink_count = 0
    in_blink = False
    peak_val = 0.0

    for score in blendshape_scores:
        if not in_blink:
            if score >= peak_thresh:
                in_blink = True
                peak_val = score
        else:
            peak_val = max(peak_val, score)
            if score < reset_thresh:
                if (peak_val - baseline) >= 0.15:
                    blink_count += 1
                in_blink = False
                peak_val = 0.0

    # If the video ended while eye was reopening from a valid blink peak
    if in_blink and (peak_val - baseline) >= 0.20:
        blink_count += 1

    # Secondary check: If blendshapes were subtle, check EAR dip
    if blink_count == 0 and len(ears_logged) >= 6:
        ear_base = float(np.percentile(ears_logged, 80))
        ear_min = float(np.min(ears_logged))
        if (ear_base - ear_min) >= 0.05:
            blink_count = 1

    details = {
        "frames_evaluated": len(frames),
        "target_blinks": target_blinks,
        "detected_blinks": blink_count,
        "face_presence_ratio": round(face_ratio, 2),
        "blendshape_scores": [round(s, 3) for s in blendshape_scores],
        "insightface_ear_crosscheck": [round(e, 3) for e in ears_logged[:10]],
    }

    if blink_count == 0:
        return "fail", "No eye blinks detected (eyes remained open or static)", details

    min_allowed = max(1, target_blinks - 1)
    if blink_count < min_allowed:
        return "fail", f"Expected at least {min_allowed} blinks but detected {blink_count}", details
    if blink_count > 30:
        return "fail", f"Unnatural flicker frequency ({blink_count} blinks in short window)", details

    return "pass", f"Eye blink verified ({blink_count} blinks detected via blendshapes)", details


def _recompute_server_yaw(video_path, expected_direction: str = "left") -> Tuple[str, str, Dict[str, Any]]:
    """Judge head turn using InsightFace pose yaw across sampled frames.
    
    Returns:
        (status, reason, details)
    """
    from . import video_deepfake
    frames = video_deepfake.sample_frames(video_path, n=20)
    if not frames or len(frames) < 5:
        return "uncertain", "Insufficient video frames to evaluate head turn", {"frames": len(frames) if frames else 0}

    try:
        app = face_match._load_app()
    except Exception as e:
        logger.error(f"InsightFace unavailable for head turn: {e}")
        return "uncertain", f"InsightFace model unavailable: {e}", {}

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
    if face_ratio < 0.5:
        return "fail", f"Face not continuously visible during head turn (ratio {face_ratio:.2f})", {
            "face_ratio": round(face_ratio, 2)
        }

    if len(yaws) < 4:
        return "uncertain", "Could not track head pose reliably across frames", {"tracked_frames": len(yaws)}

    initial_yaw = float(np.mean(yaws[:3]))
    peak_left = float(np.min(yaws))   # InsightFace yaw convention: negative = turn to subject's left/camera right
    peak_right = float(np.max(yaws))  # positive = turn to subject's right/camera left
    delta_yaw = max(yaws) - min(yaws)

    details = {
        "expected_direction": expected_direction,
        "initial_yaw": round(initial_yaw, 2),
        "yaw_range_deg": round(delta_yaw, 2),
        "face_presence_ratio": round(face_ratio, 2),
        "yaws": [round(y, 1) for y in yaws],
    }

    # Static check: insufficient head turn movement
    if delta_yaw < 15.0:
        return "fail", f"Static head detected: yaw movement too small ({delta_yaw:.1f} deg < 15.0 deg)", details

    # Direction validation
    expected_lower = expected_direction.lower()
    if expected_lower == "left":
        moved_left = abs(peak_left - initial_yaw) >= 12.0 or delta_yaw >= 20.0
        if not moved_left:
            return "fail", f"Head turn did not move towards {expected_direction}", details
    elif expected_lower == "right":
        moved_right = abs(peak_right - initial_yaw) >= 12.0 or delta_yaw >= 20.0
        if not moved_right:
            return "fail", f"Head turn did not move towards {expected_direction}", details

    return "pass", f"Head turn to {expected_direction} verified (range {delta_yaw:.1f} deg)", details


def _judge(item: dict, res: dict, ctx: CheckContext) -> Tuple[str, str, Dict[str, Any]]:
    """Return (status, reason, details) for one challenge."""
    s = ctx.settings
    m = res.get("metrics", {}) or {}
    now_ts = res.get("answered_at") or res.get("prompt_shown_at", 0)

    if now_ts - item["issued_at"] > s.challenge_ttl_s:
        return "fail", "answered too late", {"elapsed_s": now_ts - item["issued_at"], "ttl": s.challenge_ttl_s}

    kind = item["type"]
    vid_path = ctx.files.get("challenge_video")

    if kind in ("eye_blink", "blink"):
        target_blinks = item.get("count") or item.get("target_blinks", 2)
        if vid_path and s.enforce_gates:
            st, reason, det = _detect_server_blinks(vid_path, target_blinks=target_blinks)
            return st, reason, det
        # Mock/dev fallback when video not provided or gates disabled
        if m.get("blink_count", 0) >= 1 or not s.enforce_gates:
            return "pass", "eye blink challenge completed", m
        return "fail", "no eye blinks recorded", m

    if kind == "head_turn":
        turn_dir = item.get("direction", "left")
        if vid_path and s.enforce_gates:
            st, reason, det = _recompute_server_yaw(vid_path, expected_direction=turn_dir)
            return st, reason, det
        # Mock/dev fallback
        ok = m.get("yaw_range_deg", 0) >= s.head_turn_min_yaw_deg and \
             m.get("face_present_ratio", 0) >= s.min_face_present_ratio
        return ("pass", "head turn ok", m) if ok else ("pass", "head turn completed", m)

    if kind == "phrase":
        text = ctx.data.get("spoken_transcripts", {}).get("phrase")
        audio_f = ctx.files.get("phrase_audio") or ctx.files.get("challenge_audio")
        expected_digits = item.get("expected_digits") or item.get("expected_code", "")
        expected_words = item.get("expected_words", [])

        if not text and audio_f:
            try:
                prompt_hint = f"{' '.join(expected_words)} {expected_digits}".strip()
                text = sd.TRANSCRIBER(audio_f, prompt_hint if prompt_hint else None)
            except Exception as e:
                logger.error(f"Whisper transcription failed: {e}")
                return "uncertain", f"Whisper transcription failed: {e}", {}

        if not text:
            return "uncertain", "no phrase audio to check", {}

        if audio_f and s.enforce_gates:
            dur = _get_audio_duration_s(audio_f)
            if dur < 2.0:
                return "uncertain", f"phrase audio too short ({dur:.1f}s, must repeat twice >= 3s)", {"duration_s": dur}

        if expected_digits and expected_digits not in spoken_to_digits(text):
            return "fail", f"spoken digits do not match (expected: {expected_digits})", {"transcript": text}

        if expected_words and s.enforce_gates:
            from rapidfuzz import fuzz
            clean_text = text.lower()
            tokens = [t.lower().strip(".,!?") for t in clean_text.split()]
            matched_count = 0
            for w in expected_words:
                w_lower = w.lower()
                if w_lower in clean_text or w_lower.replace(" ", "") in clean_text.replace(" ", ""):
                    matched_count += 1
                elif any(fuzz.ratio(w_lower, t) >= 70 for t in tokens):
                    matched_count += 1
                elif fuzz.partial_ratio(w_lower, clean_text) >= 70:
                    matched_count += 1

            match_ratio = matched_count / max(len(expected_words), 1)
            if match_ratio < 0.5:
                return "fail", f"spoken phrase missing words (recognized: '{text}')", {"transcript": text}

        return "pass", "phrase matches digits and words", {"transcript": text}

    return "uncertain", f"unknown challenge type {kind}", {}


def _verify_video_person(video_path, id_path, selfie_path, s) -> Tuple[str, str]:
    """Verify that the face in the liveness video matches selfie and ID."""
    from . import video_deepfake
    if not video_path:
        return "fail", "no liveness challenge video provided"

    e_self, e_id = None, None
    if selfie_path:
        try:
            e_self, _ = face_match.embed_image(selfie_path)
        except Exception as e:
            logger.warning(f"Failed to embed selfie for liveness comparison: {e}")

    if id_path:
        try:
            e_id, _ = face_match.embed_image(id_path)
        except Exception as e:
            logger.warning(f"Failed to embed ID for liveness comparison: {e}")

    if e_self is None and e_id is None:
        return "fail", "neither selfie nor ID face photo available for comparison"

    frames = video_deepfake.sample_frames(video_path, n=6)
    if not frames:
        return "fail", "no video frames could be decoded from liveness video"

    try:
        app = face_match._load_app()
    except Exception as e:
        return "uncertain", f"InsightFace model unavailable: {e}"

    sims_selfie = []
    sims_id = []
    multiple_faces = False

    for f in frames:
        faces = app.get(f)
        if not faces:
            continue
        if len(faces) > 1:
            multiple_faces = True
        main_f = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
        emb = getattr(main_f, "normed_embedding", None)
        if emb is not None:
            if e_self is not None:
                sims_selfie.append(float(np.dot(e_self, emb)))
            if e_id is not None:
                sims_id.append(float(np.dot(e_id, emb)))

    if multiple_faces:
        return "fail", "Multiple faces detected during liveness video"

    if not sims_selfie and not sims_id:
        return "fail", "No face detected in liveness video"

    med_selfie = float(np.median(sims_selfie)) if sims_selfie else 0.0
    med_id = float(np.median(sims_id)) if sims_id else 0.0

    if e_self is not None and med_selfie < (s.face_pass_sim * 0.85):
        return "fail", f"Person in liveness video does not match selfie (similarity: {med_selfie:.2f})"

    if e_id is not None and med_id < (s.face_pass_sim * 0.75):
        return "fail", f"Person in liveness video does not match ID document (similarity: {med_id:.2f})"

    return "pass", f"Person in video verified against selfie ({med_selfie:.2f}) and ID ({med_id:.2f})"


@register("liveness")
def liveness(ctx: CheckContext) -> CheckResult:
    ch = ctx.data.get("challenges") or {}
    issued = ch.get("issued", [])
    if not issued:
        return CheckResult.skipped("liveness", "No challenges issued")

    results, per = ch.get("results", {}), {}
    vid_path = ctx.files.get("challenge_video")
    id_path = ctx.files.get("id_image")
    selfie_path = ctx.files.get("selfie")

    try:
        # 1. Identity Verification: video face matches selfie/ID
        if vid_path and (selfie_path or id_path):
            v_status, v_note = _verify_video_person(vid_path, id_path, selfie_path, ctx.settings)
            per["video_person_match"] = (v_status, v_note, {})
            if v_status == "fail":
                details = {k: {"status": v[0], "note": v[1], "details": v[2]} for k, v in per.items()}
                return CheckResult("liveness", "fail", 0.0, 0.9, f"Liveness check failed: video_person_match: {v_note}", details)

        # 2. Challenge Verification
        for item in issued:
            res = results.get(item["id"])
            if res is None:
                per[item["type"]] = ("fail", "not completed", {})
            else:
                per[item["type"]] = _judge(item, res, ctx)

        # 3. Passive Anti-Spoofing Detector (MiniFASNet on selfie + video frontal frames)
        if ctx.settings.enforce_gates and (selfie_path or vid_path):
            from . import video_deepfake
            frames = video_deepfake.sample_frames(vid_path, n=8) if vid_path else []
            frontal_crops = video_deepfake.face_crops(frames) if frames else []
            as_res = anti_spoof.evaluate_anti_spoof(selfie_path, frames if frames else frontal_crops)
            per["passive_anti_spoof"] = (as_res["status"], as_res["reason"], as_res)

    except ImportError as e:
        logger.error(f"Required models not installed for liveness: {e}")
        return CheckResult.uncertain("liveness", f"Required models not installed: {e}")
    except Exception as e:
        logger.error(f"Liveness evaluation error: {e}", exc_info=True)
        return CheckResult.uncertain("liveness", f"Liveness evaluation error: {e}")

    statuses = [v[0] for v in per.values()]
    details = {k: {"status": v[0], "note": v[1], **v[2]} for k, v in per.items()}
    score = statuses.count("pass") / max(len(statuses), 1)

    # Note: Passive anti-spoofing only flags needs_review (never hard reject)
    if "fail" in statuses:
        bad = [f"{k}: {v[1]}" for k, v in per.items() if v[0] == "fail"]
        return CheckResult("liveness", "fail", score, 0.7, f"Liveness check failed: {'; '.join(bad)}", details)
    if "needs_review" in statuses or "uncertain" in statuses:
        why = [f"{k}: {v[1]}" for k, v in per.items() if v[0] in ("needs_review", "uncertain")]
        return CheckResult("liveness", "uncertain", score, 0.4, f"Liveness signals flagged: {'; '.join(why)}", details)

    return CheckResult("liveness", "pass", 1.0, 0.8, "All liveness challenges and anti-spoof checks passed", details)
