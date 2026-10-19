---
title: Quickstart (15 Minutes)
description: End-to-end integration walkthrough from self-hosted Docker container to mobile app and signed webhook verification.
---

# Quickstart (15 Minutes)

This 15-minute quickstart walks you through launching the RyouU API, minting a tenant key, initiating a verification session on your server, launching the hosted flow in a mobile client, and validating the signed HMAC webhook.

---

## 1. Launch the RyouU API with Docker

Clone the monorepo and start the core service alongside PostgreSQL:

```bash
git clone https://github.com/wequgy/RyouU.git
cd RyouU
docker compose up -d
```

Verify that the local service is healthy and all neural models have preloaded into memory:

```bash
curl http://localhost:8000/readyz
```

Expected response:
```json
{"status": "ready", "models_loaded": true}
```

---

## 2. Create a Tenant with Scoped Keys

Generate a tenant API key and webhook secret for your development environment:

```bash
python scripts/create_tenant.py --name "DevFintech" --scopes "kyc:*,interview:*"
```

Output:
```text
Tenant created successfully!
Tenant ID:      ten_7a8109bf
API Key:        kyc_live_92f0ab1c8e3...
Webhook Secret: whsec_4d82b17a...
```

::: danger IMPORTANT
Store `API Key` and `Webhook Secret` exclusively on your backend server. Never commit them to source control or embed them in mobile client binaries.
:::

---

## 3. Server: Create a Verification Session

Call `POST /v1/verifications` from your backend to initiate a session with user expected identity details:

::: code-group

```python [Python]
from unclone_kyc import Client

client = Client(
    api_key="kyc_live_92f0ab1c8e3...",
    base_url="http://localhost:8000"
)

session = client.create_verification(
    reference_id="usr_4821",
    expected={
        "name": "Alex Morgan",
        "dob": "1995-08-20",
        "id_last4": "4821"
    },
    policy="strict",
    idempotency_key="tx_req_001"
)

print("Verification ID:", session.id)
print("Client Flow URL:", session.flow_url)
```

```typescript [Node.js / TypeScript]
import { UncloneKycClient } from '@unclone/kyc-node';

const client = new UncloneKycClient({
  apiKey: 'kyc_live_92f0ab1c8e3...',
  baseUrl: 'http://localhost:8000',
});

const session = await client.createVerification({
  referenceId: 'usr_4821',
  expected: {
    name: 'Alex Morgan',
    dob: '1995-08-20',
    idLast4: '4821',
  },
  policy: 'strict',
  idempotencyKey: 'tx_req_001',
});

console.log('Verification ID:', session.id);
console.log('Client Flow URL:', session.flow_url);
```

:::

Pass `session.flow_url` down to your mobile client.

---

## 4. Mobile Client: Launch the Verification Flow

The user completes ID document capture and active biometric liveness inside an isolated WebView modal.

::: warning HTTPS Requirement on Mobile Devices
Modern mobile browsers and WebViews restrict camera and microphone access to secure origins (`https://` or `localhost`). When testing from physical mobile devices or Android emulators connecting to a host machine, expose your local server over HTTPS using a tunnel (e.g. `ngrok http 8000` or Cloudflare Tunnel).
:::

::: code-group

```tsx [React Native / Expo]
import React, { useState } from 'react';
import { View, Button } from 'react-native';
import { UncloneKycModal, KycResult } from '@unclone/kyc-react-native';

export function OnboardingScreen() {
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
      <Button title="Start Verification" onPress={() => setModalOpen(true)} />

      <UncloneKycModal
        visible={modalOpen}
        config={{ backendUrl: 'https://api.yourfintech.com' }}
        params={{
          referenceId: 'usr_4821',
          name: 'Alex Morgan',
          dob: '1995-08-20',
        }}
        onComplete={(result: KycResult) => {
          setModalOpen(false);
          console.log('Result:', result.status, result.verificationId);
        }}
        onCancel={() => setModalOpen(false)}
        onError={(err) => console.error('KYC Modal Error:', err)}
      />
    </View>
  );
}
```

