"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.UncloneKyc = void 0;
const errors_1 = require("./errors");
const polling_1 = require("./polling");
// Optional dynamic import for Screen Capture security
let ScreenCapture = null;
try {
    ScreenCapture = require('expo-screen-capture');
}
catch {
    // Not installed or non-expo
}
class UncloneKyc {
    constructor(config) {
        this.listeners = new Map();
        this.abortController = null;
        this.activeVerificationId = null;
        if (!config || !config.backendUrl) {
            throw new Error('UncloneKyc requires a backendUrl (your server endpoint, e.g. https://api.yourfintech.com)');
        }
        this.config = {
            timeoutMs: 90000,
            pollingIntervalMs: 1500,
            maxPollingAttempts: 45,
            ...config,
            backendUrl: config.backendUrl.replace(/\/+$/, ''),
        };
    }
    /**
     * Register an event listener.
     * e.g. kyc.on('event', fn) or kyc.on('flow_opened', fn)
     */
    on(event, listener) {
        if (!this.listeners.has(event)) {
            this.listeners.set(event, new Set());
        }
        this.listeners.get(event).add(listener);
        return () => {
            this.listeners.get(event)?.delete(listener);
        };
    }
    emit(type, data) {
        const event = {
            type,
            verificationId: this.activeVerificationId || undefined,
            data,
            timestamp: Date.now(),
        };
        this.listeners.get(type)?.forEach((fn) => {
            try {
                fn(event);
            }
            catch (err) {
                console.error('Error in KYC event listener:', err);
            }
        });
        this.listeners.get('event')?.forEach((fn) => {
            try {
                fn(event);
            }
            catch (err) {
                console.error('Error in KYC event listener:', err);
            }
        });
    }
    /**
     * Request native Camera and Audio permissions at runtime on Android.
     */
    async requestPermissions() {
        try {
            const { Platform, PermissionsAndroid } = require('react-native');
            if (Platform.OS === 'android') {
                const cameraGranted = await PermissionsAndroid.request(PermissionsAndroid.PERMISSIONS.CAMERA, {
                    title: 'Camera Permission',
                    message: 'RyouU KYC requires access to your camera to verify your identity document and selfie.',
                    buttonPositive: 'Allow',
                });
                if (cameraGranted !== PermissionsAndroid.RESULTS.GRANTED) {
                    throw new errors_1.PermissionDeniedError('CAMERA');
                }
                const audioGranted = await PermissionsAndroid.request(PermissionsAndroid.PERMISSIONS.RECORD_AUDIO, {
                    title: 'Microphone Permission',
                    message: 'RyouU KYC requires microphone access for audio challenges and spoken verification.',
                    buttonPositive: 'Allow',
                });
                if (audioGranted !== PermissionsAndroid.RESULTS.GRANTED) {
                    throw new errors_1.PermissionDeniedError('RECORD_AUDIO');
                }
            }
            return true;
        }
        catch (err) {
            if (err instanceof errors_1.PermissionDeniedError)
                throw err;
            return true; // Web / iOS uses browser or Info.plist prompts
        }
    }
    /**
     * Enable anti-screencast / FLAG_SECURE layer while KYC is active.
     */
    async enableSecurityShield() {
        try {
            if (ScreenCapture?.preventScreenCaptureAsync) {
                await ScreenCapture.preventScreenCaptureAsync();
            }
        }
        catch {
            // Ignore if unavailable
        }
    }
    /**
     * Restore screen capture when KYC completes or cancels.
     */
    async disableSecurityShield() {
        try {
            if (ScreenCapture?.allowScreenCaptureAsync) {
                await ScreenCapture.allowScreenCaptureAsync();
            }
        }
        catch {
            // Ignore if unavailable
        }
    }
    /**
     * Create a verification session by calling customer backend POST /kyc/session.
     */
    async createSession(params) {
        const url = `${this.config.backendUrl}/kyc/session`;
        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    Accept: 'application/json',
                },
                body: JSON.stringify(params),
                signal: this.abortController?.signal,
            });
            if (!response.ok) {
                const text = await response.text();
                throw new errors_1.NetworkError(`Customer backend returned HTTP ${response.status}: ${text}`);
            }
            const data = await response.json();
            const id = data.id || data.verificationId;
            const flowUrl = data.flow_url || data.flowUrl;
            if (!id || !flowUrl) {
                throw new errors_1.NetworkError('Backend did not return valid session id and flow_url');
            }
            return { id, flowUrl };
        }
        catch (err) {
            if (err.name === 'AbortError') {
                throw new errors_1.CancelledError();
            }
            if (err instanceof errors_1.NetworkError)
                throw err;
            throw new errors_1.NetworkError(`Failed to connect to customer backend: ${err.message}`, err);
        }
    }
    /**
     * Start a complete KYC verification flow.
     */
    async start(params) {
        this.abortController = new AbortController();
        this.emit('started', params);
        await this.enableSecurityShield();
        try {
            await this.requestPermissions();
            const session = await this.createSession(params);
            this.activeVerificationId = session.id;
            this.emit('flow_opened', { flowUrl: session.flowUrl });
            // Poll backend for final verdict
            const result = await (0, polling_1.pollVerificationStatus)({
                backendUrl: this.config.backendUrl,
                verificationId: session.id,
                timeoutMs: this.config.timeoutMs,
                initialIntervalMs: this.config.pollingIntervalMs,
                signal: this.abortController.signal,
            });
            this.emit('completed', result);
            return result;
        }
        catch (err) {
            if (err instanceof errors_1.CancelledError || err.name === 'AbortError') {
                this.emit('cancelled');
                return {
                    status: 'CANCELLED',
                    verificationId: this.activeVerificationId || '',
                    reasons: ['User cancelled verification'],
                };
            }
            this.emit('error', { message: err.message });
            throw err;
        }
        finally {
            await this.disableSecurityShield();
            this.abortController = null;
        }
    }
    /**
     * Cancel the currently active KYC verification.
     */
    cancel() {
        if (this.abortController) {
            this.abortController.abort();
        }
        this.disableSecurityShield();
        this.emit('cancelled');
    }
}
exports.UncloneKyc = UncloneKyc;
