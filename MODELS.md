# Models and Anti-Fraud Architecture

This document catalogs every pretrained AI model, pipeline component, license, size, purpose, and calibrated decision threshold utilized across the **RyouU** KYC platform.

---

## 1. Inventory of Pretrained Models

| Component | Model / Package | Size | License | Purpose | Execution |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Face Analysis & Embeddings** | InsightFace (`buffalo_l`) | ~320 MB | **Non-Commercial** (InsightFace license) | Face detection, 512-dim embedding extraction, landmark_3d_68, and 3D head pose estimation. | CPU (ONNX Runtime) |
| **Speech-to-Text (ASR)** | faster-whisper (`small` / `base`) | ~460 MB | MIT / Apache 2.0 | Spoken details transcription, spontaneous challenge verification. | CPU (CTranslate2 int8) |
| **ID Document OCR** | RapidOCR (`rapidocr-onnxruntime`) | ~15 MB | Apache 2.0 | High-accuracy text extraction and bounding box detection on government ID cards. | CPU (ONNX Runtime) |
| **Visual Deepfake Detection** | ViT Image Classifier (`prithivMLmods/Deep-Fake-Detector-v2-Model`) | ~340 MB | Apache 2.0 | Frame-by-frame deepfake and digital face manipulation probability scoring. | CPU (PyTorch / Transformers) |
| **AI Voice & Speaker Consistency** | Detectif.ai Cloud API | N/A (Cloud) | Commercial API (Sponsor Credits) | Synthetic voice detection (deepfake), speaker enrollment, and cross-clip speaker verification. | Cloud API (HTTPS) |

> [!WARNING]
> **Licensing Notice on InsightFace**:
> The pretrained `buffalo_l` weights from InsightFace are restricted to non-commercial academic research and demonstration evaluation. Production enterprise deployments must substitute with commercially licensed weights (e.g. trained on CC-BY datasets or vendor-provided models).

---

## 2. Decision Thresholds & Calibration

All biometric and anti-fraud signals produce continuous confidence scores calibrated against genuine validation datasets:

### Face Verification (`face_match`)
- **Metric**: Cosine similarity between 512-dimensional InsightFace embeddings.
- **Pass Threshold**: `similarity >= 0.40`
- **Fail Threshold**: `similarity < 0.25` -> `rejected_recommended` (Strict policy)
- **Borderline (Uncertain)**: `0.25 <= similarity < 0.40` -> routed to `needs_review` for human review.

### Synchronous ID OCR Gate (`id_details`)
- **Name Token Match**: RapidFuzz token ratio `>= 80%` (partial ratio `>= 85%`). Every token of entered name must match.
- **DOB Match**: Normalized ISO `YYYY-MM-DD` date parsed from candidate dates on ID must match entered DOB.
- **ID Number Match**: Consecutive digit run on ID must end with entered last 4 digits.
- **Legibility**: Less than 2 text boxes or average confidence `< 0.40` triggers `"Unreadable ID: retake a clearer photo"`.

### Visual Scene Integrity (`scene_integrity`)
- **Multiple Faces**: `>= 2` detected faces (confidence `>= 0.60`, width `>= 40px`) in `>= 20%` of sampled video frames triggers FAIL (second person coaching).
- **Identity Continuity**: Face embedding similarity against verified selfie dropping below `0.30` in `>= 30%` of frames triggers FAIL (face swapping or person substitution).

### Audio-Visual Lip Synchronization (`lip_sync`)
- Inner-lip separation ratio (landmarks 62 & 66 distance divided by horizontal mouth width) compared against PyAV audio RMS energy envelope.
- Lack of lip movement during continuous speech flags `uncertain` ("voice and lips do not line up") for human review. Never hard-fails autonomously.

### AI Voice Detection (`voice_ai`)
- **Detectif Fake Score**: Score `> 0.62` classifies clip as synthetic/cloned voice -> FAIL.
- **Speaker Consistency**: Verified across enrollment clip, spontaneous phrase clip, and details clip. Mismatch flags coaching/impersonation.
