import { BackendStatusResponse, KycResult } from './types';
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
export declare function mapBackendVerdict(resp: BackendStatusResponse): KycResult;
