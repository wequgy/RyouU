---
title: Security & Privacy Model
description: Detailed technical review of authentication, cryptographic signatures, data isolation, and encrypted storage.
---

RyouU is built on zero-trust and defense-in-depth principles. This document outlines the technical safeguards implemented across the codebase.

---

## 1. Authentication & API Key Scopes

API keys are generated with high entropy (256-bit random bytes) and stored as salted hashes (Argon2id). They follow a granular permission scope model:

- `kyc:*` or `kyc:create`, `kyc:read`
- `interview:*` or `interview:create`, `interview:write`
- `admin:*` (tenant management and secret rotation)

Client applications (mobile apps, WebViews) are **never** issued API keys. They receive short-lived flow tokens (`flow_tok_...`, 30-minute validity) restricted to submitting data for their specific verification session.

---

## 2. Inbound and Outbound Cryptography

- **Transport Security**: In production mode (`KYC_DEV_MODE=0`), the server enforces HTTPS and rejects plain HTTP connections.
- **Webhook Signatures**: Webhooks use `HMAC-SHA256` computed over the raw payload and UNIX timestamp. A 300-second sliding replay tolerance protects against replay attacks.
- **Interviewer Tokens**: The desktop overlay authenticates with short-lived HMAC-signed tokens minted by the customer backend, preventing desktop compromise from affecting tenant credentials.

---

## 3. Sandboxing & WebView Isolation

In our mobile SDKs:
- **`FLAG_SECURE`**: The React Native and Android SDKs activate hardware screen recording protection to prevent malicious screen-mirroring malware from capturing candidate documents.
- **Origin Isolation**: WebViews are locked to the specific `flow_url` origin. File access, arbitrary URL navigation, and external intent launching are disabled.
- **Zero Client Verdict Authority**: JavaScript bridge messages cannot mark a verification as approved. Only authenticated server-to-server queries determine the verdict.
