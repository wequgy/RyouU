# Running the Unclone Suite Demos

This guide provides the exact commands to run the **Unclone Suite** across each supported deployment mode:
1. **Mode A: KYC Only Deployment** (`ENABLE_KYC=true`, `ENABLE_INTERVIEW=false`)
2. **Mode B: Overlay / Interview Integrity Only Deployment** (`ENABLE_KYC=false`, `ENABLE_INTERVIEW=true`)
3. **Mode C: Full Dual Product Deployment** (`ENABLE_KYC=true`, `ENABLE_INTERVIEW=true`)

---

## 1. Prerequisites & Environment Setup

```bash
# 1. Clone repository and install dependencies with all extras
pip install -e "services/api[all]"

# 2. Download and verify model weights (SHA-256 verified)
python -m scripts.download_models

# 3. Run preflight diagnostics
python -m scripts.preflight
```

---

## 2. Deployment Modes

### Mode A: KYC Only Deployment

Best for fintech, banking, and crypto onboarding platforms needing only document OCR, 3D liveness, and face matching. Does not mount interview routes or load interview models (ViT deepfake, SyncNet).

```bash
# 1. Install KYC-only dependencies and start the API
pip install -e "services/api[kyc,dev]"
export ENABLE_KYC=true
export ENABLE_INTERVIEW=false
uvicorn app.main:app --port 8000 --reload

# On Windows PowerShell:
# $env:ENABLE_KYC="true"; $env:ENABLE_INTERVIEW="false"; uvicorn app.main:app --port 8000 --reload
```

```bash
# 2. Verify Readyz endpoint returns only KYC models
curl http://127.0.0.1:8000/readyz
# Expected output contains insightface, mediapipe, minifasnet, rapidocr, whisper
# (SyncNet and ViT deepfake are not loaded)
```

```bash
# 3. Run a reference KYC verification session
python -m sdks.kyc.python.example
```

---

### Mode B: Overlay / Interview Integrity Only Deployment

Best for HR, technical recruiting, and proctoring platforms monitoring live technical interviews (Zoom, Teams, Meet). Does not mount KYC verification routes or load KYC models.

```bash
# 1. Install Interview-only dependencies and start the API
pip install -e "services/api[interview,dev]"
export ENABLE_KYC=false
export ENABLE_INTERVIEW=true
uvicorn app.main:app --port 8000 --reload

# On Windows PowerShell:
# $env:ENABLE_KYC="false"; $env:ENABLE_INTERVIEW="true"; uvicorn app.main:app --port 8000 --reload
```

```bash
# 2. Verify Readyz endpoint returns only Interview models
curl http://127.0.0.1:8000/readyz
# Expected output contains vit_deepfake, syncnet, detectif
```

```bash
# 3. Start the Unclone Desktop Overlay
cd apps/overlay
npm install
npm start
```

*Note: In standalone interview mode without prior KYC, the overlay displays `"No KYC baseline"` and performs independent video anomaly, lip-sync, and synthetic voice checks.*

---

### Mode C: Full Dual Product Deployment

Enables both products with cross-product biometric reuse: candidates complete KYC onboarding, and the verified face embedding automatically serves as the baseline for the live interview overlay.

```bash
# 1. Start the API with both products enabled
export ENABLE_KYC=true
export ENABLE_INTERVIEW=true
uvicorn app.main:app --port 8000 --reload

# On Windows PowerShell:
# $env:ENABLE_KYC="true"; $env:ENABLE_INTERVIEW="true"; uvicorn app.main:app --port 8000 --reload
```

```bash
# 2. Seed demo tenant credentials (generated at runtime when KYC_SEED_DEMO=1)
export KYC_SEED_DEMO=1
python -m scripts.seed_demo
# Prints runtime tenant keys: export KYC_API_KEY="<printed_key>"
```

```bash
# 3. Mint short-lived interviewer credential for the overlay
curl -X POST http://127.0.0.1:8000/v1/interviews/int_demo_01/token \
  -H "Authorization: Bearer $KYC_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"candidate_name": "Demo Candidate", "reference_id": "ref_demo_123"}'
# Returns: {"interview_id": "int_demo_01", "token": "itok_...", "expires_at": 1700000000}
```

```bash
# 4. Launch Desktop Overlay with session token (via environment variable; never CLI arguments)
cd apps/overlay
export OVERLAY_TOKEN="itok_..."
npm start -- --interview-id=int_demo_01
# On Windows PowerShell:
# $env:OVERLAY_TOKEN="itok_..."; npm start -- --interview-id=int_demo_01
```

> [!NOTE]
> **Platform Support for Meeting-App Detection**:
> - Windows: Fully tested and active (PowerShell / Win32 process enumeration).
> - macOS and Linux: **UNTESTED** (manual screen/window selection fallback).

---

## 3. Automated Validation & Test Suite

Run the full end-to-end regression and hardening test suite:

```bash
# Full Python test suite (Core, KYC, Interview)
pytest services/api/tests/ -v

# Overlay security & UI rules test
node --test apps/overlay/tests/overlay_rules.test.js

# Undeclared import scanner
python scripts/check_undeclared_imports.py
```
