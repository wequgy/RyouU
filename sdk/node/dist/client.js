"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.UncloneKycClient = void 0;
const errors_1 = require("./errors");
const webhook_1 = require("./webhook");
class UncloneKycClient {
    apiKey;
    baseUrl;
    timeoutMs;
    maxRetries;
    constructor(options) {
        if (!options || !options.apiKey) {
            throw new Error('UncloneKycClient requires an apiKey.');
        }
        this.apiKey = options.apiKey;
        this.baseUrl = (options.baseUrl || 'http://localhost:8000').replace(/\/+$/, '');
        this.timeoutMs = options.timeoutMs ?? 10000;
        this.maxRetries = options.maxRetries ?? 3;
    }
    async request(method, path, body, headers, query) {
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
        const reqHeaders = {
            Authorization: `Bearer ${this.apiKey}`,
            'User-Agent': '@unclone/kyc-node/0.1.0',
            ...(body ? { 'Content-Type': 'application/json' } : {}),
            ...headers,
        };
        let lastError = null;
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
                    throw new errors_1.AuthenticationError('Invalid or missing API key', errData);
                }
                if (response.status === 404) {
                    const errData = await response.json().catch(() => ({}));
                    throw new errors_1.NotFoundError(`Resource not found: ${path}`, errData);
                }
                if (response.status === 409) {
                    const text = await response.text();
                    throw new errors_1.ConflictError(`Conflict error: ${text}`, { status: 409, text });
                }
                if (response.status === 429) {
                    const errData = await response.json().catch(() => ({}));
                    throw new errors_1.RateLimitError('Rate limit exceeded', errData);
                }
                if (response.status >= 500) {
                    if (attempt < this.maxRetries) {
                        await new Promise((r) => setTimeout(r, 200 * Math.pow(2, attempt - 1)));
                        continue;
                    }
                    const text = await response.text();
                    throw new errors_1.KycError(`Server error HTTP ${response.status}: ${text}`, response.status);
                }
                if (!response.ok) {
                    const text = await response.text();
                    throw new errors_1.KycError(`API request failed HTTP ${response.status}: ${text}`, response.status);
                }
                if (response.status === 204) {
                    return true;
                }
                return (await response.json());
            }
            catch (err) {
                clearTimeout(timer);
                if (err instanceof errors_1.KycError) {
                    throw err;
                }
                lastError = err;
                if (attempt < this.maxRetries) {
                    await new Promise((r) => setTimeout(r, 200 * Math.pow(2, attempt - 1)));
                    continue;
                }
            }
        }
        throw new errors_1.KycError(`Network error after ${this.maxRetries} attempts: ${lastError?.message || lastError}`);
    }
    /**
     * Create a new KYC verification session.
     */
    async createVerification(params) {
        const headers = {};
        if (params.idempotencyKey) {
            headers['Idempotency-Key'] = params.idempotencyKey;
        }
        const payload = {
            reference_id: params.referenceId,
            expected: params.expected || {},
        };
        if (params.policy) {
            payload.policy = params.policy;
        }
        return this.request('POST', '/v1/verifications', payload, headers);
    }
    /**
     * Get the verification status and decision results.
     */
    async getVerification(verificationId) {
        return this.request('GET', `/v1/verifications/${verificationId}`);
    }
    /**
     * List recent verifications.
     */
    async listVerifications(params) {
        const res = await this.request('GET', '/v1/verifications', undefined, undefined, {
            limit: params?.limit ?? 50,
        });
        return res.data;
    }
    /**
     * Delete a verification and purge all associated evidence.
     */
    async deleteVerification(verificationId) {
        await this.request('DELETE', `/v1/verifications/${verificationId}`);
        return true;
    }
    /**
     * Submit a human review override ('approved' or 'rejected').
     */
    async reviewVerification(verificationId, params) {
        return this.request('POST', `/v1/verifications/${verificationId}/review`, params);
    }
    /**
     * Fetch signed expiring evidence URLs for this verification.
     */
    async getEvidence(verificationId) {
        return this.request('GET', `/v1/verifications/${verificationId}/evidence`);
    }
    /**
     * Static helper to verify webhook signatures.
     */
    static verifyWebhook = webhook_1.verifyWebhook;
}
exports.UncloneKycClient = UncloneKycClient;
