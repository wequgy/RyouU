---
title: Signal Tiles & What They Mean
description: Explanation of real-time monitoring tiles, status colors, and anomaly reasons in the overlay.
---

The RyouU Desktop Overlay displays three live status capsules and an anomaly count badge.

---

## 1. Modality Status Capsules

| Capsule / Tile | Monitored Modality | Normal State | Warning / Anomaly State |
| :--- | :--- | :--- | :--- |
| **`Video`** | Facial synthetic artifacts & deepfake generation via CLIP ViT-L/14. | Green: `Authentic Face` (`real >= 0.70`) | Red: `Visual Deepfake Flagged` (`real < 0.70`) |
| **`Voice`** | Synthetic voice clones & text-to-speech audio via Detectif.ai Aletheia. | Green: `Natural Speech` | Red: `Synthetic Speech Detected` |
| **`Speaker`** | Cross-clip biometrics matching candidate KYC voiceprint via Detectif.ai Eidos. | Green: `Identity Match` | Red: `Speaker Voice Mismatch` |

---

## 2. Status Color System

- **Green (`var(--signal-clear)`)**: All checks in the latest recorded clip evaluated cleanly within thresholds.
- **Amber (`var(--signal-caution)`)**: Video or audio quality was degraded (e.g. poor lighting, excessive background room noise, or frame drops).
- **Red (`var(--signal-flag)`)**: A statistical threshold anomaly was triggered (e.g. high synthetic audio probability or mismatching speaker embedding).

---

## 3. Flag Alert Banner & Counter

When an anomaly triggers:
1. A **Flag Alert Banner** expands with the model name, confidence score, and specific reason (e.g. `Voice Deepfake (91% synthetic probability)`).
2. The **Suspicious Clips Badge** increments (e.g. `🚩 2 flagged`).
3. Recordings are saved locally to `%USERPROFILE%\Videos\RyouU Recordings` for subsequent review by engineering hiring managers.
