import { NetworkError, TimeoutError } from './errors';
import { BackendStatusResponse, KycResult } from './types';
import { mapBackendVerdict } from './verdict';

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

export async function pollVerificationStatus(options: PollingOptions): Promise<KycResult> {
  const {
    backendUrl,
    verificationId,
    timeoutMs = 60000,
    initialIntervalMs = 1500,
    maxIntervalMs = 5000,
    maxAttempts = 40,
    fetchFn = fetch,
    signal,
  } = options;

  const url = `${backendUrl.replace(/\/+$/, '')}/kyc/status/${verificationId}`;
  const startTime = Date.now();
  let intervalMs = initialIntervalMs;
  let attempts = 0;

  while (attempts < maxAttempts) {
    if (signal?.aborted) {
      throw new Error('Polling was aborted');
    }

    if (Date.now() - startTime > timeoutMs) {
      throw new TimeoutError(`Polling timed out after ${timeoutMs}ms`);
    }

    attempts++;

    try {
      const response = await fetchFn(url, { signal });
      if (response.ok) {
        const data = (await response.json()) as BackendStatusResponse;
        // Checks are done when status is 'completed' or 'reviewed' or decision is populated
        if (data.status === 'completed' || data.status === 'reviewed' || data.decision || data.final_decision) {
          return mapBackendVerdict(data);
        }
      }
    } catch (err: any) {
      if (signal?.aborted) {
        throw new Error('Polling was aborted');
      }
      // If network blip on last attempt, surface it
      if (attempts >= maxAttempts) {
        throw new NetworkError(`Failed to fetch KYC status: ${err.message}`, err);
      }
    }

    // Wait with exponential backoff capped at maxIntervalMs
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
    intervalMs = Math.min(intervalMs * 1.5, maxIntervalMs);
  }

  throw new TimeoutError(`Max polling attempts (${maxAttempts}) reached without a final verdict`);
}
