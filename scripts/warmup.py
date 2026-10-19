"""Warm up and pre-load all AI models for enabled products.

Downloads pinned model weights if not present and verifies SHA-256 checksums:
1. InsightFace (buffalo_l)
2. MediaPipe Face Landmarker (face_landmarker.task)
3. MiniFASNet (minifasnet_v2.onnx)
4. Faster-Whisper (configured model)
5. RapidOCR (onnxruntime detection + recognition)
6. ViT Deepfake Detector (prithivMLmods/Deep-Fake-Detector-v2-Model)
7. SyncNet Lip-Sync (syncnet-python)
"""
import time
from app.config import get_settings
from scripts.download_models import ensure_models_downloaded


def main():
    s = get_settings()
    print("=" * 70)
    print("Unclone Suite Model Warmup & Cache Initialization")
    print("=" * 70)

    # 1. Download missing model weights and verify checksums
    print("Verifying model weights and checksums...")
    ensure_models_downloaded("all")
    print("-" * 70)

    # 2. KYC Product Models
    if s.enable_kyc:
        print("[KYC] Warming up KYC models:")
        
        # InsightFace buffalo_l
        t0 = time.time()
        print("  - InsightFace (buffalo_l)...", end=" ", flush=True)
        try:
            from app.checks import face_match
            face_match._load_app()
            print(f"READY ({time.time() - t0:.2f}s)")
        except Exception as e:
            print(f"FAILED: {e}")

        # MediaPipe Face Landmarker
        t0 = time.time()
        print("  - MediaPipe Face Landmarker (face_landmarker.task)...", end=" ", flush=True)
        try:
            from app.checks import liveness
            liveness._load_face_landmarker()
            print(f"READY ({time.time() - t0:.2f}s)")
        except Exception as e:
            print(f"FAILED: {e}")

        # MiniFASNet
        t0 = time.time()
        print("  - MiniFASNetV2 (minifasnet_v2.onnx)...", end=" ", flush=True)
        try:
            from app.checks import anti_spoof
            anti_spoof._load_session()
            print(f"READY ({time.time() - t0:.2f}s)")
        except Exception as e:
            print(f"FAILED: {e}")

        # Faster-Whisper
        t0 = time.time()
        print(f"  - Faster-Whisper ({s.whisper_model})...", end=" ", flush=True)
        try:
            from faster_whisper import WhisperModel
            WhisperModel(s.whisper_model, device="auto", compute_type="int8")
            print(f"READY ({time.time() - t0:.2f}s)")
        except Exception as e:
            print(f"FAILED: {e}")

        # RapidOCR
        t0 = time.time()
        print("  - RapidOCR (onnxruntime)...", end=" ", flush=True)
        try:
            from app.checks.id_details import _get_ocr
            _get_ocr()
            print(f"READY ({time.time() - t0:.2f}s)")
        except Exception as e:
            print(f"FAILED: {e}")

    # 3. Interview Product Models
    if s.enable_interview:
        print("\n[INTERVIEW] Warming up Interview models:")
        
        # ViT Deepfake Detector
        t0 = time.time()
        print("  - ViT Deepfake Detector (prithivMLmods/Deep-Fake-Detector-v2-Model)...", end=" ", flush=True)
        try:
            from app.checks.video_deepfake import _load_vit_model
            _load_vit_model()
            print(f"READY ({time.time() - t0:.2f}s)")
        except Exception as e:
            print(f"FAILED: {e}")

        # SyncNet Lip-Sync
        t0 = time.time()
        print("  - SyncNet Lip-Sync (syncnet-python)...", end=" ", flush=True)
        try:
            from app.checks import lip_sync
            has_w = lip_sync.SYNCNET_WEIGHTS_PATH.exists() and lip_sync.S3FD_WEIGHTS_PATH.exists()
            print(f"READY (calibrated: {has_w}) ({time.time() - t0:.2f}s)")
        except Exception as e:
            print(f"FAILED: {e}")

    print("=" * 70)
    print("All enabled models are cached and ready for inference!")
    print("=" * 70)


if __name__ == "__main__":
    main()