"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.UncloneKycModal = void 0;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const react_native_1 = require("react-native");
const react_native_webview_1 = require("react-native-webview");
const polling_1 = require("./polling");
const UncloneKyc_1 = require("./UncloneKyc");
const UncloneKycModal = ({ visible, config, params, onComplete, onCancel, onError, }) => {
    const [flowUrl, setFlowUrl] = (0, react_1.useState)(null);
    const [verificationId, setVerificationId] = (0, react_1.useState)(null);
    const [loading, setLoading] = (0, react_1.useState)(true);
    const [submitting, setSubmitting] = (0, react_1.useState)(false);
    const kycRef = (0, react_1.useRef)(null);
    (0, react_1.useEffect)(() => {
        if (!visible) {
            setFlowUrl(null);
            setVerificationId(null);
            setLoading(true);
            setSubmitting(false);
            return;
        }
        const kyc = new UncloneKyc_1.UncloneKyc(config);
        kycRef.current = kyc;
        let isMounted = true;
        async function init() {
            try {
                await kyc.requestPermissions();
                const session = await kyc.createSession(params);
                if (isMounted) {
                    setVerificationId(session.id);
                    setFlowUrl(session.flowUrl);
                    setLoading(false);
                }
            }
            catch (err) {
                if (isMounted) {
                    onError?.(err);
                    onCancel();
                }
            }
        }
        init();
        return () => {
            isMounted = false;
            kyc.cancel();
        };
    }, [visible, config.backendUrl, params.referenceId]);
    const handleMessage = async (event) => {
        try {
            const msg = JSON.parse(event.nativeEvent.data);
            // When page reports completion/submission, NEVER trust verdict from WebView.
            // ALWAYS poll the customer backend to fetch the authentic server verdict.
            if (msg.type === 'kyc_submitted' || msg.type === 'kyc_completed' || msg.status === 'processing') {
                if (!verificationId)
                    return;
                setSubmitting(true);
                const result = await (0, polling_1.pollVerificationStatus)({
                    backendUrl: config.backendUrl,
                    verificationId,
                    timeoutMs: config.timeoutMs,
                });
                setSubmitting(false);
                onComplete(result);
            }
        }
        catch {
            // Non-JSON message, ignore
        }
    };
    const handleClose = async () => {
        // If verification was initiated, check if there was a verdict reached
        if (verificationId) {
            try {
                const result = await (0, polling_1.pollVerificationStatus)({
                    backendUrl: config.backendUrl,
                    verificationId,
                    timeoutMs: 3000,
                    maxAttempts: 2,
                });
                if (result.status !== 'IN_REVIEW' || result.rawDecision) {
                    onComplete(result);
                    return;
                }
            }
            catch {
                // Fallback to cancelled
            }
        }
        onCancel();
    };
    return ((0, jsx_runtime_1.jsx)(react_native_1.Modal, { visible: visible, animationType: "slide", onRequestClose: handleClose, children: (0, jsx_runtime_1.jsxs)(react_native_1.SafeAreaView, { style: styles.container, children: [(0, jsx_runtime_1.jsxs)(react_native_1.View, { style: styles.header, children: [(0, jsx_runtime_1.jsx)(react_native_1.Text, { style: styles.headerTitle, children: "Identity Verification" }), (0, jsx_runtime_1.jsx)(react_native_1.TouchableOpacity, { onPress: handleClose, style: styles.closeBtn, children: (0, jsx_runtime_1.jsx)(react_native_1.Text, { style: styles.closeText, children: "\u2715" }) })] }), loading ? ((0, jsx_runtime_1.jsxs)(react_native_1.View, { style: styles.center, children: [(0, jsx_runtime_1.jsx)(react_native_1.ActivityIndicator, { size: "large", color: "#4F46E5" }), (0, jsx_runtime_1.jsx)(react_native_1.Text, { style: styles.loadingText, children: "Initializing secure KYC session..." })] })) : submitting ? ((0, jsx_runtime_1.jsxs)(react_native_1.View, { style: styles.center, children: [(0, jsx_runtime_1.jsx)(react_native_1.ActivityIndicator, { size: "large", color: "#10B981" }), (0, jsx_runtime_1.jsx)(react_native_1.Text, { style: styles.loadingText, children: "Verifying credentials with server..." })] })) : flowUrl ? ((0, jsx_runtime_1.jsx)(react_native_webview_1.WebView, { source: { uri: flowUrl }, onMessage: handleMessage, allowsInlineMediaPlayback: true, mediaPlaybackRequiresUserAction: false, javaScriptEnabled: true, domStorageEnabled: true, style: styles.webview })) : null] }) }));
};
exports.UncloneKycModal = UncloneKycModal;
const styles = react_native_1.StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: '#FFFFFF',
    },
    header: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        paddingHorizontal: 16,
        paddingVertical: 12,
        borderBottomWidth: react_native_1.StyleSheet.hairlineWidth,
        borderBottomColor: '#E5E7EB',
    },
    headerTitle: {
        fontSize: 16,
        fontWeight: '600',
        color: '#111827',
    },
    closeBtn: {
        padding: 6,
    },
    closeText: {
        fontSize: 18,
        color: '#6B7280',
    },
    center: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
        padding: 24,
    },
    loadingText: {
        marginTop: 16,
        fontSize: 14,
        color: '#4B5563',
    },
    webview: {
        flex: 1,
    },
});
