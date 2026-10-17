"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.pollVerificationStatus = pollVerificationStatus;
const errors_1 = require("./errors");
const verdict_1 = require("./verdict");
async function pollVerificationStatus(options) {
    const { backendUrl, verificationId, timeoutMs = 60000, initialIntervalMs = 1500, maxIntervalMs = 5000, maxAttempts = 40, fetchFn = fetch, signal, } = options;
    const url = `${backendUrl.replace(/\/+$/, '')}/kyc/status/${verificationId}`;
    const startTime = Date.now();
    let intervalMs = initialIntervalMs;
    let attempts = 0;
    while (attempts < maxAttempts) {
        if (signal?.aborted) {
            throw new Error('Polling was aborted');
        }
        if (Date.now() - startTime > timeoutMs) {
            throw new errors_1.TimeoutError(`Polling timed out after ${timeoutMs}ms`);
        }
        attempts++;
        try {
            const response = await fetchFn(url, { signal });
            if (response.ok) {
                const data = (await response.json());
                // Checks are done when status is 'completed' or 'reviewed' or decision is populated
                if (data.status === 'completed' || data.status === 'reviewed' || data.decision || data.final_decision) {
                    return (0, verdict_1.mapBackendVerdict)(data);
                }
            }
        }
        catch (err) {
            if (signal?.aborted) {
                throw new Error('Polling was aborted');
            }
            // If network blip on last attempt, surface it
            if (attempts >= maxAttempts) {
                throw new errors_1.NetworkError(`Failed to fetch KYC status: ${err.message}`, err);
            }
        }
        // Wait with exponential backoff capped at maxIntervalMs
        await new Promise((resolve) => setTimeout(resolve, intervalMs));
        intervalMs = Math.min(intervalMs * 1.5, maxIntervalMs);
    }
    throw new errors_1.TimeoutError(`Max polling attempts (${maxAttempts}) reached without a final verdict`);
}
