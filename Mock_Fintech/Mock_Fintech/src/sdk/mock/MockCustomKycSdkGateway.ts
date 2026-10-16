import { BaseKycSdkAdapter } from '../adapters/BaseKycSdkAdapter';
import {
  KycSessionPayload,
  KycSdkResult,
} from '../../types';

/**
 * MockCustomKycSdkGateway
 * 
 * Reference implementation of IKycSdkGateway.
 * Demonstrates the exact gateway pathway and integration hooks for plugging in
 * your custom verification SDK (Native module, React Native library, or Webview).
 * 
 * Strict instruction: DO NOT integrate Razorpay. This gateway is designed
 * specifically for custom identity / KYC verification SDKs.
 */
export class MockCustomKycSdkGateway extends BaseKycSdkAdapter {
  readonly id = 'custom-identity-sdk-v1';
  readonly name = 'Custom KYC Verification Engine';
  readonly version = '1.4.0';

  private activeSessionCancelled = false;

  public async isAvailable(): Promise<boolean> {
    // Check hardware biometric/camera capabilities or native module presence
    return true;
  }

  /**
   * Cancel an ongoing verification session.
   */
  public cancelSession(): void {
    this.activeSessionCancelled = true;
    this.emitEvent('USER_CANCELLED', 'User cancelled the verification flow');
  }

  /**
   * Launches the KYC verification session.
   * 
   * ===========================================================================
   * [INTEGRATE YOUR CUSTOM SDK HERE]
   * ===========================================================================
   * If you have a custom native SDK (e.g. Kotlin/Swift wrapper or npm package),
   * you replace the simulation steps below with your SDK's native method call.
   * 
   * Example:
   * ```ts
   * import { NativeModules } from 'react-native';
   * const { CustomKycNativeModule } = NativeModules;
   * 
   * const nativeResult = await CustomKycNativeModule.startKyc({
   *   apiKey: this.config?.apiKey,
   *   environment: this.config?.environment,
   *   userId: payload.userId,
   *   docType: payload.docType,
   *   sessionNonce: payload.clientNonce,
   * });
   * 
   * return {
   *   status: nativeResult.isSuccess ? 'SUCCESS' : 'FAILED',
   *   verificationId: nativeResult.verificationId,
   *   timestamp: Date.now(),
   *   riskScore: nativeResult.riskScore,
   * };
   * ```
   * ===========================================================================
   */
  public async launchKycFlow(payload: KycSessionPayload): Promise<KycSdkResult> {
    this.ensureInitialized();
    this.activeSessionCancelled = false;

    try {
      // Step 1: Camera & Sensor Initialization
      await this.sleep(400);
      if (this.activeSessionCancelled) return this.createCancelledResult();
      this.emitEvent('CAMERA_STARTED', 'Secure camera feed initialized', 1, 4);

      // Step 2: Document Optical Recognition (OCR) & Hologram capture
      await this.sleep(800);
      if (this.activeSessionCancelled) return this.createCancelledResult();
      this.emitEvent(
        'DOCUMENT_CAPTURED',
        `${payload.docType.replace('_', ' ')} scan captured with high clarity`,
        2,
        4,
        { docType: payload.docType, checksumValid: true }
      );

      // Step 3: Biometric 3D Liveness & Passive Face Match
      await this.sleep(900);
      if (this.activeSessionCancelled) return this.createCancelledResult();
      this.emitEvent(
        'LIVENESS_CHECK_STARTED',
        '3D active liveness & anti-spoofing analysis running',
        3,
        4
      );

      await this.sleep(700);
      if (this.activeSessionCancelled) return this.createCancelledResult();
      this.emitEvent('BIOMETRICS_VERIFIED', 'Facial biometric matched document photo (Confidence: 99.4%)', 3, 4);

      // Step 4: AML / PEP Screening & Secure Cryptographic Attestation
      await this.sleep(600);
      if (this.activeSessionCancelled) return this.createCancelledResult();
      this.emitEvent('DATA_SUBMITTED', 'Attestation sent to secure compliance ledger', 4, 4);

      await this.sleep(300);
      const verificationId = `KYC-${Date.now().toString(36).toUpperCase()}-${Math.floor(Math.random() * 8999 + 1000)}`;

      this.emitEvent('COMPLETED', `Verification successfully approved (#${verificationId})`, 4, 4, {
        verificationId,
      });

      return {
        status: 'SUCCESS',
        verificationId,
        timestamp: Date.now(),
        riskScore: 0.02,
        rawDetails: {
          matchedName: payload.fullName,
          docType: payload.docType,
          complianceTier: 'TIER_1_VERIFIED',
          facialMatchConfidence: 0.994,
          amlCleared: true,
        },
      };
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : 'Unknown KYC error';
      this.emitEvent('FAILED', `Verification failed: ${errorMsg}`);
      return {
        status: 'FAILED',
        timestamp: Date.now(),
        failureReason: errorMsg,
      };
    }
  }

  private createCancelledResult(): KycSdkResult {
    return {
      status: 'CANCELLED',
      timestamp: Date.now(),
      failureReason: 'Verification cancelled by user',
    };
  }

  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}
