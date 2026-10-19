---
title: Configuration & Environment Variables
description: Comprehensive catalog of environment variables generated directly from .env.example.
---

RyouU defaults to safe production behaviors when optional variables are omitted. Configure these values in your `.env` file or container orchestrator secrets.

---

## 1. Core System & Storage

| Variable | Default | Description |
| :--- | :--- | :--- |
| **`KYC_DATA_DIR`** | `./data` | Local filesystem path where evidence media and temporary crops are cached. |
| **`KYC_DB_PATH`** | `./kyc.db` | SQLite database path (when PostgreSQL is not used). |
| **`DATABASE_URL`** | `sqlite:///./kyc.db` | Primary PostgreSQL database connection string (`postgresql://user:pass@host:5432/kyc`). |
| **`PUBLIC_BASE_URL`** | `http://localhost:8000` | External URL of the RyouU API gateway used in callbacks. |
| **`FLOW_BASE_URL`** | `http://localhost:8000/flow` | Publicly accessible base URL for the hosted web verification flow. |
| **`KYC_CORS_ORIGINS`** | `*` | Comma-delimited list of allowed browser CORS origins. |
| **`MAX_UPLOAD_MB`** | `25` | Maximum upload size for ID document images and liveness video recordings. |

---

## 2. Security & Product Licensing

| Variable | Default | Description |
| :--- | :--- | :--- |
| **`KYC_DEV_MODE`** | `0` | Set to `1` to bypass SMS/Email OTP delivery and relax liveness constraints. (Never use in production). |
| **`KYC_STRICT`** | `1` | Enables strict gating where hard gate mismatches immediately recommend rejection. |
| **`ENABLE_KYC`** | `1` | Activates KYC verification routes (`/v1/verifications`, `/flow/*`). |
| **`ENABLE_INTERVIEW`** | `1` | Activates Interview Overlay routes (`/v1/interviews/*`). |
| **`KYC_ENFORCE_GATES`**| `1` | Enforces prerequisite order (OTP before document upload, ID before liveness). |

---

## 3. Reviewer Dashboard Authentication

| Variable | Description |
| :--- | :--- |
| **`DASHBOARD_USERNAME`** | Administrative username for the internal compliance reviewer portal. |
| **`DASHBOARD_PASSWORD_HASH`** | Argon2 or bcrypt password hash for reviewer authentication. |

---

## 4. Tenant & Token Expirations

| Variable | Default | Description |
| :--- | :--- | :--- |
| **`FLOW_TOKEN_TTL_S`** | `1800` | Ephemeral client flow token time-to-live in seconds (30 minutes). |
| **`CHALLENGE_TTL_S`** | `300` | Spoken phrase and gesture challenge expiration time in seconds (5 minutes). |

---

## 5. Detectif.ai Voice AI Integration

| Variable | Description |
| :--- | :--- |
| **`DETECTIF_BASE_URL`** | Base URL for Detectif.ai API (`https://platform.detectif.ai`). |
| **`DETECTIF_API_KEY`** | Secret API key provided in your Detectif.ai dashboard. |
| **`DETECTIF_MAX_ATTEMPTS`** | Maximum retry attempts for voice analysis (default: 3). |

---

## 6. SMS & Email OTP Providers

| Variable | Description |
| :--- | :--- |
| **`OTP_TTL_S`** | One-time passcode validity duration (default: 300s). |
| **`OTP_MAX_ATTEMPTS`** | Maximum incorrect code submissions before locking the session (default: 5). |
| **`TWILIO_ACCOUNT_SID`** | Twilio Account SID for international SMS delivery. |
| **`TWILIO_AUTH_TOKEN`** | Twilio Auth Token. |
| **`TWILIO_FROM_NUMBER`** | Twilio registered sender phone number. |
| **`FAST2SMS_API_KEY`** | Fast2SMS API key for Indian regional SMS routing. |
| **`SMTP_HOST`** / **`SMTP_PORT`** | Mail server connection parameters for email OTP delivery. |
