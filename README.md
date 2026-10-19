# Unclone — AI Biometric Identity & Interview Integrity Suite

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11-blue.svg?logo=python&logoColor=white)](https://python.org)
[![Electron](https://img.shields.io/badge/Electron-31.3.0-47848F.svg?logo=electron&logoColor=white)](https://electronjs.org)
[![Security](https://img.shields.io/badge/Security-Fernet%20AES--128--CBC%20%2B%20safeStorage-critical.svg)](https://cryptography.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Unclone** is an enterprise-grade, modular identity verification and technical interview integrity monorepo. It features state-of-the-art anti-spoofing defense, 3D active liveness verification, deepfake detection, real-time meeting overlay monitoring, and multi-platform native SDKs.

> [!IMPORTANT]
> **InsightFace Non-Commercial Notice**:
> Pretrained weights for InsightFace (`buffalo_l`) are licensed strictly for non-commercial academic research and demonstration evaluation purposes. Any commercial production deployment must replace these weights with commercially licensed models or custom-trained weights. See [NOTICE](NOTICE) for details.

---

## Suite Products & Decoupled Deployments

Unclone offers two independent products that can be deployed standalone or together:

1. **Unclone KYC (`services/api/app/kyc`)**:
   Asynchronous document OCR (RapidOCR), active/passive 3D facial liveness (MediaPipe FACS blendshapes + MiniFASNet anti-spoofing), ArcFace face matching, and spoken phrase verification.
2. **Unclone Interview Integrity (`services/api/app/interview` & `apps/overlay`)**:
   Real-time desktop meeting overlay (Zoom, Teams, Meet) detecting video injection, second person in frame, lip-sync mismatch (SyncNet), and synthetic cloned voice (Detectif.ai).

### Deployment Modes

A deployment mounts only enabled routes and loads only enabled neural models:

| Deployment Mode | Environment Configuration | Mounted Endpoints | Loaded Models |
| :--- | :--- | :--- | :--- |
| **KYC Only** | `ENABLE_KYC=true`<br>`ENABLE_INTERVIEW=false` | `/v1/verifications`, `/flow`, `/v1/policies`, `/v1/reviews` | InsightFace (`buffalo_l`), MediaPipe Landmarker, MiniFASNet v2, RapidOCR, Faster-Whisper |
| **Overlay Only** | `ENABLE_KYC=false`<br>`ENABLE_INTERVIEW=true` | `/v1/interviews`, `/v1/interviews/{id}/clips`, `/v1/interviews/{id}/token` | ViT Deepfake Detector, SyncNet Lip-Sync, Detectif.ai |
| **Dual Product** | `ENABLE_KYC=true`<br>`ENABLE_INTERVIEW=true` | All endpoints mounted | All models loaded (cross-product face baseline linked via `reference_id`) |

---

## Monorepo Layout

```
unclone-suite/
├── services/
│   └── api/
│       ├── app/
│       │   ├── core/           # Health, readyz, tenants, scoped API keys
│       │   ├── kyc/            # Verifications, flow, challenges, policies, reviews
│       │   ├── interview/      # Interviews, stream clips, interviewer tokens
│       │   ├── checks/         # Modular AI verification engines
│       │   └── migrations/     # Versioned SQLite & Postgres migration runner
│       └── tests/
│           ├── core/           # API keys, tenant isolation, migrations, contracts
│           ├── kyc/            # 3D liveness, gates, OCR, anti-spoof, security
│           └── interview/      # Overlay security, clips, loop detection
├── apps/
│   └── overlay/                # Electron meeting monitor (stores credentials via safeStorage)
├── sdks/
│   └── kyc/
│       ├── python/             # Python backend client & webhook verifier
│       ├── node/               # TypeScript / Node.js backend client
│       ├── react-native/       # React Native cross-platform flow wrapper
│       └── android/            # Native Kotlin Android SDK
├── packages/
│   └── design-tokens/          # Shared CSS design variables (tokens.css)
├── contracts/                  # OpenAPI baseline schema and client contracts
├── eval/                       # Benchmark and verification evaluation scripts
├── docs/                       # ARCHITECTURE.md, RUN_DEMO.md, SUITE_DATA_MODEL.md, MODELS.md
└── deploy/                     # Production Dockerfile, docker-compose.yml, .env.example
```

---

## Security Principles & Hardening Rules

1. **API Gateway Sole Authority**: No client application (desktop overlay, mobile SDK, hosted verification page) ever holds a database key or a Supabase key. The API is the single door to data.
2. **Overlay Credential Isolation**: The desktop overlay never holds a tenant API key. It receives only a short-lived token scoped strictly to `interview:*`, stored using Electron `safeStorage` (OS-level DPAPI/Keytar) and automatically refreshed before expiry. The overlay token is unconditionally rejected by all `/v1/verifications` and `/flow` endpoints.
3. **Fail-Secure Rule**: Any check that encounters an unhandled exception or lacks sufficient data returns `uncertain`, **never** `pass`.
4. **Tenant Isolation & Key Scopes**: Tenant API keys are stored only as SHA-256 hashes with granular permission scopes (`kyc:*`, `interview:*`, `admin:*`).
5. **No Tenant Key Under Overlay**: Enforced by static code and integration tests (`apps/overlay/tests/overlay_rules.test.js`).

---

## Quickstart

### 1. Installation

```bash
# Clean install with all dependencies
pip install -e ".[all]"

# Download verified model weights (SHA-256 checksummed)
python -m scripts.download_models

# Run preflight diagnostics
python -m scripts.preflight
```

### 2. Running the API

```bash
# Dual product mode
uvicorn services.api.app.main:app --port 8000 --reload
```

### 3. Running the Desktop Overlay

```bash
cd apps/overlay
npm install
npm start
```

### 4. Running the Complete Test Suite

```bash
# Run all backend tests (Core, KYC, Interview)
pytest services/api/tests/ -v

# Run overlay security and UI rules test
node --test apps/overlay/tests/overlay_rules.test.js

# Verify all imports are declared in pyproject.toml
python scripts/check_undeclared_imports.py
```

---

## Detailed Documentation

- [System Architecture & Threat Model](docs/ARCHITECTURE.md)
- [Running Demos (KYC Only, Overlay Only, Dual)](docs/RUN_DEMO.md)
- [Data Model & Versioned Migrations](docs/SUITE_DATA_MODEL.md)
- [AI Models, Licenses & Thresholds](docs/MODELS.md)

---

## License

This project is licensed under the [MIT License](LICENSE). See [NOTICE](NOTICE) for third-party model weights and licenses.
