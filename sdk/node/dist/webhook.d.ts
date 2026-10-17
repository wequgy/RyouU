import { WebhookEvent } from './types';
/**
 * Verify HMAC signature on incoming KYC webhook payloads.
 *
 * Header format: X-KYC-Signature: t=<timestamp>,v1=<hmac_sha256("<timestamp>.<body_bytes>")>
 */
export declare function verifyWebhook<T = any>(body: string | Buffer, signatureHeader: string, secret: string, toleranceSeconds?: number, nowTimestamp?: number): WebhookEvent<T>;
