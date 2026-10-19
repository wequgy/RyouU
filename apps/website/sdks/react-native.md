---
title: React Native & Expo SDK
description: Mobile client SDK for React Native and Expo with anti-screencast protection and hardware biometric grants.
---

The `@unclone/kyc-react-native` package provides an in-app WebView modal that launches the hosted verification flow. It features built-in screen capture prevention (`FLAG_SECURE`) and handles runtime permissions automatically.

---

## Installation

```bash
npx expo install @unclone/kyc-react-native react-native-webview expo-screen-capture
```

Add the plugin to your `app.json` (or `app.config.js`):

```json
{
  "expo": {
    "plugins": [
      "@unclone/kyc-react-native"
    ]
  }
}
```

---

## 1. Modal Component Integration

```tsx
import React, { useState } from 'react';
import { View, Button } from 'react-native';
import { UncloneKycModal, KycResult } from '@unclone/kyc-react-native';

export function VerifyScreen() {
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
      <Button title="Verify Identity" onPress={() => setModalOpen(true)} />

      <UncloneKycModal
        visible={modalOpen}
        config={{
          backendUrl: 'https://api.yourfintech.com', // Your backend, NOT the secret KYC server
        }}
        params={{
          referenceId: 'user_4821',
          name: 'Alex Morgan',
          dob: '1995-08-20',
          idLast4: '4821',
        }}
        onComplete={(result: KycResult) => {
          setModalOpen(false);
          console.log('Verification Result:', result.status, result.verificationId);
        }}
        onCancel={() => setModalOpen(false)}
        onError={(err) => console.error('KYC Modal Error:', err)}
      />
    </View>
  );
}
```

---

## 2. Programmatic API

```typescript
import { UncloneKyc } from '@unclone/kyc-react-native';

const kyc = new UncloneKyc({
  backendUrl: 'https://api.yourfintech.com',
});

// Listen to progress events
kyc.on('event', (ev) => console.log('KYC Event:', ev.type));

try {
  const result = await kyc.start({
    referenceId: 'user_4821',
    name: 'Alex Morgan',
    dob: '1995-08-20',
    idLast4: '4821',
  });

  if (result.status === 'SUCCESS') {
    console.log('User approved! Verification ID:', result.verificationId);
  } else if (result.status === 'IN_REVIEW') {
    console.log('Sent to manual review:', result.reasons);
  } else if (result.status === 'FAILED') {
    console.log('Verification failed:', result.reasons);
  }
} catch (err) {
  console.error('KYC Error:', err);
}
```

---

## 3. Security Highlights

- **Zero Secret Key Exposure**: The mobile app communicates solely with your customer backend (`/kyc/session` and `/kyc/status`).
- **Cryptographic Isolation**: When the hosted flow completes, the SDK polls your server to read the authentic verdict rather than trusting client-side JavaScript messages.
- **Anti-Screencast Shield**: Automatically enables Android `FLAG_SECURE` while the modal is visible to prevent screen mirroring and background recorder capture.
