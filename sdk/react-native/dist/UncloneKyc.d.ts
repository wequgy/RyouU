import { KycEventListener, KycEventType, KycResult, KycStartParams, UncloneKycConfig } from './types';
export declare class UncloneKyc {
    readonly config: UncloneKycConfig;
    private listeners;
    private abortController;
    private activeVerificationId;
    constructor(config: UncloneKycConfig);
    /**
     * Register an event listener.
     * e.g. kyc.on('event', fn) or kyc.on('flow_opened', fn)
     */
    on(event: KycEventType | 'event', listener: KycEventListener): () => void;
    private emit;
    /**
     * Request native Camera and Audio permissions at runtime on Android.
     */
    requestPermissions(): Promise<boolean>;
    /**
     * Enable anti-screencast / FLAG_SECURE layer while KYC is active.
     */
    private enableSecurityShield;
    /**
     * Restore screen capture when KYC completes or cancels.
     */
    private disableSecurityShield;
    /**
     * Create a verification session by calling customer backend POST /kyc/session.
     */
    createSession(params: KycStartParams): Promise<{
        id: string;
        flowUrl: string;
    }>;
    /**
     * Start a complete KYC verification flow.
     */
    start(params: KycStartParams): Promise<KycResult>;
    /**
     * Cancel the currently active KYC verification.
     */
    cancel(): void;
}
