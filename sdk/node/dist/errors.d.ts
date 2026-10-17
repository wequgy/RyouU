export declare class KycError extends Error {
    statusCode?: number;
    details?: any;
    constructor(message: string, statusCode?: number, details?: any);
}
export declare class AuthenticationError extends KycError {
    constructor(message?: string, details?: any);
}
export declare class NotFoundError extends KycError {
    constructor(message?: string, details?: any);
}
export declare class ConflictError extends KycError {
    constructor(message?: string, details?: any);
}
export declare class RateLimitError extends KycError {
    constructor(message?: string, details?: any);
}
export declare class WebhookVerificationError extends KycError {
    constructor(message?: string, details?: any);
}
