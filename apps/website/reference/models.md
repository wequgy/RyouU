---
title: AI Models & Licences
description: Complete catalog of pretrained neural models, weights, licenses, sizes, runtimes, and calibration metrics.
---

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
> Pretrained `buffalo_l` weights from InsightFace are restricted to non-commercial academic research and evaluation. Production enterprise deployments must substitute with commercially licensed weights. All other local models (`face_landmarker.task`, `minifasnet_v2.onnx`, `rapidocr`, `faster-whisper`, ViT Deepfake, `syncnet-python`) use permissive open source licenses (**Apache 2.0** or **MIT**).

---

## 2. Threshold Calibration & Measurements

| Check / Signal | Parameter / Metric | Threshold Value | Calibration State | Benchmark Metric |
| :--- | :--- | :--- | :--- | :--- |
| **`face_match`** | Cosine similarity | `pass >= 0.40`<br>`fail < 0.25`<br>`review [0.25, 0.40)` | **Calibrated** (ArcFace standard benchmark) | FAR &lt; 0.001% @ 0.40 on LFW / RyouU synthetic regression suite |
| **`id_details`** | Name token match<br>DOB match<br>ID number match<br>OCR box count | RapidFuzz `&gt;= 80%`<br>Exact ISO date<br>Ends with last 4 digits<br>`boxes &gt;= 2`, conf `&gt;= 0.40` | **Calibrated** (Locked regression suite) | 100% precision on locked test suite (17/17 tests passing) |
| **`liveness` (Blink)** | MediaPipe blendshape peak | `baseline &lt; 0.20`, `peak &gt;= 0.45` | **Calibrated** (MediaPipe Face Landmarker) | Measured on synthetic/webcam blink streams |
| **`liveness` (Head Turn)** | InsightFace pose yaw | `\|yaw\| &gt;= 15&deg;` in direction, static check | **Calibrated** (3D head pose estimation) | Measured on synthetic/webcam head turn streams |
| **`anti_spoof`** | MiniFASNet spoof probability | `spoof_score &gt; 0.50` -> review | **UNCALIBRATED** (Pretrained Silent-Face default) | **NOT MEASURED** on domain webcam dataset |
| **`video_deepfake`** | ViT fake score (16 frames) | Average fake score `&gt; 0.50` -> review | **UNCALIBRATED** (HF zero-shot classifier default) | **NOT MEASURED** on production video streams |
| **`lip_sync`** | SyncNet offset / mouth-RMS | Ratio during speech `&lt; 0.015` -> review | **UNCALIBRATED** (Heuristic envelope alignment) | **NOT MEASURED** on production multi-accent dataset |
| **`voice_ai`** | Detectif fake score | `fake_score &gt; 0.62` -> review | **Calibrated** (Detectif.ai vendor API default) | Vendor reported ROC-AUC: **NOT MEASURED** internally |
| **`scene_integrity`** | Multi-face / identity drop | `&gt;= 2` faces in `&gt; 20%` frames;<br>sim `&lt; 0.30` in `&gt; 30%` frames | **Calibrated** (InsightFace similarity + count) | Locked regression verified |
