export class KycError extends Error {
  public code: string;
  public details?: any;

  constructor(message: string, code = 'KYC_ERROR', details?: any) {
    super(message);
    this.name = 'KycError';
    this.code = code;
    this.details = details;
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

export class NetworkError extends KycError {
  constructor(message = 'Network connection failed during KYC verification', details?: any) {
    super(message, 'NETWORK_ERROR', details);
    this.name = 'NetworkError';
  }
}

export class TimeoutError extends KycError {
  constructor(message = 'KYC verification polling timed out before a final decision was reached', details?: any) {
    super(message, 'TIMEOUT_ERROR', details);
    this.name = 'TimeoutError';
  }
}

export class PermissionDeniedError extends KycError {
  constructor(permission: string, details?: any) {
    super(`Required permission was denied: ${permission}`, 'PERMISSION_DENIED', details);
    this.name = 'PermissionDeniedError';
  }
}

export class CancelledError extends KycError {
  constructor(message = 'KYC verification was cancelled by user', details?: any) {
    super(message, 'CANCELLED', details);
    this.name = 'CancelledError';
  }
}
