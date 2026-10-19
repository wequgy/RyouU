# Running the Unclone Suite Demos

This guide provides the exact commands to run the **Unclone Suite** across each supported deployment mode:
1. **Mode A: KYC Only Deployment** (`ENABLE_KYC=true`, `ENABLE_INTERVIEW=false`)
2. **Mode B: Overlay / Interview Integrity Only Deployment** (`ENABLE_KYC=false`, `ENABLE_INTERVIEW=true`)
3. **Mode C: Full Dual Product Deployment** (`ENABLE_KYC=true`, `ENABLE_INTERVIEW=true`)

---

## 1. Prerequisites & Environment Setup

```bash
# 1. Clone repository and install dependencies with all extras
pip install -e ".[all]"

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
# 1. Start the API with KYC enabled and Interview disabled
export ENABLE_KYC=true
export ENABLE_INTERVIEW=false
uvicorn services.api.app.main:app --port 8000 --reload

# On Windows PowerShell:
# $env:ENABLE_KYC="true"; $env:ENABLE_INTERVIEW="false"; uvicorn services.api.app.main:app --port 8000 --reload
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
# 1. Start the API with Interview enabled and KYC disabled
export ENABLE_KYC=false
export ENABLE_INTERVIEW=true
uvicorn services.api.app.main:app --port 8000 --reload

# On Windows PowerShell:
# $env:ENABLE_KYC="false"; $env:ENABLE_INTERVIEW="true"; uvicorn services.api.app.main:app --port 8000 --reload
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
uvicorn services.api.app.main:app --port 8000 --reload

# On Windows PowerShell:
# $env:ENABLE_KYC="true"; $env:ENABLE_INTERVIEW="true"; uvicorn services.api.app.main:app --port 8000 --reload
```

```bash
# 2. Seed demo tenant credentials
python -m scripts.seed_demo
# Creates tenant: demo_strict (key: kyc_demo_strict_key)
# Creates tenant: demo_lenient (key: kyc_demo_lenient_key)
```

```bash
# 3. Mint short-lived interviewer credential for the overlay
curl -X POST http://127.0.0.1:8000/v1/interviews/int_demo_01/token \
  -H "Authorization: Bearer kyc_demo_strict_key" \
  -H "Content-Type: application/json" \
  -d '{"candidate_name": "Demo Candidate", "reference_id": "ref_demo_123"}'
# Returns: {"interview_id": "int_demo_01", "token": "itok_...", "expires_at": 1700000000}
```

```bash
# 4. Launch Desktop Overlay with session token
cd apps/overlay
npm start -- --interview-id=int_demo_01 --token=<YOUR_MINTED_TOKEN>
```

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
