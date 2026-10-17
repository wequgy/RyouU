"""Warm up and pre-load all AI models.

Downloads/loads:
1. InsightFace (buffalo_l)
2. faster-whisper (small / configured model)
3. RapidOCR (onnxruntime detection + recognition)
4. ViT deepfake detector (prithivMLmods/Deep-Fake-Detector-v2-Model)
Prints the load time for each model.
"""
import time
from app.config import get_settings


def main():
    s = get_settings()
    print("=" * 60)
    print("RyouU KYC Model Warmup & Cache Initialization")
    print("=" * 60)

    # 1. InsightFace buffalo_l
    t0 = time.time()
    print("Loading InsightFace buffalo_l...", end=" ", flush=True)
    from app.checks import face_match
    face_match._load_app()
    print(f"DONE ({time.time() - t0:.2f}s)")

    # 2. Faster-Whisper
    t0 = time.time()
    print(f"Loading faster-whisper ({s.whisper_model})...", end=" ", flush=True)
    from faster_whisper import WhisperModel
    WhisperModel(s.whisper_model, device="auto", compute_type="int8")
    print(f"DONE ({time.time() - t0:.2f}s)")

    # 3. RapidOCR
    t0 = time.time()
    print("Loading RapidOCR (onnxruntime)...", end=" ", flush=True)
    from app.checks.id_details import _get_ocr
    _get_ocr()
    print(f"DONE ({time.time() - t0:.2f}s)")

    # 4. ViT Deepfake detector
    t0 = time.time()
    print("Loading ViT Deepfake Detector...", end=" ", flush=True)
    try:
        from app.checks.video_deepfake import _load
        _load()
        print(f"DONE ({time.time() - t0:.2f}s)")
    except Exception as e:
        print(f"FAILED: {e}")

    print("=" * 60)
    print("All required models are cached and ready for inference!")
    print("=" * 60)


if __name__ == "__main__":
    main()