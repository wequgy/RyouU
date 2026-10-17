"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.WebhookVerificationError = exports.RateLimitError = exports.ConflictError = exports.NotFoundError = exports.AuthenticationError = exports.KycError = void 0;
class KycError extends Error {
    statusCode;
    details;
    constructor(message, statusCode, details) {
        super(message);
        this.name = 'KycError';
        this.statusCode = statusCode;
        this.details = details;
        Object.setPrototypeOf(this, new.target.prototype);
    }
}
exports.KycError = KycError;
class AuthenticationError extends KycError {
    constructor(message = 'Invalid or missing API key', details) {
        super(message, 401, details);
        this.name = 'AuthenticationError';
    }
}
exports.AuthenticationError = AuthenticationError;
class NotFoundError extends KycError {
    constructor(message = 'Resource not found', details) {
        super(message, 404, details);
        this.name = 'NotFoundError';
    }
}
exports.NotFoundError = NotFoundError;
class ConflictError extends KycError {
    constructor(message = 'Conflict with current resource state', details) {
        super(message, 409, details);
        this.name = 'ConflictError';
    }
}
exports.ConflictError = ConflictError;
class RateLimitError extends KycError {
    constructor(message = 'Rate limit exceeded', details) {
        super(message, 429, details);
        this.name = 'RateLimitError';
    }
}
exports.RateLimitError = RateLimitError;
class WebhookVerificationError extends KycError {
    constructor(message = 'Webhook verification failed', details) {
        super(message, undefined, details);
        this.name = 'WebhookVerificationError';
    }
}
exports.WebhookVerificationError = WebhookVerificationError;
