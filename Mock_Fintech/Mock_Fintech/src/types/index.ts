export type UserKycStatus = 'NOT_STARTED' | 'PENDING_REVIEW' | 'VERIFIED' | 'REJECTED';

export type KycTier = 'Tier 0 (Restricted)' | 'Tier 1 (Basic Verified)' | 'Tier 2 (Enterprise)';

export interface UserProfile {
  id: string;
  fullName: string;
  email: string;
  phone: string;
  accountNumber: string;
  kycStatus: UserKycStatus;
  kycTier: KycTier;
  kycCompletedAt?: string;
  verificationSessionId?: string;
  transferLimitDaily: number;
}

export interface AccountBalance {
  currency: 'USD' | 'EUR' | 'GBP' | 'INR';
  total: number;
  available: number;
  savings: number;
}

export type TransactionType = 'credit' | 'debit';
export type TransactionCategory = 'transfer' | 'shopping' | 'salary' | 'investment' | 'crypto';

export interface Transaction {
  id: string;
  title: string;
  subtitle: string;
  amount: number;
  type: TransactionType;
  category: TransactionCategory;
  date: string;
  status: 'completed' | 'pending' | 'flagged';
  iconName: string;
}

// ---------------------------------------------------------------------------
// Custom SDK Gateway Interfaces & Payloads
// ---------------------------------------------------------------------------

export type SdkEnvironment = 'sandbox' | 'production';

export type KycDocumentType = 'PASSPORT' | 'DRIVING_LICENSE' | 'NATIONAL_ID';

export interface KycSdkConfig {
  apiKey: string;
  environment: SdkEnvironment;
  theme?: {
    primaryColor?: string;
    backgroundColor?: string;
    isDarkMode?: boolean;
  };
  timeoutSeconds?: number;
  metadata?: Record<string, unknown>;
}

export interface KycSessionPayload {
  userId: string;
  fullName: string;
  email: string;
  docType: KycDocumentType;
  sessionReferenceId: string;
  clientNonce: string;
  dob?: string;
  idLast4?: string;
  phone?: string;
}

export type KycVerificationStatus = 'SUCCESS' | 'FAILED' | 'CANCELLED' | 'IN_REVIEW';

export interface KycSdkResult {
  status: KycVerificationStatus;
  verificationId?: string;
  timestamp: number;
  riskScore?: number;
  failureReason?: string;
  rawDetails?: Record<string, unknown>;
}

export type KycSdkEventType = 
  | 'INITIALIZED'
  | 'CAMERA_STARTED'
  | 'DOCUMENT_CAPTURED'
  | 'LIVENESS_CHECK_STARTED'
  | 'BIOMETRICS_VERIFIED'
  | 'DATA_SUBMITTED'
  | 'COMPLETED'
  | 'FAILED'
  | 'USER_CANCELLED';

export interface KycSdkEvent {
  type: KycSdkEventType;
  message: string;
  timestamp: number;
  step?: number;
  totalSteps?: number;
  data?: Record<string, unknown>;
}
