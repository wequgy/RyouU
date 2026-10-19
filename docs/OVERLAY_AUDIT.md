# RyouU Meeting Overlay - Architecture & Codebase Audit

**Date:** 2026-10-19  
**Target:** `apps/overlay` (previously `RyouU_Meeting_Overlay-main`) & KYC Backend Integration  
**Status:** Audit Complete — Pre-Implementation Phase

---

## 1. Executive Summary

This audit assesses the current state of the interview meeting overlay desktop application (`apps/overlay`), its capture subsystem, security posture, machine learning dependencies, and integration with the RyouU KYC verification platform. 

The audit confirms major architectural vulnerabilities, non-standard fallbacks, security hazards, and unpinned dependencies. This document establishes the technical baseline before initiating code modifications.

---

## 2. Inventory of Claimed Checks vs. Actual Implementation

| Claimed Capability | Actual Implementation | Assessment & Deficiencies |
| :--- | :--- | :--- |
| **Video Deepfake Detection** | `verify_deepfake.py` running `openai/clip-vit-large-patch14` zero-shot text classification. | **Critical Flaw**: CLIP vision-language model with prompt pairs ("an authentic live webcam video..." vs. "an AI generated deepfake...") is **not** a deepfake detector. It measures semantic similarity to prompt strings. The hardcoded 70% threshold is arbitrary and uncalibrated. Each 25s clip spawns a new Python process and reloads the ~1.7 GB PyTorch model from disk. |
| **Voice Deepfake Detection** | `detectifai_verifier.py` calling Detectif.ai Aletheia API (`/v1/deepfake/detect`). | Cloud integration functions when configured, but contains a local acoustic heuristic fallback (`scipy.signal.spectrogram` high-frequency energy ratio) when offline. |
| **Speaker Identity Verification** | `detectifai_verifier.py` calling Detectif.ai Eidos API (`/v1/speakers/enroll` and `/v1/speakers/verify`) via Supabase gateway. | Cloud integration functions when configured, but falls back to local FFT spectral slice cosine similarity (`_local_speaker_verification`). Spectral slice cosine is **not** a valid biometric voiceprint and produces false matches/rejections. |
| **Face Identity Verification** | **Missing entirely** from overlay. | No facial embedding or comparison against KYC enrollment or round-1 snapshot exists in the overlay desktop app. |
| **Lip Synchronization** | **Missing entirely** from overlay. | No SyncNet or audio-visual sync verification exists in the overlay. |
| **Loop / Replay Detection** | **Missing entirely** from overlay. | No frame sequence repetition or frozen video detection exists. |
| **Second Person / Helper** | **Missing entirely** from overlay. | No multi-face detection, gaze tracking, or background typing sound analysis. |

---

## 3. Capture Mechanism & Subsystems

### 3.1 Candidate Tile Selection
- **Implementation**: `picker.html` + `picker.js` opens a full-screen transparent window (`BrowserWindow` across primary display bounds).
- **Coordinate Flow**: User drags a rectangular marquee over the candidate's video tile in Zoom/Teams/Meet. The window captures mouse events and sends `{x, y, width, height}` back to `main.js` via IPC (`capture:select-region`).
- **Validation**: `main.js` validates bounds $\ge 40 \times 40$ px and clamps to display size.

### 3.2 Video Capture
- **Implementation**: `desktopCapturer.getSources({ types: ["screen"] })` selects the display source matching `displayId`.
- **Cropping**: In `renderer.js`, an off-screen HTML5 `<video>` receives the full screen stream. A `<canvas>` sized to `selectedRegion.width × selectedRegion.height` renders the cropped slice via `ctx.drawImage(video, cropX, cropY, cropW, cropH, 0, 0, targetW, targetH)` at 30 fps via `requestAnimationFrame`.
- **Recording**: A `MediaRecorder` encodes the canvas stream into `video/webm;codecs=vp8` (or `vp9`) in 25-second chunks.

### 3.3 System Audio Loopback
- **Implementation**: `session.defaultSession.setDisplayMediaRequestHandler` overrides getDisplayMedia permissions to request `{ video: sources[0], audio: "loopback" }`.
- **Mixed Audio Hazard**: `navigator.mediaDevices.getDisplayMedia({ audio: true, video: ... })` captures all system audio. If the interviewer speaks through their computer speaker/headphones, the loopback audio mixes the interviewer's voice with the candidate's voice.
- **Current Behavior**: The system sends this mixed audio track directly to Detectif.ai, risking scoring the interviewer's voice against the candidate's voiceprint.

