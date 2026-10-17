"""Preflight verification of all AI models, database, and Detectif API connectivity.

Usage:
  python -m scripts.preflight

Exits with code 1 if any critical component is missing under KYC_STRICT=1.
"""
import os
import sys
import time

from app.config import get_settings


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


def check_insightface():
    try:
        from app.checks import face_match
        face_match._load_app()
        return True, "Loaded buffalo_l (detection + recognition + landmarks)"
    except Exception as e:
        return False, str(e)


def check_whisper(s):
    try:
        from faster_whisper import WhisperModel
        WhisperModel(s.whisper_model, device="auto", compute_type="int8")
        return True, f"Loaded faster-whisper model '{s.whisper_model}'"
    except Exception as e:
        return False, str(e)


def check_rapidocr():
    try:
        from app.checks.id_details import _get_ocr
        _get_ocr()
        return True, "Loaded RapidOCR onnxruntime models"
    except Exception as e:
        return False, str(e)


def check_vit_deepfake():
    try:
        from app.checks.video_deepfake import _load
        _load()
        return True, "Loaded ViT Deepfake Detector (prithivMLmods/Deep-Fake-Detector-v2-Model)"
    except Exception as e:
        return False, str(e)


def main():
    s = get_settings()
    strict = os.environ.get("KYC_STRICT", "0").strip() in ("1", "true", "yes")

    print("=" * 70)
    print(f"RyouU KYC Preflight System Diagnostics [KYC_STRICT={'1' if strict else '0'}]")
    print("=" * 70)

    checks = [
        ("InsightFace (buffalo_l)", check_insightface),
        ("Faster-Whisper (ASR)", lambda: check_whisper(s)),
        ("RapidOCR (ID OCR)", check_rapidocr),
        ("ViT Deepfake (Visual)", check_vit_deepfake),
        ("Detectif.ai (Voice AI)", lambda: check_detectif(s)),
    ]

    all_passed = True
    for name, fn in checks:
        t0 = time.time()
        ok, msg = fn()
        dur = time.time() - t0
        status_str = "[ PASS ]" if ok else "[ FAIL ]"
        print(f" {status_str} {name:<26} ({dur:.2f}s) -> {msg}")
        if not ok:
            all_passed = False

    print("=" * 70)
    if not all_passed:
        if strict:
            print("ERROR: Preflight failed under KYC_STRICT=1. Aborting startup.")
            sys.exit(1)
        else:
            print("WARNING: Some components reported warnings. Running in lenient/dev mode.")
    else:
        print("SUCCESS: All preflight security checks and AI models passed.")
    print("=" * 70)


if __name__ == "__main__":
    main()
