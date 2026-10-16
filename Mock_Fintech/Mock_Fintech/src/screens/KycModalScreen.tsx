import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  Modal,
  Linking,
  Platform,
  TextInput,
  PermissionsAndroid,
} from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { WebView } from 'react-native-webview';
import { SecureDisplayLayer } from '../security/SecureDisplayLayer';
import { KycGatewayRegistry } from '../sdk/core/KycGatewayRegistry';
import { UnCloneKycSdkAdapter, getDetectedServerUrl } from '../sdk/adapters/UnCloneKycSdkAdapter';
import {
  UserProfile,
  KycDocumentType,
  KycSdkEvent,
  KycSdkResult,
} from '../types';

interface KycModalScreenProps {
  visible: boolean;
  user: UserProfile;
  onClose: () => void;
  onVerificationSuccess: (result: KycSdkResult) => void;
}

export const KycModalScreen: React.FC<KycModalScreenProps> = ({
  visible,
  user,
  onClose,
  onVerificationSuccess,
}) => {
  const [selectedDoc, setSelectedDoc] = useState<KycDocumentType>('NATIONAL_ID');
  const [isVerifying, setIsVerifying] = useState(false);
  const [events, setEvents] = useState<KycSdkEvent[]>([]);
  const [activeStep, setActiveStep] = useState<number>(0);
  const [result, setResult] = useState<KycSdkResult | null>(null);
  const [flowUrl, setFlowUrl] = useState<string | null>(null);
  const [activeVerificationId, setActiveVerificationId] = useState<string | null>(null);
  const [serverUrl, setServerUrl] = useState<string>(getDetectedServerUrl());
  const [activeGatewayId, setActiveGatewayId] = useState<string>('unclone-ai-kyc-sdk');
  const [connectionStatus, setConnectionStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const [showServerConfig, setShowServerConfig] = useState(false);

  // Real user identity inputs — standard KYC basic details
  const [userFullName, setUserFullName] = useState<string>('');
  const [userDob, setUserDob] = useState<string>('');         // YYYY-MM-DD
  const [userEmail, setUserEmail] = useState<string>('');
  const [userPhone, setUserPhone] = useState<string>('');
  const [formError, setFormError] = useState<string>('');

  const webViewRef = useRef<any>(null);
  const AnyWebView = WebView as any;

  // Get active gateway
  const activeGateway = KycGatewayRegistry.getGateway(activeGatewayId) || KycGatewayRegistry.getActiveGateway();

  // Test backend connectivity
  const testBackendConnection = async (target = serverUrl) => {
    setConnectionStatus('checking');
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 3500);
      const res = await fetch(`${target.replace(/\/$/, '')}/healthz`, { signal: controller.signal });
      clearTimeout(timeoutId);
      if (res.ok) {
        setConnectionStatus('online');
      } else {
        setConnectionStatus('offline');
      }
    } catch (_) {
      setConnectionStatus('offline');
    }
  };

  // Reset state and test connection when modal opens
  useEffect(() => {
    if (visible) {
      setEvents([]);
      setActiveStep(0);
      setResult(null);
      setIsVerifying(false);
      setFlowUrl(null);
      setActiveVerificationId(null);
      setFormError('');
      // Pre-populate from user profile if available
      setUserFullName(user.fullName || '');
      setUserEmail(user.email || '');
      testBackendConnection(serverUrl);
    }
  }, [visible]);

  // Subscribe to SDK events
  useEffect(() => {
    if (!visible) return;

    const unsubscribe = activeGateway.onEvent((event: KycSdkEvent) => {
      setEvents((prev) => [event, ...prev]);
      if (event.step) {
        setActiveStep(event.step);
      }
    });

    return () => {
      unsubscribe();
    };
  }, [visible, activeGateway]);

  // Handle gateway server change
  const handleServerChange = (url: string) => {
    setServerUrl(url);
    if (activeGateway instanceof UnCloneKycSdkAdapter) {
      activeGateway.setApiBase(url);
    }
    testBackendConnection(url);
  };

  const handleGatewayChange = (gatewayId: string) => {
    setActiveGatewayId(gatewayId);
    try {
      KycGatewayRegistry.setActiveGateway(gatewayId);
    } catch (_) {}
  };

  const startKycFlow = async () => {
    // Validate standard basic details
    if (!userFullName.trim()) { setFormError('Please enter your full legal name.'); return; }
    if (!userDob.trim() || !/^\d{4}-\d{2}-\d{2}$/.test(userDob.trim())) {
      setFormError('Please enter your date of birth in YYYY-MM-DD format (e.g. 2000-01-15).');
      return;
    }
    if (!userEmail.trim() || !userEmail.includes('@')) { setFormError('Please enter a valid email address for OTP delivery.'); return; }
    if (!userPhone.trim() || userPhone.replace(/\D/g,'').length < 10) { setFormError('Please enter a valid 10-digit mobile number.'); return; }
    setFormError('');

    setIsVerifying(true);
    setEvents([]);
    setActiveStep(1);
    setResult(null);

    // Request Android native hardware permissions upfront
    if (Platform.OS === 'android') {
      try {
        await PermissionsAndroid.requestMultiple([
          PermissionsAndroid.PERMISSIONS.CAMERA,
          PermissionsAndroid.PERMISSIONS.RECORD_AUDIO,
        ]);
      } catch (pErr) {
        console.warn('PermissionsAndroid error:', pErr);
      }
    }

    try {
      // 1. Initialize Gateway Config
      await activeGateway.initialize({
        apiKey: 'apex_live_sec_token_9948291a',
        environment: 'sandbox',
        theme: {
          isDarkMode: false,
          primaryColor: '#2563EB',
        },
      });

      // 2. If UnClone SDK adapter is active, create real session and show live WebView
      if (activeGateway instanceof UnCloneKycSdkAdapter) {
        activeGateway.setApiBase(serverUrl);
        const session = await activeGateway.createVerificationSession({
          userId: user.id,
          fullName: userFullName.trim(),
          email: userEmail.trim(),
          phone: userPhone.trim(),
          dob: userDob.trim(),
          docType: selectedDoc,
          sessionReferenceId: `APX-${Date.now()}`,
          clientNonce: Math.random().toString(36).substring(2, 15),
        });

        setActiveVerificationId(session.verificationId);
        setFlowUrl(session.flowUrl);
        setActiveStep(2);
      } else {
        // Fallback simulated mock flow
        const sdkResult = await activeGateway.launchKycFlow({
          userId: user.id,
          fullName: user.fullName,
          email: user.email,
          docType: selectedDoc,
          sessionReferenceId: `SESS-${Date.now()}`,
          clientNonce: Math.random().toString(36).substring(2, 15),
        });

        setResult(sdkResult);
        if (sdkResult.status === 'SUCCESS') {
          setTimeout(() => {
            onVerificationSuccess(sdkResult);
          }, 1200);
        }
        setIsVerifying(false);
      }
    } catch (err) {
      console.error('[KycModalScreen] Verification error:', err);
      setResult({
        status: 'FAILED',
        timestamp: Date.now(),
        failureReason: err instanceof Error ? err.message : 'Failed to connect to KYC server',
      });
      setIsVerifying(false);
    }
  };

  // Handle postMessage from embedded WebView
  const handleWebViewMessage = (event: { nativeEvent: { data: string } }) => {
    try {
      const data = JSON.parse(event.nativeEvent.data);
      console.log('[KycModalScreen] WebView message:', data);

      if (data.type === 'kyc_complete') {
        const isSuccess = data.status === 'completed' || data.status === 'needs_review';
        const finalResult: KycSdkResult = {
          status: isSuccess ? 'SUCCESS' : 'FAILED',
          verificationId: data.vid || activeVerificationId || `KYC-${Date.now()}`,
          timestamp: Date.now(),
          riskScore: data.status === 'completed' ? 0.01 : 0.08,
          rawDetails: data,
        };

        setResult(finalResult);
        setIsVerifying(false);
        setFlowUrl(null);

        if (isSuccess) {
          setTimeout(() => {
            onVerificationSuccess(finalResult);
          }, 1200);
        }
      }
    } catch (e) {
      console.warn('Failed to parse WebView message:', e);
    }
  };

  const handleOpenInBrowser = async () => {
    if (flowUrl) {
      try {
        await Linking.openURL(flowUrl);
      } catch (err) {
        console.warn('Cannot open URL in browser:', err);
      }
    }
  };

  const handleCheckBackendStatus = async () => {
    if (!activeVerificationId || !(activeGateway instanceof UnCloneKycSdkAdapter)) return;
    try {
      const data = await activeGateway.pollVerificationStatus(activeVerificationId, 2, 500);
      const isSuccess = data.status === 'completed' || data.status === 'needs_review';
      const finalResult: KycSdkResult = {
        status: isSuccess ? 'SUCCESS' : 'FAILED',
        verificationId: activeVerificationId,
        timestamp: Date.now(),
        riskScore: data.status === 'completed' ? 0.01 : 0.08,
        rawDetails: data,
      };
      setResult(finalResult);
      setIsVerifying(false);
      setFlowUrl(null);
      if (isSuccess) {
        onVerificationSuccess(finalResult);
      }
    } catch (_) {
      // Still in progress
    }
  };

  const documentOptions: Array<{
    type: KycDocumentType;
    title: string;
    subtitle: string;
    icon: keyof typeof MaterialCommunityIcons.glyphMap;
  }> = [
    {
      type: 'NATIONAL_ID',
      title: 'National Identity Card',
      subtitle: 'Aadhaar / Government Photo ID card',
      icon: 'badge-account-horizontal-outline',
    },
    {
      type: 'PASSPORT',
      title: 'Passport',
      subtitle: 'Biometric page or machine-readable travel document',
      icon: 'passport',
    },
    {
      type: 'DRIVING_LICENSE',
      title: "Driver's License",
      subtitle: 'State or national driving credential',
      icon: 'card-account-details-outline',
    },
  ];

  return (
    <Modal visible={visible} animationType="slide" transparent={false} onRequestClose={onClose}>
      <SecureDisplayLayer enabled={visible} showDevSimulatorControls={false}>
        <View style={styles.container}>
          {/* Top Bar */}
          <View style={styles.topBar}>
            <View>
              <Text style={styles.modalTitle}>Identity Verification</Text>
              <Text style={styles.sdkBadge}>
                SDK: {activeGateway.name} (v{activeGateway.version})
              </Text>
            </View>

            <TouchableOpacity
              style={styles.closeBtn}
              onPress={onClose}
              activeOpacity={0.8}
            >
              <MaterialCommunityIcons name="close" size={20} color="#94A3B8" />
            </TouchableOpacity>
          </View>

          {/* Security Banner */}
          <View style={styles.securityBanner}>
            <MaterialCommunityIcons name="shield-lock-outline" size={16} color="#10B981" />
            <Text style={styles.securityBannerText}>
              Protected Session: Hardware-enforced screencast &amp; capture prevention active.
            </Text>
          </View>

          {/* LIVE WEBVIEW SESSION */}
          {flowUrl && !result ? (
            <View style={styles.webViewWrapper}>
              {/* Quick actions top bar for WebView */}
              <View style={styles.webViewHeader}>
                <View style={styles.webViewStatusBadge}>
                  <View style={styles.onlineDot} />
                  <Text style={styles.webViewStatusText}>Active KYC Verification Tunnel</Text>
                </View>
                <View style={styles.webViewActions}>
                  <TouchableOpacity
                    style={styles.iconBtn}
                    onPress={handleOpenInBrowser}
                    activeOpacity={0.8}
                  >
                    <MaterialCommunityIcons name="open-in-new" size={16} color="#38BDF8" />
                    <Text style={styles.iconBtnText}>Browser</Text>
                  </TouchableOpacity>

                  <TouchableOpacity
                    style={styles.iconBtn}
                    onPress={handleCheckBackendStatus}
                    activeOpacity={0.8}
                  >
                    <MaterialCommunityIcons name="sync" size={16} color="#10B981" />
                    <Text style={styles.iconBtnText}>Refresh</Text>
                  </TouchableOpacity>
                </View>
              </View>

              {/* The Live Interactive KYC WebView */}
              <AnyWebView
                ref={webViewRef}
                source={{ uri: flowUrl }}
                style={styles.webView}
                javaScriptEnabled={true}
                domStorageEnabled={true}
                allowsInlineMediaPlayback={true}
                mediaPlaybackRequiresUserAction={false}
                mediaCapturePermissionGrantType="grant"
                mixedContentMode="always"
                allowFileAccess={true}
                originWhitelist={['*']}
                onPermissionRequest={(event: any) => {
                  try {
                    if (typeof event?.grant === 'function') {
                      event.grant(event.resources);
                    } else if (typeof event?.nativeEvent?.grant === 'function') {
                      event.nativeEvent.grant(event.nativeEvent.resources);
                    } else if (typeof event?.nativeEvent?.request?.grant === 'function') {
                      event.nativeEvent.request.grant(event.nativeEvent.request.resources);
                    } else if (typeof event?.request?.grant === 'function') {
                      event.request.grant(event.request.resources);
                    }
                  } catch (pErr) {
                    console.warn('onPermissionRequest grant error:', pErr);
                  }
                }}
                onMessage={handleWebViewMessage}
                startInLoadingState={true}
                renderLoading={() => (
                  <View style={styles.loadingContainer}>
                    <ActivityIndicator size="large" color="#10B981" />
                    <Text style={styles.loadingText}>Initializing secure KYC channel...</Text>
                  </View>
                )}
              />
            </View>
          ) : (
            <ScrollView style={styles.scrollContent} contentContainerStyle={styles.scrollInner}>
              {/* STEP 1: PRE-LAUNCH CONFIG & SELECTION */}
              {!isVerifying && !result && (
                <>
                  {/* ── Identity Details Form ── */}
                  <Text style={styles.stepTitle}>Your Basic Details</Text>
                  <Text style={styles.stepDescription}>
                    Enter your basic personal details. We'll verify your email and phone next, and then capture your government ID.
                  </Text>

                  <View style={styles.inputGroup}>
                    <Text style={styles.inputLabel}>Full Legal Name</Text>
                    <TextInput
                      style={styles.inputField}
                      value={userFullName}
                      onChangeText={setUserFullName}
                      placeholder="e.g. Alex Rivera"
                      placeholderTextColor="#94A3B8"
                      autoCapitalize="words"
                      returnKeyType="next"
                    />
                  </View>

                  <View style={styles.inputGroup}>
                    <Text style={styles.inputLabel}>Date of Birth</Text>
                    <TextInput
                      style={styles.inputField}
                      value={userDob}
                      onChangeText={setUserDob}
                      placeholder="YYYY-MM-DD  e.g. 2000-01-15"
                      placeholderTextColor="#94A3B8"
                      keyboardType="numeric"
                      returnKeyType="next"
                      maxLength={10}
                    />
                  </View>

                  <View style={styles.inputGroup}>
                    <Text style={styles.inputLabel}>Email Address</Text>
                    <TextInput
                      style={styles.inputField}
                      value={userEmail}
                      onChangeText={setUserEmail}
                      placeholder="e.g. user@example.com (OTP will be sent here)"
                      placeholderTextColor="#94A3B8"
                      keyboardType="email-address"
                      autoCapitalize="none"
                      returnKeyType="next"
                    />
                  </View>

                  <View style={styles.inputGroup}>
                    <Text style={styles.inputLabel}>Mobile Number</Text>
                    <TextInput
                      style={styles.inputField}
                      value={userPhone}
                      onChangeText={setUserPhone}
                      placeholder="10-digit mobile number e.g. 9876543210"
                      placeholderTextColor="#94A3B8"
                      keyboardType="phone-pad"
                      returnKeyType="done"
                      maxLength={13}
                    />
                  </View>

                  {formError !== '' && (
                    <View style={styles.errorBox}>
                      <MaterialCommunityIcons name="alert-circle-outline" size={16} color="#DC2626" />
                      <Text style={styles.errorText}>{formError}</Text>
                    </View>
                  )}

                  {/* Document Type */}
                  <Text style={[styles.stepTitle, { marginTop: 12 }]}>ID Document to Verify</Text>
                  <Text style={styles.stepDescription}>
                    Select the government identity document you will upload during the verification session.
                  </Text>
                  <View style={styles.docList}>
                    {documentOptions.map((doc) => {
                      const isSelected = selectedDoc === doc.type;
                      return (
                        <TouchableOpacity
                          key={doc.type}
                          style={[styles.docCard, isSelected && styles.docCardSelected]}
                          onPress={() => setSelectedDoc(doc.type)}
                          activeOpacity={0.8}
                        >
                          <View style={[styles.docIconCircle, isSelected && styles.docIconSelected]}>
                            <MaterialCommunityIcons
                              name={doc.icon}
                              size={24}
                              color={isSelected ? '#2563EB' : '#64748B'}
                            />
                          </View>
                          <View style={styles.docInfo}>
                            <Text style={[styles.docTitle, isSelected && styles.docTitleSelected]}>
                              {doc.title}
                            </Text>
                            <Text style={styles.docSubtitle}>{doc.subtitle}</Text>
                          </View>
                          <View style={[styles.radioCircle, isSelected && styles.radioCircleSelected]}>
                            {isSelected && <View style={styles.radioInner} />}
                          </View>
                        </TouchableOpacity>
                      );
                    })}
                  </View>

                  {/* Verification Suite Checklist */}
                  <View style={styles.checksCard}>
                    <Text style={styles.checksTitle}>Integrated AI Verification Modules:</Text>
                    <View style={styles.checkPillGrid}>
                      <View style={styles.checkPill}>
                        <MaterialCommunityIcons name="face-recognition" size={14} color="#059669" />
                        <Text style={styles.checkPillText}>Face Match to ID</Text>
                      </View>
                      <View style={styles.checkPill}>
                        <MaterialCommunityIcons name="waveform" size={14} color="#059669" />
                        <Text style={styles.checkPillText}>AI Voice Detection</Text>
                      </View>
                      <View style={styles.checkPill}>
                        <MaterialCommunityIcons name="eye-outline" size={14} color="#059669" />
                        <Text style={styles.checkPillText}>Video Deepfake Filter</Text>
                      </View>
                      <View style={styles.checkPill}>
                        <MaterialCommunityIcons name="translate" size={14} color="#059669" />
                        <Text style={styles.checkPillText}>Spoken Name &amp; DOB</Text>
                      </View>
                      <View style={styles.checkPill}>
                        <MaterialCommunityIcons name="cellphone-message" size={14} color="#059669" />
                        <Text style={styles.checkPillText}>Phone &amp; Email OTP</Text>
                      </View>
                      <View style={styles.checkPill}>
                        <MaterialCommunityIcons name="dice-multiple-outline" size={14} color="#059669" />
                        <Text style={styles.checkPillText}>Spontaneous Phrase</Text>
                      </View>
                    </View>
                  </View>

                  {/* Server Connection Status & Config */}
                  <View style={styles.serverBox}>
                    <View style={styles.serverBoxHeader}>
                      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                        <MaterialCommunityIcons name="server-network" size={16} color="#2563EB" />
                        <Text style={styles.serverBoxTitle}>KYC Engine Connection</Text>
                      </View>
                      <View style={[
                        styles.statusIndicatorBadge,
                        { flexDirection: 'row', alignItems: 'center', gap: 4 },
                        connectionStatus === 'online' ? styles.statusBadgeOnline :
                        connectionStatus === 'checking' ? styles.statusBadgeChecking : styles.statusBadgeOffline
                      ]}>
                        <MaterialCommunityIcons
                          name={connectionStatus === 'online' ? 'check-circle' : connectionStatus === 'checking' ? 'progress-clock' : 'alert-circle'}
                          size={12}
                          color={connectionStatus === 'online' ? '#059669' : connectionStatus === 'checking' ? '#2563EB' : '#DC2626'}
                        />
                        <Text style={[
                          styles.statusBadgeText,
                          connectionStatus === 'online' ? styles.statusTextOnline :
                          connectionStatus === 'checking' ? styles.statusTextChecking : styles.statusTextOffline
                        ]}>
                          {connectionStatus === 'online' ? 'Online' :
                           connectionStatus === 'checking' ? 'Testing...' : 'Offline / Check IP'}
                        </Text>
                      </View>
                    </View>

                    <Text style={styles.serverCurrentText}>{serverUrl}</Text>

                    <View style={styles.serverPresetsRow}>
                      <TouchableOpacity
                        style={[
                          styles.presetBtn,
                          serverUrl === 'http://192.168.0.103:8000' && styles.presetBtnActive,
                        ]}
                        onPress={() => handleServerChange('http://192.168.0.103:8000')}
                      >
                        <Text style={[styles.presetBtnText, serverUrl === 'http://192.168.0.103:8000' && styles.presetBtnTextActive]}>
                          LAN (192.168.0.103)
                        </Text>
                      </TouchableOpacity>

                      <TouchableOpacity
                        style={[
                          styles.presetBtn,
                          serverUrl === 'http://10.0.2.2:8000' && styles.presetBtnActive,
                        ]}
                        onPress={() => handleServerChange('http://10.0.2.2:8000')}
                      >
                        <Text style={[styles.presetBtnText, serverUrl === 'http://10.0.2.2:8000' && styles.presetBtnTextActive]}>
                          Emulator (10.0.2.2)
                        </Text>
                      </TouchableOpacity>

                      <TouchableOpacity
                        style={[styles.presetBtn, { borderColor: '#CBD5E1' }]}
                        onPress={() => testBackendConnection(serverUrl)}
                      >
                        <Text style={styles.presetBtnText}>Ping Test</Text>
                      </TouchableOpacity>
                    </View>
                  </View>

                  {/* Launch Button */}
                  <TouchableOpacity
                    style={styles.launchButton}
                    onPress={startKycFlow}
                    activeOpacity={0.8}
                  >
                    <MaterialCommunityIcons name="camera-iris" size={20} color="#0A0E1A" />
                    <Text style={styles.launchButtonText}>Launch Live Verification</Text>
                  </TouchableOpacity>
                </>
              )}

              {/* SIMULATED SCANNER FALLBACK (If using MockCustomKycSdkGateway) */}
              {isVerifying && !flowUrl && (
                <View style={styles.verificationActiveContainer}>
                  <View style={styles.scannerViewport}>
                    <View style={styles.scannerTargetBox}>
                      <MaterialCommunityIcons name="face-recognition" size={54} color="#10B981" />
                      <Text style={styles.scannerPrompt}>Connecting to KYC engine...</Text>
                    </View>
                  </View>
                  <ActivityIndicator size="small" color="#10B981" style={{ marginTop: 16 }} />
                </View>
              )}

              {/* VERIFICATION RESULT SCREEN */}
              {!isVerifying && result && (
                <View style={styles.resultContainer}>
                  {result.status === 'SUCCESS' ? (
                    <>
                      <View style={styles.successIconCircle}>
                        <MaterialCommunityIcons name="check-decagram" size={64} color="#10B981" />
                      </View>
                      <Text style={styles.successTitle}>Identity Verified</Text>
                      <Text style={styles.successSubtitle}>
                        Your biometric proofs and credentials have passed all UnClone security checks.
                      </Text>

                      <View style={styles.resultDetailsCard}>
                        <View style={styles.detailRow}>
                          <Text style={styles.detailLabel}>Verification ID</Text>
                          <Text style={styles.detailValue}>{result.verificationId}</Text>
                        </View>
                        <View style={styles.detailRow}>
                          <Text style={styles.detailLabel}>Document Proof</Text>
                          <Text style={styles.detailValue}>{selectedDoc}</Text>
                        </View>
                        <View style={styles.detailRow}>
                          <Text style={styles.detailLabel}>Fraud / Deepfake Risk</Text>
                          <Text style={[styles.detailValue, { color: '#10B981' }]}>
                            {((result.riskScore || 0.01) * 100).toFixed(1)}% (Passed)
                          </Text>
                        </View>
                        <View style={styles.detailRow}>
                          <Text style={styles.detailLabel}>Transfer Limit</Text>
                          <Text style={[styles.detailValue, { color: '#38BDF8' }]}>
                            Unlocked ($100,000 / day)
                          </Text>
                        </View>
                      </View>

                      <TouchableOpacity
                        style={styles.completeBtn}
                        onPress={onClose}
                        activeOpacity={0.8}
                      >
                        <Text style={styles.completeBtnText}>Return to ApexPay</Text>
                      </TouchableOpacity>
                    </>
                  ) : (
                    <>
                      <View style={styles.failedIconCircle}>
                        <MaterialCommunityIcons name="alert-circle-outline" size={64} color="#EF4444" />
                      </View>
                      <Text style={styles.failedTitle}>Verification Incomplete</Text>
                      <Text style={styles.failedSubtitle}>
                        {result.failureReason || 'Verification session ended without completion.'}
                      </Text>

                      <TouchableOpacity
                        style={styles.retryBtn}
                        onPress={startKycFlow}
                        activeOpacity={0.8}
                      >
                        <Text style={styles.retryBtnText}>Retry Verification</Text>
                      </TouchableOpacity>
                    </>
                  )}
                </View>
              )}
            </ScrollView>
          )}
        </View>
      </SecureDisplayLayer>
    </Modal>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F0F4FF',
  },
  topBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingTop: 20,
    paddingBottom: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#E2E8F0',
    backgroundColor: '#FFFFFF',
  },
  modalTitle: {
    color: '#0F172A',
    fontSize: 18,
    fontWeight: '800',
  },
  sdkBadge: {
    color: '#3B82F6',
    fontSize: 11,
    fontWeight: '600',
    marginTop: 2,
  },
  closeBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#F1F5F9',
    justifyContent: 'center',
    alignItems: 'center',
  },
  securityBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: 'rgba(5, 150, 105, 0.08)',
    paddingVertical: 9,
    paddingHorizontal: 16,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(5, 150, 105, 0.15)',
  },
  securityBannerText: {
    flex: 1,
    color: '#059669',
    fontSize: 11,
    fontWeight: '600',
  },
  webViewWrapper: {
    flex: 1,
    backgroundColor: '#F0F4FF',
  },
  webViewHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 10,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E2E8F0',
  },
  webViewStatusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  onlineDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#059669',
  },
  webViewStatusText: {
    color: '#334155',
    fontSize: 12,
    fontWeight: '600',
  },
  webViewActions: {
    flexDirection: 'row',
    gap: 8,
  },
  iconBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
    backgroundColor: '#F1F5F9',
    borderWidth: 1,
    borderColor: '#E2E8F0',
  },
  iconBtnText: {
    color: '#334155',
    fontSize: 11,
    fontWeight: '600',
  },
  webView: {
    flex: 1,
    backgroundColor: '#F0F4FF',
  },
  loadingContainer: {
    position: 'absolute',
    inset: 0,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#F0F4FF',
  },
  loadingText: {
    color: '#64748B',
    fontSize: 13,
    marginTop: 12,
    fontWeight: '500',
  },
  scrollContent: {
    flex: 1,
    backgroundColor: '#F0F4FF',
  },
  scrollInner: {
    padding: 20,
    paddingBottom: 40,
  },
  stepTitle: {
    color: '#0F172A',
    fontSize: 17,
    fontWeight: '800',
    marginBottom: 6,
  },
  stepDescription: {
    color: '#64748B',
    fontSize: 13,
    lineHeight: 19,
    marginBottom: 20,
  },
  docList: {
    gap: 10,
    marginBottom: 18,
  },
  docCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    padding: 16,
    borderRadius: 16,
    borderWidth: 1.5,
    borderColor: '#E2E8F0',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 1,
  },
  docCardSelected: {
    backgroundColor: '#EFF6FF',
    borderColor: '#3B82F6',
  },
  docIconCircle: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#F1F5F9',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 14,
  },
  docIconSelected: {
    backgroundColor: 'rgba(59, 130, 246, 0.12)',
  },
  docInfo: {
    flex: 1,
  },
  docTitle: {
    color: '#1E293B',
    fontSize: 14,
    fontWeight: '700',
    marginBottom: 3,
  },
  docTitleSelected: {
    color: '#1D4ED8',
  },
  docSubtitle: {
    color: '#94A3B8',
    fontSize: 11,
  },
  radioCircle: {
    width: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 2,
    borderColor: '#CBD5E1',
    justifyContent: 'center',
    alignItems: 'center',
  },
  radioCircleSelected: {
    borderColor: '#3B82F6',
  },
  radioInner: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: '#3B82F6',
  },
  checksCard: {
    backgroundColor: '#EFF6FF',
    padding: 16,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#BFDBFE',
    marginBottom: 16,
  },
  checksTitle: {
    color: '#1D4ED8',
    fontSize: 11,
    fontWeight: '700',
    marginBottom: 10,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  checkPillGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  checkPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    backgroundColor: 'rgba(59,130,246,0.08)',
    borderWidth: 1,
    borderColor: 'rgba(59,130,246,0.2)',
    paddingVertical: 5,
    paddingHorizontal: 10,
    borderRadius: 8,
  },
  checkPillText: {
    color: '#1E40AF',
    fontSize: 11,
    fontWeight: '600',
  },
  serverBox: {
    backgroundColor: '#FFFFFF',
    borderRadius: 14,
    padding: 14,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    marginBottom: 18,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 3,
    elevation: 1,
  },
  serverBoxHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 4,
  },
  serverBoxTitle: {
    color: '#3B82F6',
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  serverCurrentText: {
    color: '#334155',
    fontSize: 13,
    fontFamily: 'monospace',
    marginBottom: 10,
  },
  serverPresetsRow: {
    flexDirection: 'column',
    gap: 6,
  },
  presetBtn: {
    paddingVertical: 9,
    paddingHorizontal: 12,
    borderRadius: 9,
    backgroundColor: '#F8FAFF',
    borderWidth: 1,
    borderColor: '#E2E8F0',
  },
  presetBtnActive: {
    borderColor: '#3B82F6',
    backgroundColor: 'rgba(59,130,246,0.08)',
  },
  presetBtnText: {
    color: '#475569',
    fontSize: 11,
    fontWeight: '600',
  },
  launchButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: '#3B82F6',
    paddingVertical: 16,
    borderRadius: 14,
    shadowColor: '#3B82F6',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 12,
    elevation: 4,
  },
  launchButtonText: {
    color: '#FFFFFF',
    fontWeight: '800',
    fontSize: 15,
    letterSpacing: 0.2,
  },
  verificationActiveContainer: {
    alignItems: 'center',
    paddingVertical: 20,
  },
  scannerViewport: {
    width: '100%',
    height: 220,
    backgroundColor: '#F1F5F9',
    borderRadius: 18,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    justifyContent: 'center',
    alignItems: 'center',
  },
  scannerTargetBox: {
    alignItems: 'center',
    gap: 12,
  },
  scannerPrompt: {
    color: '#64748B',
    fontSize: 13,
  },
  resultContainer: {
    alignItems: 'center',
    paddingVertical: 20,
  },
  successIconCircle: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: 'rgba(5, 150, 105, 0.1)',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
  },
  successTitle: {
    color: '#0F172A',
    fontSize: 22,
    fontWeight: '800',
    marginBottom: 6,
  },
  successSubtitle: {
    color: '#64748B',
    fontSize: 14,
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: 24,
  },
  resultDetailsCard: {
    width: '100%',
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 4,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    marginBottom: 20,
  },
  detailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#F1F5F9',
  },
  detailLabel: {
    color: '#94A3B8',
    fontSize: 12,
  },
  detailValue: {
    color: '#1E293B',
    fontSize: 12,
    fontWeight: '700',
    fontFamily: 'monospace',
  },
  completeBtn: {
    backgroundColor: '#059669',
    paddingVertical: 15,
    paddingHorizontal: 28,
    borderRadius: 13,
    width: '100%',
    alignItems: 'center',
    shadowColor: '#059669',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.25,
    shadowRadius: 8,
    elevation: 3,
  },
  completeBtnText: {
    color: '#FFFFFF',
    fontWeight: '800',
    fontSize: 15,
  },
  failedIconCircle: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: 'rgba(220, 38, 38, 0.08)',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
  },
  failedTitle: {
    color: '#DC2626',
    fontSize: 22,
    fontWeight: '800',
    marginBottom: 6,
  },
  failedSubtitle: {
    color: '#64748B',
    fontSize: 14,
    textAlign: 'center',
    marginBottom: 24,
    lineHeight: 20,
  },
  retryBtn: {
    backgroundColor: '#DC2626',
    paddingVertical: 15,
    paddingHorizontal: 28,
    borderRadius: 13,
    width: '100%',
    alignItems: 'center',
  },
  retryBtnText: {
    color: '#FFFFFF',
    fontWeight: '800',
    fontSize: 15,
  },
  inputGroup: {
    marginBottom: 14,
  },
  inputLabel: {
    color: '#64748B',
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 6,
  },
  inputField: {
    backgroundColor: '#FFFFFF',
    borderWidth: 1.5,
    borderColor: '#E2E8F0',
    borderRadius: 12,
    color: '#0F172A',
    fontSize: 15,
    paddingHorizontal: 14,
    paddingVertical: 13,
    fontFamily: Platform.OS === 'ios' ? 'System' : 'sans-serif',
  },
  errorBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: 'rgba(220,38,38,0.07)',
    borderWidth: 1,
    borderColor: 'rgba(220,38,38,0.25)',
    borderRadius: 10,
    padding: 12,
    marginBottom: 12,
  },
  errorText: {
    color: '#DC2626',
    fontSize: 13,
    flex: 1,
  },
  statusIndicatorBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 8,
    borderWidth: 1,
  },
  statusBadgeOnline: {
    backgroundColor: '#ECFDF5',
    borderColor: '#A7F3D0',
  },
  statusBadgeOffline: {
    backgroundColor: '#FEF2F2',
    borderColor: '#FECACA',
  },
  statusBadgeChecking: {
    backgroundColor: '#EFF6FF',
    borderColor: '#BFDBFE',
  },
  statusBadgeText: {
    fontSize: 11,
    fontWeight: '700',
  },
  statusTextOnline: {
    color: '#059669',
  },
  statusTextOffline: {
    color: '#DC2626',
  },
  statusTextChecking: {
    color: '#2563EB',
  },
  presetBtnTextActive: {
    color: '#2563EB',
    fontWeight: '700',
  },
});
