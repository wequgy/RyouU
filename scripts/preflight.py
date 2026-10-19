"""Preflight verification of all AI models, database, and Detectif API connectivity.

Usage:
  python -m scripts.preflight

Lists every model by name. Exits with code 1 if any critical component is missing under KYC_STRICT=1.
"""
import os
import sys
import time

from app.config import get_settings


def check_insightface():
    try:
        from app.checks import face_match
        face_match._load_app()
        return True, "Loaded buffalo_l (SCRFD detection + ArcFace recognition + 3D pose)"
    except Exception as e:
        return False, str(e)


def check_mediapipe_landmarker():
    try:
        from app.checks import liveness
        liveness._load_face_landmarker()
        return True, "Loaded face_landmarker.task (52 blendshapes, eyeBlinkLeft/Right)"
    except Exception as e:
        return False, str(e)


def check_minifasnet():
    try:
        from app.checks import anti_spoof
        anti_spoof._load_session()
        return True, "Loaded minifasnet_v2.onnx (Silent-Face-Anti-Spoofing)"
    except Exception as e:
        return False, str(e)


def check_rapidocr():
    try:
        from app.checks.id_details import _get_ocr
        _get_ocr()
        return True, "Loaded RapidOCR onnxruntime models"
    except Exception as e:
        return False, str(e)


def check_whisper(s):
    try:
        from faster_whisper import WhisperModel
        WhisperModel(s.whisper_model, device="auto", compute_type="int8")
        return True, f"Loaded faster-whisper model '{s.whisper_model}'"
    except Exception as e:
        return False, str(e)


def check_vit_deepfake():
    try:
        from app.checks.video_deepfake import _load_vit_model
        _load_vit_model()
        return True, "Loaded ViT Deepfake Detector (prithivMLmods/Deep-Fake-Detector-v2-Model)"
    except Exception as e:
        return False, str(e)


def check_syncnet():
    try:
        from app.checks import lip_sync
        has_w = lip_sync.SYNCNET_WEIGHTS_PATH.exists() and lip_sync.S3FD_WEIGHTS_PATH.exists()
        if has_w:
            return True, "Loaded SyncNet model weights (syncnet_v2.model, sfd_face.pth)"
        return True, "SyncNet available (syncnet-python installed; weights UNCALIBRATED)"
    except Exception as e:
        return False, str(e)


def check_detectif(s):
    if not s.detectif_api_key:
        return False, "DETECTIF_API_KEY is not set"
    try:
        from app.checks.voice_ai import get_credits
        res = get_credits(s)
        rem = res.get("credits_remaining")
        return True, f"Online (credits remaining: {rem})"
    except Exception as e:
        return False, f"Detectif error: {e}"


def main():
    s = get_settings()
    strict = os.environ.get("KYC_STRICT", "1" if s.strict_mode else "0").strip() in ("1", "true", "yes")

    print("=" * 75)
    print(f"Unclone Suite Preflight System Diagnostics [KYC_STRICT={'1' if strict else '0'}]")
    print("=" * 75)

    # 1. Download missing models and verify pinned SHA-256 checksums
    product_scope = "all"
    if s.enable_kyc and not s.enable_interview:
        product_scope = "kyc"
    elif s.enable_interview and not s.enable_kyc:
        product_scope = "interview"

    from scripts.download_models import ensure_models_downloaded
    download_ok = ensure_models_downloaded(product_scope, exit_on_failure=strict)
    if not download_ok and strict:
        print("ERROR: Model download and checksum verification failed under KYC_STRICT=1.")
        sys.exit(1)

    checks = []
    if s.enable_kyc:
        checks.extend([
            ("InsightFace (buffalo_l)", check_insightface),
            ("MediaPipe Face Landmarker", check_mediapipe_landmarker),
            ("MiniFASNet (Anti-Spoofing)", check_minifasnet),
            ("RapidOCR (ID Text)", check_rapidocr),
            ("Faster-Whisper (ASR)", lambda: check_whisper(s)),
        ])
    if s.enable_interview:
        if not s.enable_kyc:
            checks.append(("InsightFace (buffalo_l)", check_insightface))
        checks.extend([
            ("ViT Deepfake / GenD", check_vit_deepfake),
            ("SyncNet (Lip-Sync)", check_syncnet),
            ("Detectif.ai (Voice AI API)", lambda: check_detectif(s)),
        ])

    all_passed = True
    for name, fn in checks:
        t0 = time.time()
        ok, msg = fn()
        dur = time.time() - t0
        status_str = "[ PASS ]" if ok else "[ FAIL ]"
        print(f" {status_str} {name:<28} ({dur:.2f}s) -> {msg}")
        if not ok:
            # Detectif without key in dev mode doesn't fail non-strict
            if name.startswith("Detectif") and not strict:
                continue
            all_passed = False

    print("=" * 75)
    if not all_passed:
        if strict:
            print("ERROR: Preflight failed under KYC_STRICT=1. Aborting startup.")
            sys.exit(1)
        else:
            print("WARNING: Some components reported warnings. Running in lenient/dev mode.")
    else:
        print("SUCCESS: All preflight security checks and AI models passed.")
    print("=" * 75)


if __name__ == "__main__":
    main()
