"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.verifyWebhook = verifyWebhook;
const crypto = __importStar(require("crypto"));
const errors_1 = require("./errors");
/**
 * Verify HMAC signature on incoming KYC webhook payloads.
 *
 * Header format: X-KYC-Signature: t=<timestamp>,v1=<hmac_sha256("<timestamp>.<body_bytes>")>
 */
function verifyWebhook(body, signatureHeader, secret, toleranceSeconds = 300, nowTimestamp) {
    if (!signatureHeader) {
        throw new errors_1.WebhookVerificationError('Missing X-KYC-Signature header');
    }
    const parts = signatureHeader.split(',').reduce((acc, pair) => {
        const idx = pair.indexOf('=');
        if (idx !== -1) {
            acc[pair.slice(0, idx).trim()] = pair.slice(idx + 1).trim();
        }
        return acc;
    }, {});
    const tsStr = parts['t'];
    const givenMac = parts['v1'];
    if (!tsStr || !givenMac) {
        throw new errors_1.WebhookVerificationError('Malformed X-KYC-Signature header format');
    }
    const ts = parseInt(tsStr, 10);
    if (isNaN(ts)) {
        throw new errors_1.WebhookVerificationError('Invalid timestamp in signature header');
    }
    const now = nowTimestamp !== undefined ? nowTimestamp : Math.floor(Date.now() / 1000);
    if (Math.abs(now - ts) > toleranceSeconds) {
        throw new errors_1.WebhookVerificationError(`Webhook timestamp outside tolerance window (${Math.abs(now - ts)}s > ${toleranceSeconds}s)`);
    }
    const bodyBuffer = Buffer.isBuffer(body) ? body : Buffer.from(body, 'utf-8');
    const hmac = crypto.createHmac('sha256', secret);
    hmac.update(`${ts}.`);
    hmac.update(bodyBuffer);
    const expectedMac = hmac.digest('hex');
    const expectedBuf = Buffer.from(expectedMac, 'hex');
    const givenBuf = Buffer.from(givenMac, 'hex');
    if (expectedBuf.length !== givenBuf.length || !crypto.timingSafeEqual(expectedBuf, givenBuf)) {
        throw new errors_1.WebhookVerificationError('Webhook signature verification failed');
    }
    try {
        const jsonStr = bodyBuffer.toString('utf-8');
        return JSON.parse(jsonStr);
    }
    catch (err) {
        throw new errors_1.WebhookVerificationError(`Failed to parse webhook JSON body: ${err.message}`);
    }
}
