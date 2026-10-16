# Custom KYC SDK Integration Guide

This directory contains the integration pathways, architecture contracts, and native bridge templates for connecting any **Custom KYC / Identity Verification SDK** into ApexPay.

> **Note on Vendor Independence**: Razorpay is **NOT** integrated. Instead, a clean, vendor-agnostic gateway architecture (`IKycSdkGateway`) is provided so you can connect your own in-house, native, or third-party verification SDK.

---

## Architecture Overview

```
+-----------------------------------------------------------+
|                   Fintech App Layer                       |
|           (Launch Interceptor / Dashboard)               |
+-----------------------------------------------------------+
                              |
                              v
+-----------------------------------------------------------+
|             <SecureDisplayLayer> (DRM Shield)             |
|   - Android FLAG_SECURE / WindowManager Hardware Blackout |
|   - iOS UIScreen.isCaptured Detection & Canvas Shield     |
+-----------------------------------------------------------+
                              |
                              v
+-----------------------------------------------------------+
|                    KycGatewayRegistry                     |
|           (Pluggable Singleton SDK Manager)               |
+-----------------------------------------------------------+
                              |
      +-----------------------+-----------------------+
      |                                               |
      v                                               v
[Your Custom SDK Gateway]                 [Mock Custom SDK Gateway]
(IKycSdkGateway implementation)             (Default reference)
```

---

## Quick Start: Integrating Your Custom SDK

### Step 1: Implement `IKycSdkGateway` (or extend `BaseKycSdkAdapter`)

Create a new file, e.g., `src/sdk/custom/MyCompanyKycGateway.ts`:

```typescript
import { BaseKycSdkAdapter } from '../adapters/BaseKycSdkAdapter';
import { KycSessionPayload, KycSdkResult } from '../../types';

export class MyCompanyKycGateway extends BaseKycSdkAdapter {
  readonly id = 'my-company-kyc';
  readonly name = 'My Company Identity SDK';
  readonly version = '2.1.0';

  public async launchKycFlow(payload: KycSessionPayload): Promise<KycSdkResult> {
    this.ensureInitialized();

    // 1. Call your custom SDK (native bridge, React Native library, or Webview)
    // Example:
    // const response = await NativeModules.CustomKycNativeModule.startNativeKycSession({
    //   apiKey: this.config?.apiKey,
    //   userId: payload.userId,
    //   docType: payload.docType,
    // });

    // 2. Map and return the standardized result:
    return {
      status: 'SUCCESS',
      verificationId: 'VERIF-XYZ-123',
      timestamp: Date.now(),
      riskScore: 0.01,
    };
  }
}
```

### Step 2: Register in `KycGatewayRegistry`

In your application entry or configuration file (e.g. `App.tsx` or `index.ts`):

```typescript
import { KycGatewayRegistry } from './src/sdk/core/KycGatewayRegistry';
import { MyCompanyKycGateway } from './src/sdk/custom/MyCompanyKycGateway';

// Instantiate and register
const myGateway = new MyCompanyKycGateway();
KycGatewayRegistry.registerGateway(myGateway);

// Set as active
KycGatewayRegistry.setActiveGateway(myGateway.id);
```

### Step 3: Native Android / iOS Integration

If your SDK includes compiled native libraries:
- **Android**: Reference `src/sdk/native-bridges/android/CustomKycSdkModule.kt` to bind your `.aar` or Gradle dependency. `FLAG_SECURE` is automatically set on the Activity window to black out screen casting.
- **iOS**: Reference `src/sdk/native-bridges/ios/CustomKycSdkBridge.swift` to bind your `.xcframework` or CocoaPod. Screen capture state is monitored via `UIScreen.capturedDidChangeNotification`.

---

## Anti-Screencasting Protection Explained

Streaming platforms like Netflix, Prime Video, and banking apps prevent screencasting and screen recording by invoking OS-level hardware protections:

1. **Android**: When `FLAG_SECURE` (`WindowManager.LayoutParams.FLAG_SECURE`) is active:
   - Screen recording software captures solid black frames.
   - Screencasting (Chromecast, Miracast, HDMI, scrcpy) blanks out.
   - Android system screenshots are blocked with a toast: *"Can't take screenshot due to security policy"*.
   - App previews in the Recent Apps switcher are obscured.

2. **iOS**:
   - `UIScreen.isCaptured` actively detects if screen recording, AirPlay screencasting, or QuickTime capture is active.
   - When detected, the `SecureDisplayLayer` displays the DRM blackout shield immediately.
   - The hardware container pattern (`UITextField(isSecureTextEntry = true)`) hardware-protects the subview layer.
