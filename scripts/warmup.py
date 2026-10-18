"""Warm up and pre-load all AI models.

Caches models and prints load time for each:
1. InsightFace (buffalo_l)
2. MediaPipe Face Landmarker (face_landmarker.task)
3. MiniFASNet (minifasnet_v2.onnx)
4. Faster-Whisper (small / configured model)
5. RapidOCR (onnxruntime detection + recognition)
6. ViT Deepfake Detector (prithivMLmods/Deep-Fake-Detector-v2-Model)
"""
import time
from app.config import get_settings


def main():
    s = get_settings()
    print("=" * 70)
    print("RyouU KYC Model Warmup & Cache Initialization")
    print("=" * 70)

    # 1. InsightFace buffalo_l
    t0 = time.time()
    print("Loading InsightFace buffalo_l...", end=" ", flush=True)
    from app.checks import face_match
    face_match._load_app()
    print(f"DONE ({time.time() - t0:.2f}s)")

    # 2. MediaPipe Face Landmarker
    t0 = time.time()
    print("Loading MediaPipe Face Landmarker...", end=" ", flush=True)
    from app.checks import liveness
    liveness._load_face_landmarker()
    print(f"DONE ({time.time() - t0:.2f}s)")

    # 3. MiniFASNet
    t0 = time.time()
    print("Loading MiniFASNetV2 (Silent-Face-Anti-Spoofing)...", end=" ", flush=True)
    from app.checks import anti_spoof
    anti_spoof._load_session()
    print(f"DONE ({time.time() - t0:.2f}s)")

    # 4. Faster-Whisper
    t0 = time.time()
    print(f"Loading faster-whisper ({s.whisper_model})...", end=" ", flush=True)
    from faster_whisper import WhisperModel
    WhisperModel(s.whisper_model, device="auto", compute_type="int8")
    print(f"DONE ({time.time() - t0:.2f}s)")

    # 5. RapidOCR
    t0 = time.time()
    print("Loading RapidOCR (onnxruntime)...", end=" ", flush=True)
    from app.checks.id_details import _get_ocr
    _get_ocr()
    print(f"DONE ({time.time() - t0:.2f}s)")

    # 6. ViT Deepfake Detector
    t0 = time.time()
    print("Loading ViT Deepfake Detector...", end=" ", flush=True)
    try:
        from app.checks.video_deepfake import _load_vit_model
        _load_vit_model()
        print(f"DONE ({time.time() - t0:.2f}s)")
    except Exception as e:
        print(f"FAILED: {e}")

    print("=" * 70)
    print("All required models are cached and ready for inference!")
    print("=" * 70)


if __name__ == "__main__":
    main()