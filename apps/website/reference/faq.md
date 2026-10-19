---
title: FAQ & Changelog
description: Frequently asked questions, changelog, and semantic versioning policy for RyouU.
---

Frequently asked architectural and operational questions about the RyouU identity verification and live interview monitoring platform.

---

## Frequently Asked Questions

### 1. Does RyouU store raw face biometrics in the cloud?
**No.** RyouU is designed for self-hosting. Biometric crops and audio files remain strictly on your own servers or S3-compatible buckets. If external cloud features (like Detectif.ai Voice AI) are disabled, zero biometric media ever leaves your boundary.

### 2. Can RyouU run on CPU-only instances?
**Yes.** All core models (InsightFace ArcFace via ONNX, MediaPipe Face Landmarker, MiniFASNetV2, and RapidOCR) are compiled for CPU execution. A standard 4-core cloud instance can comfortably process 100+ verifications per hour without GPU acceleration.

### 3. How does RyouU handle false-positive deepfake flags?
Probabilistic soft signals (deepfake detection, lip-sync, passive anti-spoofing) can **NEVER** issue an autonomous denial. They only elevate a verification to `needs_review`. Your human compliance officers inspect the high-resolution evidence in your internal dashboard and make the final decision.

### 4. What happens when an external API or model fails?
In accordance with our strict error contract, any runtime exception, timeout, or missing model returns **`uncertain`**, never `pass`. This ensures that service interruptions do not open security bypasses.

---

## Semantic Versioning Policy

RyouU adheres strictly to [Semantic Versioning (SemVer 2.0.0)](https://semver.org/):

- **Major (`X.0.0`)**: Breaking changes to the REST API schema, breaking changes to SDK method signatures, or removals of previously supported check endpoints.
- **Minor (`0.X.0`)**: Backwards-compatible feature additions, new neural model support, or updated detection rules.
- **Patch (`0.0.X`)**: Bug fixes, model weight conversion scripts, security patches, and performance optimizations.

---

## Changelog

### v0.1.0 (Current Release)
- **Initial Open Source Release of RyouU Suite**:
  - Unified server gateway supporting both KYC verification flows and Desktop Interview Overlay sessions.
  - MediaPipe Face Landmarker blendshape active liveness (blinks and 3D head yaw rotation).
  - MiniFASNetV2 passive presentation attack detection (PAD) converted from official Minivision weights to ONNX opset 11.
  - RapidOCR automated government document text extraction and token fuzzy matching.
  - Signed HMAC-SHA256 webhooks with 300s replay tolerance window.
  - Desktop Electron HUD overlay with CLIP ViT-L/14 keyframe deepfake scoring and Detectif.ai voice biometrics.
  - Multi-platform SDKs for Python, Node.js / TypeScript, React Native / Expo, and Android (Kotlin / Jetpack Compose).
