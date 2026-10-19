---
title: Merge It Into Your Product
description: Production integration checklist, common architectural mistakes, and deployment mode extras.
---

Integrating biometric identity verification requires strict architectural discipline. Review this checklist and common pitfalls before launching to production.

---

## 1. Production Integration Checklist

| Verification Stage | Requirement | Verified |
| :--- | :--- | :---: |
| **Credentials** | Tenant API keys (`kyc_live_...`) exist only in secure server environment variables. | [ ] |
| **Client Secrets** | Zero secret keys are compiled into Android APKs, iOS bundles, or React Native apps. | [ ] |
| **Origins** | The verification flow runs strictly over HTTPS on custom domains or internal tunnels. | [ ] |
| **Webhooks** | Inbound webhooks are authenticated via HMAC-SHA256 signatures with 300s replay tolerance. | [ ] |
| **Verdict Logic** | Decision logic inspects `final_decision ?? decision === "approved"`, never `status === "completed"`. | [ ] |
| **Client Isolation** | The mobile client never trusts WebView `window.postMessage` to grant account permissions; it polls the backend for server verification. | [ ] |
| **Retention** | Storage lifecycle policies are configured to purge raw biometric evidence according to customer retention guidelines. | [ ] |
| **Human Review** | A queue or dashboard is configured to triage all verifications that land in `needs_review`. | [ ] |

---

## 2. Common Architectural Mistakes to Avoid

### 1. Secret Key in the Mobile App
**The Anti-Pattern**: Initializing the server-side SDK directly in React Native or Android using `KYC_API_KEY`.  
**The Danger**: Attackers can decompile APKs in seconds, extract your tenant key, and generate arbitrary verifications or deplete your quota.  
**The Fix**: Only your customer backend holds `KYC_API_KEY`. The mobile app talks solely to your customer backend (`/kyc/session` and `/kyc/status`).

### 2. Trusting the In-App WebView Message
**The Anti-Pattern**: Reading `{ type: "KYC_COMPLETE", success: true }` from WebView JavaScript messages and immediately granting account access.  
**The Danger**: A malicious user on a rooted device can inject JavaScript into the WebView to emit fake completion messages.  
**The Fix**: The mobile client treats WebView events only as an indicator to close the UI modal, then asks your server: `GET /kyc/status/{id}`.

### 3. Treating `completed` as `approved`
**The Anti-Pattern**: Writing `if (session.status === "completed") { activateUser(); }`.  
**The Danger**: A session that completed all checks but failed due to a fake document or high deepfake probability has `status: "completed"` and `decision: "needs_review"` or `"rejected_recommended"`.  
**The Fix**: Check `const verdict = session.final_decision ?? session.decision; if (verdict === "approved") ...`.

### 4. Running Without HTTPS in Mobile Environments
**The Anti-Pattern**: Pointing Android or iOS WebViews to `http://192.168.1.x:8000`.  
**The Danger**: Mobile OS WebViews strictly block WebRTC, camera, and microphone hardware access on insecure HTTP origins.  
**The Fix**: Terminate SSL on your server or use an HTTPS tunnel (e.g. `ngrok http 8000`) during development.

### 5. Skipping Webhook Signature Validation
**The Anti-Pattern**: Parsing the webhook JSON body directly without verifying the `X-KYC-Signature` header.  
**The Danger**: Attackers can send fake webhook POST requests directly to your webhook endpoint to approve fraudulent accounts.  
**The Fix**: Use `verify_webhook(body, signature, secret, tolerance_s=300)` from the official SDKs.

### 6. Using Demo Keys or Dev Mode in Production
**The Anti-Pattern**: Leaving `KYC_DEV_MODE=1` or using default seeded demo keys in live environments.  
**The Danger**: Dev mode bypasses SMS OTP delivery and relaxes liveness thresholds.  
**The Fix**: Set `KYC_DEV_MODE=0` and generate production keys via `python scripts/create_tenant.py`.

---

## 3. Deployment Modes & Extras

RyouU supports modular packaging. Install only the dependencies required for your deployment profile:

```bash
# Core API and database models only (lightweight, zero ML packages)
pip install -e .

# Full KYC pipeline (InsightFace, MediaPipe, RapidOCR, MiniFASNet)
pip install -e ".[kyc]"

# Live Interview Desktop Overlay & audio verification
pip install -e ".[interview]"

# Complete suite with all ML models and development utilities
pip install -e ".[all]"
```

| Deployment Mode | Included Capabilities | Typical Infrastructure |
| :--- | :--- | :--- |
| **KYC Only** (`ENABLE_KYC=1`, `ENABLE_INTERVIEW=0`) | Document OCR, face match, active 3D liveness, anti-spoofing, hosted web flow. | 2–4 CPU cores, 4 GB RAM, Docker container. |
| **Interview Only** (`ENABLE_KYC=0`, `ENABLE_INTERVIEW=1`) | Desktop HUD overlay, video clip ViT classifier, Detectif.ai voice/speaker integration. | Interviewer workstations (Windows/macOS) + lightweight server. |
| **Unified Suite** (`ENABLE_KYC=1`, `ENABLE_INTERVIEW=1`) | Complete end-to-end identity onboarding and continuous interview integrity monitoring. | 4–8 CPU cores, 8 GB RAM, PostgreSQL database. |
