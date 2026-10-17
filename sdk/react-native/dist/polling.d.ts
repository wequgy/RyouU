import { KycResult } from './types';
export interface PollingOptions {
    backendUrl: string;
    verificationId: string;
    timeoutMs?: number;
    initialIntervalMs?: number;
    maxIntervalMs?: number;
    maxAttempts?: number;
    fetchFn?: typeof fetch;
    signal?: AbortSignal;
}
export declare function pollVerificationStatus(options: PollingOptions): Promise<KycResult>;
