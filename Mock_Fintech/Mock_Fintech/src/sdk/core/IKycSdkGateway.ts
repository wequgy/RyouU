import {
  KycSdkConfig,
  KycSessionPayload,
  KycSdkResult,
  KycSdkEvent,
} from '../../types';

/**
 * Interface definition for KYC SDK Gateways.
 * 
 * Any custom SDK (e.g. In-house identity verification, native AAR SDK, 
 * web-based secure view, or third-party vendor SDK) must implement this contract.
 * Note: Razorpay is NOT integrated; this provides the gateway path for custom SDKs.
 */
export interface IKycSdkGateway {
  /** Unique identifier of the gateway (e.g. 'custom-biometric-sdk') */
  readonly id: string;

  /** Human-readable display name of the SDK (e.g. 'Apex Verified ID SDK') */
  readonly name: string;

  /** Semantic version string of the SDK */
  readonly version: string;

  /**
   * Checks whether the SDK is supported on the current device and platform.
   */
  isAvailable(): Promise<boolean>;

  /**
   * Initializes the SDK with customer credentials, environment, and styling configurations.
   */
  initialize(config: KycSdkConfig): Promise<void>;

  /**
   * Launches the KYC verification session.
   * Returns a promise that resolves with the verification result once completed, failed, or cancelled.
   */
  launchKycFlow(payload: KycSessionPayload): Promise<KycSdkResult>;

  /**
   * Subscribes to granular KYC lifecycle events (camera start, document captured, liveness check, etc.).
   * Returns an unsubscribe function.
   */
  onEvent(listener: (event: KycSdkEvent) => void): () => void;

  /**
   * Tears down any active SDK sessions, camera feeds, or native resources.
   */
  tearDown(): Promise<void>;
}
