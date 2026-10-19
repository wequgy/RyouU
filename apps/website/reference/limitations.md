---
title: Limitations & Responsibilities
description: Honest engineering limits, signal calibration status, licensing notices, and legal compliance responsibilities.
---

Honesty matters more than polish. RyouU does not claim to be "unbreakable", "100% accurate", or to "stop all fraud". Identity verification is a **layered, server-enforced, human-in-the-loop** defense system.

---

## 1. Probabilistic Signals & Weak Indicators

Several checks in the RyouU platform rely on machine learning heuristics that are inherently probabilistic:

- **Visual Deepfake Detection**: Generalization across diverse webcam sensors, compression artifacts, and studio lighting varies. Deepfake scores are a **weak signal** intended exclusively to flag suspicious sessions for manual human inspection.
- **Lip Synchronization (SyncNet)**: Audio-video synchronization scoring can degrade on low-bandwidth networks, asynchronous Bluetooth headsets, or non-English speech patterns.
- **Passive Anti-Spoofing (PAD)**: The pretrained MiniFASNet model detects printed paper and digital screens, but thresholds are **uncalibrated** against wide consumer camera distributions until benchmarked on your specific domain dataset.
- **Voice Clone Detection**: Detectif.ai synthetic speech analysis is optimized primarily for English-language speech; accuracy on regional dialects and accented speech is lower.

> [!IMPORTANT]
> **Because these signals are probabilistic, they NEVER issue an automated denial recommendation (`rejected_recommended`).** They can only transition a verification to `needs_review`.

---

## 2. Licensing Notice on InsightFace

Pretrained `buffalo_l` weights from InsightFace are restricted to **non-commercial academic research and evaluation**.

Production enterprise deployments must substitute these weights with commercially licensed face matching models or train custom embeddings on CC-BY datasets. All other local models bundled with RyouU (`face_landmarker.task`, `minifasnet_v2.onnx`, `rapidocr`, `faster-whisper`) use permissive open-source licenses (**Apache 2.0** or **MIT**).

---

## 3. External Infrastructure Requirements

- **SMS OTP Delivery**: RyouU does not bundle free SMS credits. Production telephone verification requires credentials from an SMS gateway that you configure (e.g. Twilio or Fast2SMS).
- **Detectif.ai API**: Voice deepfake analysis and speaker verification require an active account and API key with Detectif.ai.
- **HTTPS on Mobile**: Physical Android and iOS devices will strictly refuse camera and microphone access on non-HTTPS origins. You must terminate SSL on your public domain or configure an HTTPS tunnel.

---

## 4. Compliance and Your Responsibilities

> [!WARNING]
> **RyouU makes NO automated compliance certifications.**
> Deploying RyouU does not automatically satisfy regulatory requirements such as:
> - Reserve Bank of India (RBI) V-CIP regulations
> - European Union General Data Protection Regulation (GDPR)
> - India Digital Personal Data Protection (DPDP) Act
> - Illinois Biometric Information Privacy Act (BIPA)
>
> RyouU provides technical infrastructure (face comparison, active liveness tracking, encrypted evidence storage, and audit logs). **Customers are strictly responsible for conducting their own legal and compliance review** to determine whether their deployment, retention periods, and consent disclosures satisfy applicable laws.
