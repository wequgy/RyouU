# @unclone/kyc-react-native

Production-ready React Native and Expo SDK for the Unclone Identity Verification Service.

## Features
- **Zero API Secrets in Mobile Client**: The app only connects to your backend server (`${backendUrl}/kyc/session` and `${backendUrl}/kyc/status/${id}`).
- **Hardened Verdict Mapping**: Status is evaluated exclusively from server decisions (`approved` -> `SUCCESS`, `needs_review`/`rejected_recommended` -> `IN_REVIEW`, `rejected` -> `FAILED`).
- **Anti-Screencast Protection**: Automatically activates `FLAG_SECURE` screen recording prevention while the verification modal is open.
- **Expo Config Plugin**: Automatically injects required Android `CAMERA` and `RECORD_AUDIO` permissions and iOS `NSCameraUsageDescription` / `NSMicrophoneUsageDescription`.
- **Runtime Permission Requests**: Automatically requests hardware camera and microphone permissions on Android.

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

## Usage

### 1. Programmatic API
```typescript
import { UncloneKyc } from '@unclone/kyc-react-native';

const kyc = new UncloneKyc({
  backendUrl: 'https://api.yourfintech.com', // Your backend, NOT the secret KYC server
});

// Optional: listen to progress events
kyc.on('event', (ev) => console.log('KYC Event:', ev.type));

try {
  const result = await kyc.start({
    referenceId: 'user_4821',
    name: 'Alex Morgan',
    dob: '1995-08-20',
    idLast4: '4821',
    email: 'alex@example.com',
    phone: '+1234567890',
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

### 2. Modal Component
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
        config={{ backendUrl: 'https://api.yourfintech.com' }}
        params={{
          referenceId: 'user_4821',
          name: 'Alex Morgan',
          dob: '1995-08-20',
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
