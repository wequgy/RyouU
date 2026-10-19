# Models and Anti-Fraud Architecture

This document catalogs every pretrained AI model, pipeline component, license, size, purpose, runtime, and calibration status across the **RyouU** KYC and interview integrity platform.

---

## 1. Inventory of Pretrained Models

| Component | Model / Package | Artifact / Source | Size | License | Purpose | Execution |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Face Analysis & Embeddings** | InsightFace (`buffalo_l`) | `~/.insightface/models/buffalo_l/` | ~320 MB | **Non-Commercial** (InsightFace license) | Face detection (SCRFD 10GF), 512-dim embedding extraction (ArcFace w600k), 3D 68-point landmarks, and head pose estimation. | CPU (ONNX Runtime) |
| **Face Landmarker & Blendshapes** | MediaPipe Face Landmarker | `models/face_landmarker.task` | 3.75 MB | **Apache 2.0** | 52 facial blendshapes (`eyeBlinkLeft`, `eyeBlinkRight`), 478 3D landmarks for real-time blink and movement liveness. Pinned v1 asset. | CPU (TFLite / XNNPACK) |
| **Passive Anti-Spoofing** | MiniFASNetV2 (Silent-Face-Anti-Spoofing) | `models/minifasnet_v2.onnx` | 1.74 MB | **Apache 2.0** (Copyright 2020 Minivision) | Presentation attack detection (PAD), print/replay spoof classification via multi-scale face crops. Converted from official `2.7_80x80_MiniFASNetV2.pth` via `scripts/convert_minifasnet.py`. | CPU (ONNX Runtime) |
| **ID Document OCR** | RapidOCR (`rapidocr-onnxruntime`) | Python package bundled models | ~15 MB | **Apache 2.0** | High-accuracy text bounding box detection and OCR on government ID cards. | CPU (ONNX Runtime) |
| **Speech-to-Text (ASR)** | faster-whisper (`base.en` / `small`) | HuggingFace / CTranslate2 | ~140 MB (`base.en`) / ~460 MB (`small`) | **MIT / Apache 2.0** | Spontaneous challenge phrase verification and spoken detail transcription. | CPU (CTranslate2 int8) |
| **Visual Deepfake Detection** | ViT Image Classifier (`prithivMLmods/Deep-Fake-Detector-v2-Model`) | HuggingFace Hub / PyTorch cache | ~340 MB | **Apache 2.0** | Multi-frame face crop deepfake and generative manipulation probability scoring. | CPU (PyTorch / Transformers) |
| **Lip Synchronization** | SyncNet (`syncnet-python`) | `syncnet-python` / pipeline | Pipeline package | **MIT** | Audio-visual synchronization scoring between lip movement and speech audio envelope. | CPU (PyTorch) |
| **AI Voice & Speaker Consistency** | Detectif.ai Cloud API | Cloud REST API (`api.detectif.ai`) | Cloud API | **Commercial API** (Sponsor Credits) | Synthetic voice detection (deepfake), speaker enrollment, and cross-clip speaker verification. | Cloud API (HTTPS) |

> [!WARNING]
> **Licensing Notice on InsightFace**:
> Pretrained `buffalo_l` weights from InsightFace are restricted to non-commercial academic research and evaluation. Production enterprise deployments must substitute with commercially licensed weights (e.g. trained on CC-BY datasets or vendor-provided models). All other local models (`face_landmarker.task`, `minifasnet_v2.onnx`, `rapidocr`, `faster-whisper`, ViT Deepfake, `syncnet-python`) use permissive open source licenses (**Apache 2.0** or **MIT**).

---

## 2. Third-Party Attributions & Licenses

### MiniFASNetV2 (Silent-Face-Anti-Spoofing)
- **Repository**: [minivision-ai/Silent-Face-Anti-Spoofing](https://github.com/minivision-ai/Silent-Face-Anti-Spoofing)
- **Copyright**: Copyright (c) 2020 Minivision
- **License**: Apache License, Version 2.0
- **Model Checksum (SHA-256)**: `d7b3cd9ba8a7ceb13baa8c4720902e27ca3112eff52f926c08804af6b6eecc7b`
- **Conversion**: Generated via `scripts/convert_minifasnet.py` (PyTorch -> ONNX opset 11 at 80x80 resolution, verified numerical tolerance < 1e-4).
- **Runtime**: ONNX Runtime only (zero PyTorch dependency in production KYC).

### MediaPipe Face Landmarker
- **Source**: Google MediaPipe Model Asset Bundle (`float16/1/face_landmarker.task`)
- **License**: Apache License, Version 2.0
- **Model Checksum (SHA-256)**: `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff`

---

## 3. Decision Policy & Signal Constraints

To protect against false-positive automated denials and ensure compliance with regulatory standards:

1. **Hard Gates vs. Soft Signals**:
   - **Hard Mismatches** (`id_details`, `face_match`, OTP failure, gate prerequisites) are the **ONLY** checks permitted to output `rejected_recommended`.
   - **Model-Based Signals** (`video_deepfake`, `anti_spoof`, `lip_sync`, `scene_integrity`, `liveness`) can **ONLY** push a verification to `needs_review` (or remain `pass` / `uncertain`). They **NEVER** issue an autonomous `rejected_recommended`.

2. **Strict Failure Semantics**:
   - Any runtime error, missing model file, timeout, unparseable input, or insufficient frame count strictly returns **`uncertain`**, never `pass`.
   - Silent fallbacks and swallowed exceptions (`except Exception: pass`) are strictly forbidden. If a model fails to load, it is reported by name in diagnostics and returns `uncertain`.
