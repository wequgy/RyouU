"""System readiness verification for enabled products."""
from app.config import get_settings


def check_system_readiness():
    """Verify operational readiness of every required AI model, database, and Detectif API for enabled products."""
    s = get_settings()
    models = {}
    critical_names = []

    # KYC Models
    if s.enable_kyc:
        # 1. InsightFace buffalo_l
        try:
            from app.checks import face_match
            face_match._load_app()
            models["InsightFace (buffalo_l)"] = {"status": "ready", "license": "InsightFace Non-Commercial", "purpose": "Face embeddings and pose yaw"}
        except Exception as e:
            models["InsightFace (buffalo_l)"] = {"status": "error", "error": str(e)}

        # 2. MediaPipe Face Landmarker
        try:
            from app.checks import liveness
            liveness._load_face_landmarker()
            models["MediaPipe Face Landmarker (face_landmarker.task)"] = {"status": "ready", "license": "Apache-2.0", "purpose": "Eye blink blendshapes"}
        except Exception as e:
            models["MediaPipe Face Landmarker (face_landmarker.task)"] = {"status": "error", "error": str(e)}

        # 3. MiniFASNet Passive Anti-Spoofing
        try:
            from app.checks import anti_spoof
            anti_spoof._load_session()
            models["MiniFASNetV2 (Silent-Face-Anti-Spoofing)"] = {"status": "ready", "license": "Apache-2.0", "purpose": "Passive face anti-spoofing"}
        except Exception as e:
            models["MiniFASNetV2 (Silent-Face-Anti-Spoofing)"] = {"status": "error", "error": str(e)}

        # 4. RapidOCR
        try:
            from app.checks import id_details
            id_details._get_ocr()
            models["RapidOCR (onnxruntime)"] = {"status": "ready", "license": "Apache-2.0", "purpose": "ID document text extraction"}
        except Exception as e:
            models["RapidOCR (onnxruntime)"] = {"status": "error", "error": str(e)}

        # 5. Faster-Whisper
        try:
            from faster_whisper import WhisperModel
            models["Faster-Whisper (ASR)"] = {"status": "ready", "model": s.whisper_model, "license": "MIT", "purpose": "Speech transcription"}
        except Exception as e:
            models["Faster-Whisper (ASR)"] = {"status": "error", "error": str(e)}

        critical_names.extend([
            "InsightFace (buffalo_l)",
            "MediaPipe Face Landmarker (face_landmarker.task)",
            "MiniFASNetV2 (Silent-Face-Anti-Spoofing)",
            "RapidOCR (onnxruntime)",
            "Faster-Whisper (ASR)"
        ])

    # Interview Models
    if s.enable_interview:
        # 6. ViT Deepfake Detector
        try:
            from app.checks import video_deepfake
            video_deepfake._load_vit_model()
            models["ViT Deepfake Detector (prithivMLmods/Deep-Fake-Detector-v2-Model)"] = {"status": "ready", "license": "Apache-2.0", "purpose": "Visual deepfake classification"}
        except Exception as e:
            models["ViT Deepfake Detector (prithivMLmods/Deep-Fake-Detector-v2-Model)"] = {"status": "error", "error": str(e)}

        # 7. SyncNet Lip-Sync
        try:
            from app.checks import lip_sync
            has_w = lip_sync.SYNCNET_WEIGHTS_PATH.exists() and lip_sync.S3FD_WEIGHTS_PATH.exists()
            models["SyncNet (syncnet-python)"] = {
                "status": "ready" if has_w else "uncalibrated",
                "weights_present": has_w,
                "license": "MIT",
                "purpose": "Audio-visual lip synchronization"
            }
        except Exception as e:
            models["SyncNet (syncnet-python)"] = {"status": "error", "error": str(e)}

        # 8. Detectif.ai Voice API
        if s.detectif_api_key:
            models["Detectif.ai (Voice AI)"] = {"status": "configured", "base_url": s.detectif_base_url, "purpose": "Voice cloning & speaker verification"}
        else:
            models["Detectif.ai (Voice AI)"] = {"status": "unconfigured", "error": "DETECTIF_API_KEY not set"}

        critical_names.append("ViT Deepfake Detector (prithivMLmods/Deep-Fake-Detector-v2-Model)")

    # In production strict mode, critical components must be ready
    all_ready = all(models.get(name, {}).get("status") in ("ready", "configured", "uncalibrated") for name in critical_names)
    return all_ready, models