---

## 4. Meeting App Detection

- **Current Implementation**:
  ```javascript
  execFile("tasklist", ["/FI", "IMAGENAME eq Zoom.exe", "/NH"], ...)
  ```
- **Platform Limitation**: Hardcoded to Windows `tasklist` command and specifically `Zoom.exe`.
- **Deficiencies**:
  - Incompatible with macOS (`pgrep` / AppleScript) and Linux (`ps` / `pgrep`).
  - Does not detect Microsoft Teams, Google Meet (browser-based), or Webex.
  - No fallback for manual window selection if process detection fails.

---

## 5. Security Posture & Secrets Management

- **Credentials Exposure**:
  - Detectif.ai API keys (`DETECTIF_API_KEY`) and Supabase credentials (`SUPABASE_URL`, `SUPABASE_KEY`) reside directly on the interviewer's desktop inside `.env`.
  - Anyone with access to the interviewer machine or binary can extract these enterprise provider keys.
- **Client Machine Prerequisites**:
  - Interviewers must have a full Python 3.10+ installation with PyTorch (~2.5 GB), torchvision, transformers, and opencv-python on their system `PATH`.
  - Process execution via `child_process.execFile("python", ...)` fails if Python is not on PATH or has missing packages.
- **Electron Security Flags**:
  - `contextIsolation: true` is enabled.
  - `nodeIntegration: false` is enabled.
  - `sandbox: true` is **not** explicitly configured.
  - Content Security Policy (CSP) is **missing** from HTML files (`index.html`, `picker.html`).
  - `safeStorage` is **not** used; tokens/secrets are plaintext in memory or environment files.
  - Dependencies in `package.json` are unpinned: `"electron": "*"`.

---

## 6. Personal & Test Media Hygiene

The following media files were identified in the overlay repository and root:
1. `RyouU_Meeting_Overlay-main/Harsha_Testing.mp4` (339 KB) — Personal webcam test recording.
2. `RyouU_Meeting_Overlay-main/Test_Audio.m4a` (341 KB) — Personal voice clip.
3. `RyouU_Meeting_Overlay-main/Test_Audio.mp4` (341 KB) — Personal media recording.
4. Root test artifacts: `clip.mp4`, `id.jpeg`, `other_person.jpeg`, `selfie1.jpg`.

*Action*: All personal test media must be removed from the project tree and git tracking.

---

## 7. Confirmed Architectural Deficiencies to Remedy

| ID | Issue | Severity | Remediation Plan |
| :--- | :--- | :--- | :--- |
| **AUD-01** | Desktop holds provider keys & runs local PyTorch | Critical | Move all ML models and Detectif keys to FastAPI KYC backend. Desktop receives only short-lived tenant session tokens. |
| **AUD-02** | Zero-shot CLIP used as deepfake detector | Critical | Replace with GenD + ViT Classifier (`Deep-Fake-Detector-v2-Model`) running on the server. |
| **AUD-03** | Local spectral cosine voice fallback | High | Remove spectral fallbacks. Return `uncertain` with explicit diagnostic reason when audio cannot be analyzed. |
| **AUD-04** | Mixed interviewer/candidate audio | High | Add Voice Activity Gating + Detectif verify matching so interviewer speech is never scored as the candidate. |
| **AUD-05** | Missing identity & liveness checks | High | Implement server-side InsightFace facial consistency, SyncNet lip-sync, and deterministic frame hash loop detection. |
| **AUD-06** | Windows-only Zoom tasklist detection | Medium | Expand detection across Windows, macOS, and Linux for Zoom, Teams, and Meet, plus window picker option. |
| **AUD-07** | Unpinned Electron & missing CSP | Medium | Pin Electron to stable LTS, enable sandbox, safeStorage, and strict CSP. |
| **AUD-08** | Inconsistent UI aesthetics | Medium | Extract design tokens from `flow.html` into shared CSS custom properties. Standardize compact overlay UI. |
| **AUD-09** | Fragmented data storage | Medium | Unify KYC and Interview sessions under a single relational database schema with versioned migrations. |

---

*This audit document serves as the specification baseline for Phases 1 through 5.*
