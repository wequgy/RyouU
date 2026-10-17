# Running the RyouU KYC Live Demo

This guide provides the exact step-by-step commands to run the complete end-to-end KYC identity verification stack:
1. **Core KYC Backend API** (FastAPI, Port 8000)
2. **Customer Fintech Backend** (`demo_client`, Port 9000)
3. **Cloudflare Tunnel** (for live mobile camera & microphone HTTPS access)
4. **Mobile Fintech App** (`ApexPay_Android` or React Native)

> [!IMPORTANT]
> **Architecture & Security Philosophy**:
> RyouU implements a **layered, server-enforced, human-in-the-loop** defense system. The secret API keys live exclusively in your backend server and are never embedded inside the mobile client or frontend bundle. The system produces automated recommendations (`approved`, `needs_review`, `rejected_recommended`), reserving final decisions for authorized compliance officers.

---

## Prerequisites

1. Python 3.10+ with active virtual environment:
   ```bash
   pip install -r requirements.txt
   ```
2. Cloudflared CLI installed:
   ```bash
   winget install Cloudflare.cloudflared
   ```

---

## Step 1: Preflight Diagnostics & Model Warmup

Verify all local AI models (InsightFace `buffalo_l`, RapidOCR, faster-whisper, ViT deepfake) and Detectif.ai connectivity:

```bash
# Preflight health check
python -m scripts.preflight

# Pre-cache all neural weights
python -m scripts.warmup
```

---

## Step 2: Seed Demo Credentials & Reset Data

Initialize the database with demo tenant credentials:

```bash
python -m scripts.seed_demo
```

This creates:
- **Tenant ID**: `demo_strict`
- **API Key**: `kyc_demo_strict_key`
- **Default Policy**: `strict`

---

## Step 3: Start the Core KYC Service (Port 8000)

```bash
uvicorn app.main:app --port 8000 --reload
```

Health check verification:
- URL: `http://localhost:8000/readyz`

---

## Step 4: Expose KYC Service via HTTPS Cloudflare Tunnel

Live camera streams (`getUserMedia`) in modern browsers and WebViews strictly mandate an HTTPS context:

```bash
cloudflared tunnel --url http://localhost:8000
```

Copy the generated trycloudflare URL (e.g. `https://your-tunnel.trycloudflare.com`).

Set this in your environment or `.env`:
```bash
PUBLIC_BASE_URL="https://your-tunnel.trycloudflare.com"
```

---

## Step 5: Start the Reference Customer Backend (Port 9000)

The customer backend securely issues session tokens using the secret API key and receives signed webhook callbacks:

```bash
uvicorn demo_client.app:app --port 9000 --reload
```

---

## Step 6: Launch the Fintech Mobile App (ApexPay)

The mobile application communicates exclusively with the customer backend on Port 9000 (no KYC secret keys inside):

```bash
cd ApexPay_Android
./gradlew installDebug
```

Inside the app:
1. Tap **Verify Identity**.
2. Complete synchronous ID OCR validation.
3. Perform live selfie capture (file upload blocked).
4. Complete head turn and spontaneous spoken phrase challenge.
5. On completion, the mobile app automatically polls the customer backend (`/kyc/status/{id}`) to fetch the authenticated verdict.

---

## Step 7: Automated Attack Scenarios & Evaluation

Run the automated attack test suite to benchmark defense performance against synthetic manipulation:

```bash
python -m scripts.e2e_demo --all-scenarios
```
