export type KycStatus = 'SUCCESS' | 'IN_REVIEW' | 'FAILED' | 'CANCELLED';
export interface UncloneKycConfig {
    backendUrl: string;
    theme?: 'light' | 'dark' | 'auto';
    timeoutMs?: number;
    pollingIntervalMs?: number;
    maxPollingAttempts?: number;
}
export interface KycStartParams {
    referenceId: string;
    name?: string;
    dob?: string;
    idLast4?: string;
    email?: string;
    phone?: string;
    policy?: 'strict' | 'lenient' | string;
}
export interface KycResult {
    status: KycStatus;
    verificationId: string;
    riskScore?: number | null;
    reasons?: string[];
    rawDecision?: string | null;
    rawFinalDecision?: string | null;
}
export type KycEventType = 'started' | 'flow_opened' | 'submitted' | 'completed' | 'cancelled' | 'error';
export interface KycEvent {
    type: KycEventType;
    verificationId?: string;
    data?: any;
    timestamp: number;
}
export type KycEventListener = (event: KycEvent) => void;
export interface BackendStatusResponse {
    id: string;
    reference_id?: string;
    status: string;
    decision?: string | null;
    final_decision?: string | null;
    trust?: number | null;
    reasons?: string[];
}