```kotlin [Android (Kotlin Compose)]
import androidx.compose.runtime.*
import androidx.compose.material3.Button
import androidx.compose.material3.Text
import com.ryouu.kyc.model.KycConfig
import com.ryouu.kyc.model.KycParams
import com.ryouu.kyc.model.KycStatus
import com.ryouu.kyc.ui.RyouUKycModal

@Composable
fun OnboardingScreen() {
    var showModal by remember { mutableStateOf(false) }

    Button(onClick = { showModal = true }) {
        Text("Verify Identity")
    }

    RyouUKycModal(
        visible = showModal,
        config = KycConfig(backendUrl = "https://api.yourfintech.com"),
        params = KycParams(
            referenceId = "usr_4821",
            name = "Alex Morgan",
            dob = "1995-08-20"
        ),
        onComplete = { result ->
            showModal = false
            when (result.status) {
                KycStatus.SUCCESS -> { /* Verification approved */ }
                KycStatus.IN_REVIEW -> { /* Manual review required */ }
                KycStatus.FAILED -> { /* Verification failed */ }
                KycStatus.CANCELLED -> { /* Dismissed */ }
            }
        },
        onCancel = { showModal = false },
        onError = { err -> showModal = false }
    )
}
```

:::

---

## 5. Server: Receive and Verify Signed Webhooks

When the user finishes the hosted flow, the RyouU server dispatches an HMAC-SHA256 signed HTTP POST event to your configured webhook URL.

::: code-group

```python [Python (FastAPI)]
from fastapi import FastAPI, Request, HTTPException
from unclone_kyc import verify_webhook, WebhookVerificationError

app = FastAPI()
WEBHOOK_SECRET = "whsec_4d82b17a..."

@app.post("/webhooks/kyc")
async def handle_kyc_webhook(request: Request):
    raw_body = await request.body()
    signature_header = request.headers.get("X-KYC-Signature")
    
    try:
        event = verify_webhook(
            body=raw_body,
            signature_header=signature_header,
            secret=WEBHOOK_SECRET,
            tolerance_s=300 # 5-minute replay window
        )
    except WebhookVerificationError as err:
        raise HTTPException(status_code=400, detail=f"Invalid webhook: {err}")

    # Inspect the verified payload
    event_type = event["type"]
    verification_id = event["data"]["id"]
    decision = event["data"]["final_decision"] or event["data"]["decision"]

    print(f"Verified Event {event_type} for {verification_id} -> Verdict: {decision}")
    return {"received": True}
```

```typescript [Node.js (Express)]
import express from 'express';
import { verifyWebhook, WebhookVerificationError } from '@unclone/kyc-node';

const app = express();
const WEBHOOK_SECRET = 'whsec_4d82b17a...';

app.post('/webhooks/kyc', express.raw({ type: 'application/json' }), (req, res) => {
  const signature = req.headers['x-kyc-signature'] as string;
  try {
    const event = verifyWebhook(req.body, signature, WEBHOOK_SECRET, 300);
    
    const decision = event.data.final_decision ?? event.data.decision;
    console.log(`Verified KYC Event for ${event.data.id} -> Verdict: ${decision}`);
    
    res.json({ received: true });
  } catch (err) {
    if (err instanceof WebhookVerificationError) {
      return res.status(400).send('Invalid signature');
    }
    return res.status(500).send('Internal error');
  }
});
```

:::

---

## 6. Testing with the Built-in Demo Client

You can run the simulated tenant client in `demo_client/` to observe real webhook delivery and verification polling without writing frontend code:

```bash
python -m demo_client.app --port 9000
```

Open `http://localhost:9000` in your browser, enter sample user identity details, and click **Start KYC Verification**.
