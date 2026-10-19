import * as crypto from 'crypto';
import { WebhookVerificationError } from './errors';
import { WebhookEvent } from './types';

/**
 * Verify HMAC signature on incoming KYC webhook payloads.
 *
 * Header format: X-KYC-Signature: t=<timestamp>,v1=<hmac_sha256("<timestamp>.<body_bytes>")>
 */
export function verifyWebhook<T = any>(
  body: string | Buffer,
  signatureHeader: string,
  secret: string,
  toleranceSeconds = 300,
  nowTimestamp?: number
): WebhookEvent<T> {
  if (!signatureHeader) {
    throw new WebhookVerificationError('Missing X-KYC-Signature header');
  }

  const parts = signatureHeader.split(',').reduce<Record<string, string>>((acc, pair) => {
    const idx = pair.indexOf('=');
    if (idx !== -1) {
      acc[pair.slice(0, idx).trim()] = pair.slice(idx + 1).trim();
    }
    return acc;
  }, {});

  const tsStr = parts['t'];
  const givenMac = parts['v1'];

  if (!tsStr || !givenMac) {
    throw new WebhookVerificationError('Malformed X-KYC-Signature header format');
  }

  const ts = parseInt(tsStr, 10);
  if (isNaN(ts)) {
    throw new WebhookVerificationError('Invalid timestamp in signature header');
  }

  const now = nowTimestamp !== undefined ? nowTimestamp : Math.floor(Date.now() / 1000);
  if (Math.abs(now - ts) > toleranceSeconds) {
    throw new WebhookVerificationError(
      `Webhook timestamp outside tolerance window (${Math.abs(now - ts)}s > ${toleranceSeconds}s)`
    );
  }

  const bodyBuffer = Buffer.isBuffer(body) ? body : Buffer.from(body, 'utf-8');
  const hmac = crypto.createHmac('sha256', secret);
  hmac.update(`${ts}.`);
  hmac.update(bodyBuffer);
  const expectedMac = hmac.digest('hex');

  const expectedBuf = Buffer.from(expectedMac, 'hex');
  const givenBuf = Buffer.from(givenMac, 'hex');

  if (expectedBuf.length !== givenBuf.length || !crypto.timingSafeEqual(expectedBuf, givenBuf)) {
    throw new WebhookVerificationError('Webhook signature verification failed');
  }

  try {
    const jsonStr = bodyBuffer.toString('utf-8');
    return JSON.parse(jsonStr) as WebhookEvent<T>;
  } catch (err: any) {
    throw new WebhookVerificationError(`Failed to parse webhook JSON body: ${err.message}`);
  }
}
