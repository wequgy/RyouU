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
          <Text style={styles.headerTitle}>Identity Verification</Text>
          <TouchableOpacity onPress={handleClose} style={styles.closeBtn}>
            <Text style={styles.closeText}>✕</Text>
          </TouchableOpacity>
        </View>

        {loading ? (
          <View style={styles.center}>
            <ActivityIndicator size="large" color="#4F46E5" />
            <Text style={styles.loadingText}>Initializing secure KYC session...</Text>
          </View>
        ) : submitting ? (
          <View style={styles.center}>
            <ActivityIndicator size="large" color="#10B981" />
            <Text style={styles.loadingText}>Verifying credentials with server...</Text>
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
    backgroundColor: '#FFFFFF',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
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
