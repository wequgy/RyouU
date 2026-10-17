export type CheckStatus = 'pass' | 'fail' | 'uncertain' | 'skipped';

export type VerificationDecision = 'approved' | 'needs_review' | 'rejected_recommended';

export type FinalDecision = 'approved' | 'rejected' | 'needs_review' | 'rejected_recommended';

export interface CheckItemResult {
  name: string;
  status: CheckStatus;
  score: number;
  confidence: number;
  reason: string;
  details?: Record<string, any>;
}

export interface VerificationSession {
  id: string;
  status: string;
  policy: string;
  expires_at: number;
  flow_url: string;
}

export interface VerificationReview {
  decision: 'approved' | 'rejected';
  note?: string;
  at: number;
}

export interface VerificationResult {
  id: string;
  reference_id: string;
  status: string;
  policy: string;
  decision: VerificationDecision | null;
  final_decision: FinalDecision | null;
  trust: number | null;
  reasons: string[];
  results: CheckItemResult[];
  review?: VerificationReview | null;
  webhook?: Record<string, any> | null;
  created_at: number;
  updated_at: number;
}

export interface CreateVerificationParams {
  referenceId: string;
  expected?: {
    name?: string;
    dob?: string;
    idLast4?: string;
    email?: string;
    phone?: string;
    [key: string]: any;
  };
  policy?: 'strict' | 'lenient' | string;
  idempotencyKey?: string;
}

export interface ReviewVerificationParams {
  decision: 'approved' | 'rejected';
  note?: string;
}

export interface WebhookEvent<T = any> {
  id: string;
  type: string;
  created: number;
  data: T;
}

export interface EvidenceItem {
  kind: string;
  url: string;
  expires_in_s: number;
}

export interface EvidenceManifest {
  verification_id: string;
  evidence: Record<string, EvidenceItem>;
}

export interface ClientOptions {
  apiKey: string;
  baseUrl?: string;
  timeoutMs?: number;
  maxRetries?: number;
}
