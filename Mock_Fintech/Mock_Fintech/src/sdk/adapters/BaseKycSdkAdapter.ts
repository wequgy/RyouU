import { IKycSdkGateway } from '../core/IKycSdkGateway';
import {
  KycSdkConfig,
  KycSessionPayload,
  KycSdkResult,
  KycSdkEvent,
  KycSdkEventType,
} from '../../types';

/**
 * Base abstract adapter providing event listener subscriptions,
 * state validation, and error normalization for custom KYC SDK implementations.
 */
export abstract class BaseKycSdkAdapter implements IKycSdkGateway {
  abstract readonly id: string;
  abstract readonly name: string;
  abstract readonly version: string;

  protected config: KycSdkConfig | null = null;
  protected isInitialized = false;
  private listeners: Set<(event: KycSdkEvent) => void> = new Set();

  public async isAvailable(): Promise<boolean> {
    return true;
  }

  public async initialize(config: KycSdkConfig): Promise<void> {
    this.config = config;
    this.isInitialized = true;
    this.emitEvent('INITIALIZED', `Initialized ${this.name} (${this.version}) in ${config.environment} mode`);
  }

  public abstract launchKycFlow(payload: KycSessionPayload): Promise<KycSdkResult>;

  public onEvent(listener: (event: KycSdkEvent) => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  protected emitEvent(type: KycSdkEventType, message: string, step?: number, totalSteps?: number, data?: Record<string, unknown>): void {
    const event: KycSdkEvent = {
      type,
      message,
      timestamp: Date.now(),
      step,
      totalSteps,
      data,
    };

    this.listeners.forEach((listener) => {
      try {
        listener(event);
      } catch (err) {
        console.error(`[${this.id}] Error in event listener:`, err);
      }
    });
  }

  public async tearDown(): Promise<void> {
    this.listeners.clear();
    this.isInitialized = false;
    this.config = null;
  }

  protected ensureInitialized(): void {
    if (!this.isInitialized || !this.config) {
      throw new Error(`[${this.id}] SDK must be initialized with config before launching verification.`);
    }
  }
}
