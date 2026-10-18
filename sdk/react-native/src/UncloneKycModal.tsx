import React, { useEffect, useState, useRef } from 'react';
import {
  ActivityIndicator,
  Modal,
  SafeAreaView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { WebView } from 'react-native-webview';

import { pollVerificationStatus } from './polling';
import { KycResult, KycStartParams, UncloneKycConfig } from './types';
import { UncloneKyc } from './UncloneKyc';

export interface UncloneKycModalProps {
  visible: boolean;
  config: UncloneKycConfig;
  params: KycStartParams;
  onComplete: (result: KycResult) => void;
  onCancel: () => void;
  onError?: (error: Error) => void;
}

export const UncloneKycModal: React.FC<UncloneKycModalProps> = ({
  visible,
  config,
  params,
  onComplete,
  onCancel,
  onError,
}) => {
  const [flowUrl, setFlowUrl] = useState<string | null>(null);
  const [verificationId, setVerificationId] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const kycRef = useRef<UncloneKyc | null>(null);

  useEffect(() => {
    if (!visible) {
      setFlowUrl(null);
      setVerificationId(null);
      setLoading(true);
      setSubmitting(false);
      return;
    }

    const kyc = new UncloneKyc(config);
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
      } catch (err: any) {
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

  const handleMessage = async (event: any) => {
    try {
      const msg = JSON.parse(event.nativeEvent.data);
      // When page reports completion/submission, NEVER trust verdict from WebView.
      // ALWAYS poll the customer backend to fetch the authentic server verdict.
      if (msg.type === 'kyc.done' || msg.type === 'kyc_complete' || msg.type === 'kyc_submitted' || msg.type === 'kyc_completed' || msg.status === 'processing') {
        if (!verificationId) return;
        setSubmitting(true);
        const result = await pollVerificationStatus({
          backendUrl: config.backendUrl,
          verificationId,
          timeoutMs: config.timeoutMs,
        });
        setSubmitting(false);
        onComplete(result);
      }
    } catch {
      // Non-JSON message, ignore
    }
  };

  const handleClose = async () => {
    // If verification was initiated, check if there was a verdict reached
    if (verificationId) {
      try {
        const result = await pollVerificationStatus({
          backendUrl: config.backendUrl,
          verificationId,
          timeoutMs: 3000,
          maxAttempts: 2,
        });
        if (result.status !== 'IN_REVIEW' || result.rawDecision) {
          onComplete(result);
          return;
        }
      } catch {
        // Fallback to cancelled
      }
    }
    onCancel();
  };

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={handleClose}>
      <SafeAreaView style={styles.container}>
        <View style={styles.header}>
          <TouchableOpacity onPress={handleClose} style={styles.closeBtn} activeOpacity={0.7}>
            <Text style={styles.closeText}>✕</Text>
          </TouchableOpacity>
          <View style={styles.headerTitleWrap}>
            <Text style={styles.headerTitle}>Identity Verification</Text>
            <View style={styles.secureBadge}>
              <View style={styles.secureDot} />
              <Text style={styles.secureText}>256-Bit Encrypted</Text>
            </View>
          </View>
          <View style={styles.helpPlaceholder} />
        </View>

        {loading ? (
          <View style={styles.center}>
            <ActivityIndicator size="large" color="#65A30D" />
            <Text style={styles.loadingTitle}>Connecting to secure enclave</Text>
            <Text style={styles.loadingText}>Initializing biometric verification session…</Text>
          </View>
        ) : submitting ? (
          <View style={styles.center}>
            <ActivityIndicator size="large" color="#65A30D" />
            <Text style={styles.loadingTitle}>Evaluating credentials</Text>
            <Text style={styles.loadingText}>Verifying session with secure server…</Text>
          </View>
        ) : flowUrl ? (
          <WebView
            source={{ uri: flowUrl }}
            onMessage={handleMessage}
            allowsInlineMediaPlayback
            mediaPlaybackRequiresUserAction={false}
            javaScriptEnabled
            domStorageEnabled
            style={styles.webview}
          />
        ) : null}
      </SafeAreaView>
    </Modal>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F8FAFC',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#E2E8F0',
  },
  headerTitleWrap: {
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#0F172A',
    letterSpacing: -0.2,
  },
  secureBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginTop: 2,
  },
  secureDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: '#65A30D',
  },
  secureText: {
    fontSize: 10,
    fontWeight: '600',
    color: '#64748B',
    textTransform: 'uppercase',
    letterSpacing: 0.3,
  },
  closeBtn: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: '#F1F5F9',
    alignItems: 'center',
    justifyContent: 'center',
  },
  closeText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#0F172A',
  },
  helpPlaceholder: {
    width: 34,
  },
  center: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 28,
    backgroundColor: '#F8FAFC',
  },
  loadingTitle: {
    marginTop: 18,
    fontSize: 16,
    fontWeight: '700',
    color: '#0F172A',
  },
  loadingText: {
    marginTop: 6,
    fontSize: 13,
    color: '#64748B',
    textAlign: 'center',
  },
  webview: {
    flex: 1,
    backgroundColor: '#F8FAFC',
  },
});

