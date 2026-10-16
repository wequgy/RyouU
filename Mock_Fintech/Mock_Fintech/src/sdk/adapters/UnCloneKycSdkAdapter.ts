import { BaseKycSdkAdapter } from './BaseKycSdkAdapter';
import {
  KycSessionPayload,
  KycSdkResult,
} from '../../types';
import { NativeModules, Platform } from 'react-native';

export function getDetectedServerUrl(): string {
  // Always prefer secure HTTPS Cloudflare tunnel so Android Chromium WebView enables WebRTC camera
  return 'https://feels-thrown-happen-professional.trycloudflare.com';
}

export interface UnCloneVerificationSession {
  verificationId: string;
  flowUrl: string;
  policy: string;
  status: string;
}

/**
 * UnCloneKycSdkAdapter
 * 
 * Official SDK adapter connecting ApexPay to the UnClone KYC Verification Engine.
 * Supports:
 * - Face match against ID proof (InsightFace)
 * - AI synthetic voice detection (Detectif.ai)
 * - Video deepfake detection
 * - Spoken details vs ID parsing (Whisper)
 * - Phone & email OTP verification
 * - Dynamic randomized spontaneous text challenges
 * - Anti-screencast & source security signals
 */
export class UnCloneKycSdkAdapter extends BaseKycSdkAdapter {
  readonly id = 'unclone-ai-kyc-sdk';
  readonly name = 'UnClone AI Identity SDK';
  readonly version = '2.1.0';

  // Configurable base URL: auto-detects Expo packager host or defaults to Wi-Fi LAN IP
  private apiBase: string = getDetectedServerUrl();
  private apiKey: string = 'kyc_demo_strict_key';

  public setApiBase(url: string): void {
    this.apiBase = url.replace(/\/$/, '');
  }

  public getApiBase(): string {
    return this.apiBase;
  }

  public setApiKey(key: string): void {
    this.apiKey = key;
  }

  /**
   * Creates a live verification session on the UnClone KYC server
   * and returns the session ID and hosted WebView flow URL.
   */
  public async createVerificationSession(payload: KycSessionPayload): Promise<UnCloneVerificationSession> {
    this.emitEvent('INITIALIZED', `Connecting to KYC engine at ${this.apiBase}...`, 1, 4);

    const endpoint = `${this.apiBase}/v1/verifications`;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 8000);

    let response: Response;
    try {
      response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${this.apiKey}`,
        },
        body: JSON.stringify({
          reference_id: payload.userId,
          policy: 'strict',
          expected: {
            name: payload.fullName,
            dob: payload.dob || undefined,
            id_last4: payload.idLast4 || undefined,
          },
        }),
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
    } catch (fetchErr: any) {
      clearTimeout(timeoutId);
      if (fetchErr.name === 'AbortError') {
        throw new Error(`Connection timed out after 8s trying to reach ${this.apiBase}. Ensure your phone is on the same Wi-Fi and server is running.`);
      }
      throw new Error(`Cannot reach KYC engine at ${this.apiBase}: ${fetchErr.message || 'Network request failed'}. Check Wi-Fi connection.`);
    }

    if (!response.ok) {
      const errText = await response.text().catch(() => '');
      throw new Error(`KYC session creation failed (${response.status}): ${errText.slice(0, 150)}`);
    }

    const data = await response.json();
    let flowUrl = data.flow_url;
    if (payload.fullName) flowUrl += `&name=${encodeURIComponent(payload.fullName)}`;
    if (payload.email) flowUrl += `&email=${encodeURIComponent(payload.email)}`;
    if (payload.phone) flowUrl += `&phone=${encodeURIComponent(payload.phone)}`;
    if (payload.dob) flowUrl += `&dob=${encodeURIComponent(payload.dob)}`;
    if (payload.idLast4) flowUrl += `&idLast4=${encodeURIComponent(payload.idLast4)}`;

    return {
      verificationId: data.id,
      flowUrl,
      policy: data.policy,
      status: data.status,
    };
  }

  /**
   * Polls the KYC backend for the final verification result.
   */
  public async pollVerificationStatus(
    verificationId: string,
    maxAttempts = 40,
    intervalMs = 2000
  ): Promise<Record<string, unknown>> {
    const endpoint = `${this.apiBase}/v1/verifications/${verificationId}`;

    for (let i = 0; i < maxAttempts; i++) {
      try {
        const resp = await fetch(endpoint, {
          headers: {
            Authorization: `Bearer ${this.apiKey}`,
          },
        });

        if (resp.ok) {
          const data = await resp.json();
          if (data.status === 'completed' || data.status === 'needs_review' || data.status === 'rejected_recommended') {
            return data;
          }
        }
      } catch (err) {
        // continue polling
      }
      await new Promise((r) => setTimeout(r, intervalMs));
    }

    throw new Error('Verification timed out waiting for backend checks to complete.');
  }

  /**
   * Standard IKycSdkGateway entry point for custom execution.
   */
  public async launchKycFlow(payload: KycSessionPayload): Promise<KycSdkResult> {
    this.ensureInitialized();

    try {
      const session = await this.createVerificationSession(payload);
      this.emitEvent('CAMERA_STARTED', 'KYC session active. Running verification suite...', 2, 4, {
        verificationId: session.verificationId,
        flowUrl: session.flowUrl,
      });

      // Poll for backend completion
      const finalResult = await this.pollVerificationStatus(session.verificationId);
      const isApproved = finalResult.status === 'completed' || finalResult.decision === 'approve';

      this.emitEvent('COMPLETED', `Verification complete (${finalResult.status})`, 4, 4, {
        verificationId: session.verificationId,
      });

      return {
        status: isApproved ? 'SUCCESS' : 'IN_REVIEW',
        verificationId: session.verificationId,
        timestamp: Date.now(),
        riskScore: typeof finalResult.trust === 'number' ? 1 - finalResult.trust : 0.05,
        rawDetails: finalResult,
      };
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Unknown KYC error';
      this.emitEvent('FAILED', `Verification failed: ${msg}`);
      return {
        status: 'FAILED',
        timestamp: Date.now(),
        failureReason: msg,
      };
    }
  }
}
