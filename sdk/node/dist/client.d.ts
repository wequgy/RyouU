import { ClientOptions, CreateVerificationParams, EvidenceManifest, ReviewVerificationParams, VerificationResult, VerificationSession } from './types';
import { verifyWebhook } from './webhook';
export declare class UncloneKycClient {
    readonly apiKey: string;
    readonly baseUrl: string;
    readonly timeoutMs: number;
    readonly maxRetries: number;
    constructor(options: ClientOptions);
    private request;
    /**
     * Create a new KYC verification session.
     */
    createVerification(params: CreateVerificationParams): Promise<VerificationSession>;
    /**
     * Get the verification status and decision results.
     */
    getVerification(verificationId: string): Promise<VerificationResult>;
    /**
     * List recent verifications.
     */
    listVerifications(params?: {
        limit?: number;
    }): Promise<VerificationResult[]>;
    /**
     * Delete a verification and purge all associated evidence.
     */
    deleteVerification(verificationId: string): Promise<boolean>;
    /**
     * Submit a human review override ('approved' or 'rejected').
     */
    reviewVerification(verificationId: string, params: ReviewVerificationParams): Promise<VerificationResult>;
    /**
     * Fetch signed expiring evidence URLs for this verification.
     */
    getEvidence(verificationId: string): Promise<EvidenceManifest>;
    /**
     * Static helper to verify webhook signatures.
     */
    static verifyWebhook: typeof verifyWebhook;
}
