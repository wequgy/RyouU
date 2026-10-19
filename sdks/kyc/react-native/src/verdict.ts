import { BackendStatusResponse, KycResult, KycStatus } from './types';

/**
 * Maps the backend verification decision to the SDK's public KycStatus.
 *
 * Rules:
 * - The VERDICT is `decision` / `final_decision`, NEVER `status`.
 * - `status="completed"` only means checks have finished evaluating; it is NOT success.
 * - Only `approved` is success ('SUCCESS').
 * - `needs_review` and `rejected_recommended` map to 'IN_REVIEW'.
 * - `rejected` (human review decision) maps to 'FAILED'.
 * - If cancelled or missing verdict when closed -> 'CANCELLED'.
 */
export function mapBackendVerdict(resp: BackendStatusResponse): KycResult {
  const verdict = resp.final_decision || resp.decision;
  let status: KycStatus;

  switch (verdict) {
    case 'approved':
      status = 'SUCCESS';
      break;
    case 'needs_review':
    case 'rejected_recommended':
      status = 'IN_REVIEW';
      break;
    case 'rejected':
      status = 'FAILED';
      break;
    default:
      // If checks completed without a decision or inconclusive
      status = 'IN_REVIEW';
      break;
  }

  // Calculate risk score: trust is 1.0 = genuine, so riskScore = 1.0 - trust
  const riskScore = resp.trust !== undefined && resp.trust !== null ? Math.round((1 - resp.trust) * 100) / 100 : null;

  return {
    status,
    verificationId: resp.id,
    riskScore,
    reasons: resp.reasons || [],
    rawDecision: resp.decision || null,
    rawFinalDecision: resp.final_decision || null,
  };
}
