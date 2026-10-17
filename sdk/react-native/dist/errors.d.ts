export declare class KycError extends Error {
    code: string;
    details?: any;
    constructor(message: string, code?: string, details?: any);
}
export declare class NetworkError extends KycError {
    constructor(message?: string, details?: any);
}
export declare class TimeoutError extends KycError {
    constructor(message?: string, details?: any);
}
export declare class PermissionDeniedError extends KycError {
    constructor(permission: string, details?: any);
}
export declare class CancelledError extends KycError {
    constructor(message?: string, details?: any);
}
