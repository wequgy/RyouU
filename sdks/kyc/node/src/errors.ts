export class KycError extends Error {
  public statusCode?: number;
  public details?: any;

  constructor(message: string, statusCode?: number, details?: any) {
    super(message);
    this.name = 'KycError';
    this.statusCode = statusCode;
    this.details = details;
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

export class AuthenticationError extends KycError {
  constructor(message = 'Invalid or missing API key', details?: any) {
    super(message, 401, details);
    this.name = 'AuthenticationError';
  }
}

export class NotFoundError extends KycError {
  constructor(message = 'Resource not found', details?: any) {
    super(message, 404, details);
    this.name = 'NotFoundError';
  }
}

export class ConflictError extends KycError {
  constructor(message = 'Conflict with current resource state', details?: any) {
    super(message, 409, details);
    this.name = 'ConflictError';
  }
}

export class RateLimitError extends KycError {
  constructor(message = 'Rate limit exceeded', details?: any) {
    super(message, 429, details);
    this.name = 'RateLimitError';
  }
}

export class WebhookVerificationError extends KycError {
  constructor(message = 'Webhook verification failed', details?: any) {
    super(message, undefined, details);
    this.name = 'WebhookVerificationError';
  }
}
