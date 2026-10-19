import {
  AuthenticationError,
  ConflictError,
  KycError,
  NotFoundError,
  RateLimitError,
} from './errors';
import {
  ClientOptions,
  CreateVerificationParams,
  EvidenceManifest,
  ReviewVerificationParams,
  VerificationResult,
  VerificationSession,
} from './types';
import { verifyWebhook } from './webhook';

export class UncloneKycClient {
  public readonly apiKey: string;
  public readonly baseUrl: string;
  public readonly timeoutMs: number;
  public readonly maxRetries: number;

  constructor(options: ClientOptions) {
    if (!options || !options.apiKey) {
      throw new Error('UncloneKycClient requires an apiKey.');
    }
    this.apiKey = options.apiKey;
    this.baseUrl = (options.baseUrl || 'http://localhost:8000').replace(/\/+$/, '');
    this.timeoutMs = options.timeoutMs ?? 10000;
    this.maxRetries = options.maxRetries ?? 3;
  }

  private async request<T>(
    method: string,
    path: string,
    body?: any,
    headers?: Record<string, string>,
    query?: Record<string, any>
  ): Promise<T> {
    let urlStr = `${this.baseUrl}${path}`;
    if (query) {
      const q = new URLSearchParams();
      for (const [k, v] of Object.entries(query)) {
        if (v !== undefined && v !== null) {
          q.set(k, String(v));
        }
      }
      const qs = q.toString();
      if (qs) {
        urlStr += (urlStr.includes('?') ? '&' : '?') + qs;
      }
    }

    const reqHeaders: Record<string, string> = {
      Authorization: `Bearer ${this.apiKey}`,
      'User-Agent': '@unclone/kyc-node/0.1.0',
      ...(body ? { 'Content-Type': 'application/json' } : {}),
      ...headers,
    };

    let lastError: any = null;

    for (let attempt = 1; attempt <= this.maxRetries; attempt++) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), this.timeoutMs);

      try {
        const response = await fetch(urlStr, {
          method,
          headers: reqHeaders,
          body: body ? JSON.stringify(body) : undefined,
          signal: controller.signal,
        });

        clearTimeout(timer);

        if (response.status === 401) {
          const errData = await response.json().catch(() => ({}));
          throw new AuthenticationError('Invalid or missing API key', errData);
        }
        if (response.status === 404) {
          const errData = await response.json().catch(() => ({}));
          throw new NotFoundError(`Resource not found: ${path}`, errData);
        }
        if (response.status === 409) {
          const text = await response.text();
          throw new ConflictError(`Conflict error: ${text}`, { status: 409, text });
        }
        if (response.status === 429) {
          const errData = await response.json().catch(() => ({}));
          throw new RateLimitError('Rate limit exceeded', errData);
        }
        if (response.status >= 500) {
          if (attempt < this.maxRetries) {
            await new Promise((r) => setTimeout(r, 200 * Math.pow(2, attempt - 1)));
            continue;
          }
          const text = await response.text();
          throw new KycError(`Server error HTTP ${response.status}: ${text}`, response.status);
        }
        if (!response.ok) {
          const text = await response.text();
          throw new KycError(`API request failed HTTP ${response.status}: ${text}`, response.status);
        }

        if (response.status === 204) {
          return true as unknown as T;
        }

        return (await response.json()) as T;
      } catch (err: any) {
        clearTimeout(timer);
        if (err instanceof KycError) {
          throw err;
        }
        lastError = err;
        if (attempt < this.maxRetries) {
          await new Promise((r) => setTimeout(r, 200 * Math.pow(2, attempt - 1)));
          continue;
        }
      }
    }

    throw new KycError(`Network error after ${this.maxRetries} attempts: ${lastError?.message || lastError}`);
  }

  /**
   * Create a new KYC verification session.
   */
  public async createVerification(params: CreateVerificationParams): Promise<VerificationSession> {
    const headers: Record<string, string> = {};
    if (params.idempotencyKey) {
      headers['Idempotency-Key'] = params.idempotencyKey;
    }

    const payload: Record<string, any> = {
      reference_id: params.referenceId,
      expected: params.expected || {},
    };
    if (params.policy) {
      payload.policy = params.policy;
    }

    return this.request<VerificationSession>('POST', '/v1/verifications', payload, headers);
  }

  /**
   * Get the verification status and decision results.
   */
  public async getVerification(verificationId: string): Promise<VerificationResult> {
    return this.request<VerificationResult>('GET', `/v1/verifications/${verificationId}`);
  }

  /**
   * List recent verifications.
   */
  public async listVerifications(params?: { limit?: number }): Promise<VerificationResult[]> {
    const res = await this.request<{ data: VerificationResult[] }>('GET', '/v1/verifications', undefined, undefined, {
      limit: params?.limit ?? 50,
    });
    return res.data;
  }

  /**
   * Delete a verification and purge all associated evidence.
   */
  public async deleteVerification(verificationId: string): Promise<boolean> {
    await this.request<boolean>('DELETE', `/v1/verifications/${verificationId}`);
    return true;
  }

  /**
   * Submit a human review override ('approved' or 'rejected').
   */
  public async reviewVerification(
    verificationId: string,
    params: ReviewVerificationParams
  ): Promise<VerificationResult> {
    return this.request<VerificationResult>('POST', `/v1/verifications/${verificationId}/review`, params);
  }

  /**
   * Fetch signed expiring evidence URLs for this verification.
   */
  public async getEvidence(verificationId: string): Promise<EvidenceManifest> {
    return this.request<EvidenceManifest>('GET', `/v1/verifications/${verificationId}/evidence`);
  }

  /**
   * Static helper to verify webhook signatures.
   */
  public static verifyWebhook = verifyWebhook;
}
