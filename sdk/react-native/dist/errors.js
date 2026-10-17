"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.CancelledError = exports.PermissionDeniedError = exports.TimeoutError = exports.NetworkError = exports.KycError = void 0;
class KycError extends Error {
    constructor(message, code = 'KYC_ERROR', details) {
        super(message);
        this.name = 'KycError';
        this.code = code;
        this.details = details;
        Object.setPrototypeOf(this, new.target.prototype);
    }
}
exports.KycError = KycError;
class NetworkError extends KycError {
    constructor(message = 'Network connection failed during KYC verification', details) {
        super(message, 'NETWORK_ERROR', details);
        this.name = 'NetworkError';
    }
}
exports.NetworkError = NetworkError;
class TimeoutError extends KycError {
    constructor(message = 'KYC verification polling timed out before a final decision was reached', details) {
        super(message, 'TIMEOUT_ERROR', details);
        this.name = 'TimeoutError';
    }
}
exports.TimeoutError = TimeoutError;
class PermissionDeniedError extends KycError {
    constructor(permission, details) {
        super(`Required permission was denied: ${permission}`, 'PERMISSION_DENIED', details);
        this.name = 'PermissionDeniedError';
    }
}
exports.PermissionDeniedError = PermissionDeniedError;
class CancelledError extends KycError {
    constructor(message = 'KYC verification was cancelled by user', details) {
        super(message, 'CANCELLED', details);
        this.name = 'CancelledError';
    }
}
exports.CancelledError = CancelledError;
