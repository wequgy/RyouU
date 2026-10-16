import React, { ReactNode } from 'react';
import { View, StyleSheet, Text, TouchableOpacity } from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useSecureDisplay } from './useSecureDisplay';
import { AntiScreencastShield } from './AntiScreencastShield';

interface SecureDisplayLayerProps {
  children: ReactNode;
  enabled?: boolean;
  onScreenshotAttempt?: () => void;
  showDevSimulatorControls?: boolean;
}

/**
 * SecureDisplayLayer
 * 
 * Hardware-level screencast and screen recording protection container.
 * 
 * Functions like Netflix, Disney+, and Banking apps:
 * - On Android, sets WindowManager.LayoutParams.FLAG_SECURE to force black screen capture.
 * - On iOS, monitors UIScreen.capturedDidChangeNotification and shields the UI.
 * - Overlays AntiScreencastShield immediately when screen recording or casting is detected.
 */
export const SecureDisplayLayer: React.FC<SecureDisplayLayerProps> = ({
  children,
  enabled = true,
  onScreenshotAttempt,
  showDevSimulatorControls = true,
}) => {
  const {
    isSecureActive,
    isCaptureDetected,
    simulatedScreencast,
    toggleScreencastSimulation,
    platform,
  } = useSecureDisplay({
    enabled,
    onScreenshotAttempt,
  });

  return (
    <View style={styles.container}>
      {/* Dev Simulator Controller: allows verifying DRM/screencast protection */}
      {showDevSimulatorControls && (
        <View style={styles.devBar}>
          <View style={styles.devStatusLeft}>
            <View style={[styles.statusDot, isSecureActive ? styles.dotGreen : styles.dotAmber]} />
            <Text style={styles.devStatusText}>
              DRM Layer: {isSecureActive ? 'FLAG_SECURE (ACTIVE)' : 'INITIALIZING'}
            </Text>
          </View>

          <TouchableOpacity
            style={[styles.simButton, simulatedScreencast ? styles.simButtonActive : null]}
            onPress={toggleScreencastSimulation}
            activeOpacity={0.7}
          >
            <MaterialCommunityIcons
              name={simulatedScreencast ? 'cast-connected' : 'cast'}
              size={14}
              color={simulatedScreencast ? '#EF4444' : '#94A3B8'}
            />
            <Text
              style={[
                styles.simButtonText,
                simulatedScreencast ? styles.simButtonTextActive : null,
              ]}
            >
              {simulatedScreencast ? 'Stop Cast Sim' : 'Simulate Screencast'}
            </Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Main Content Area */}
      <View style={styles.contentWrapper}>
        {children}

        {/* Screencast / Recording DRM Protective Shield */}
        {isCaptureDetected && (
          <AntiScreencastShield
            isSimulated={simulatedScreencast}
            onDismissSimulation={toggleScreencastSimulation}
          />
        )}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#05070E',
  },
  devBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#0F172A',
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#1E293B',
    zIndex: 10000,
  },
  devStatusLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  statusDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
  },
  dotGreen: {
    backgroundColor: '#10B981',
  },
  dotAmber: {
    backgroundColor: '#F59E0B',
  },
  devStatusText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#94A3B8',
    letterSpacing: 0.4,
    fontFamily: 'monospace',
  },
  simButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    backgroundColor: '#1E293B',
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#334155',
  },
  simButtonActive: {
    backgroundColor: 'rgba(239, 68, 68, 0.2)',
    borderColor: '#EF4444',
  },
  simButtonText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#94A3B8',
  },
  simButtonTextActive: {
    color: '#EF4444',
  },
  contentWrapper: {
    flex: 1,
    position: 'relative',
  },
});
