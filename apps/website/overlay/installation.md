---
title: Installation & Launch (Desktop Overlay)
description: Setting up the RyouU Desktop Overlay for technical interview monitoring on Windows and macOS.
---

The **RyouU Overlay** is a lightweight, non-intrusive desktop HUD designed for interviewers conducting remote coding or technical interviews over Zoom, Google Meet, or Microsoft Teams.

---

## 1. Prerequisites

| Component | Minimum Version | Note |
| :--- | :--- | :--- |
| **Node.js** | v18+ | Electron desktop host runtime. |
| **Python** | 3.10+ | Local video clip analysis and audio processing. |
| **PyTorch CPU** | `torch==2.1+cpu` | CPU-only neural inference (zero GPU required). |
| **Operating System** | Windows 10/11 or macOS 12+ | Hardware screen and microphone capture support. |

---

## 2. Setup & Installation

Navigate to the overlay package in the monorepo:

```bash
cd apps/overlay
npm install
```

Install local Python dependencies for CLIP ViT-L/14 keyframe evaluation:

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install transformers scipy opencv-python pillow python-dotenv
```

---

## 3. Launching the Overlay

Launch the Electron application:

```bash
npm start
```

On first launch:
1. The overlay appears as a compact floating panel on top of your interview meeting window.
2. Click **Select Region** to drag a selection box directly over the candidate's video tile.
3. Enter the candidate's ID (e.g. `candidate-001`) to link the session to their enrolled KYC reference voiceprint.
4. Confirm participant consent before starting monitoring.
