import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';

interface AntiScreencastShieldProps {
  onDismissSimulation?: () => void;
  isSimulated?: boolean;
}

export const AntiScreencastShield: React.FC<AntiScreencastShieldProps> = ({
  onDismissSimulation,
  isSimulated = false,
}) => {
  return (
    <View style={styles.container}>
      <View style={styles.content}>
        <View style={styles.iconCircle}>
          <MaterialCommunityIcons name="cast-off" size={48} color="#EF4444" />
        </View>

        <Text style={styles.title}>SCREENCAST / RECORDING DETECTED</Text>
        
        <View style={styles.badge}>
          <MaterialCommunityIcons name="shield-alert-outline" size={16} color="#F59E0B" />
          <Text style={styles.badgeText}>DRM / HARDWARE SECURITY LAYER ACTIVE</Text>
        </View>

        <Text style={styles.description}>
          To protect sensitive personal identification and comply with financial data security regulations (e.g. PCI-DSS, AML/KYC), this verification display is shielded from screencasting, screen recording, and external capture.
        </Text>

        <View style={styles.detailBox}>
          <Text style={styles.detailTitle}>Security Enforcement:</Text>
          <Text style={styles.detailItem}>• Android: WindowManager.LayoutParams.FLAG_SECURE</Text>
          <Text style={styles.detailItem}>• iOS: UIScreen.capturedDidChangeNotification</Text>
          <Text style={styles.detailItem}>• Hardware: Video Compositor Blackout Layer</Text>
        </View>

        {isSimulated && onDismissSimulation && (
          <TouchableOpacity
            style={styles.resumeButton}
            onPress={onDismissSimulation}
            activeOpacity={0.8}
          >
            <MaterialCommunityIcons name="play-circle-outline" size={20} color="#FFFFFF" />
            <Text style={styles.resumeButtonText}>Stop Screencast Simulation</Text>
          </TouchableOpacity>
        )}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: '#000000',
    zIndex: 9999,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  content: {
    width: '100%',
    maxWidth: 420,
    alignItems: 'center',
    paddingVertical: 32,
    paddingHorizontal: 24,
    borderRadius: 20,
    backgroundColor: '#0B0F19',
    borderWidth: 1,
    borderColor: '#1E293B',
  },
  iconCircle: {
    width: 90,
    height: 90,
    borderRadius: 45,
    backgroundColor: 'rgba(239, 68, 68, 0.12)',
    borderWidth: 2,
    borderColor: 'rgba(239, 68, 68, 0.4)',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 20,
  },
  title: {
    fontSize: 16,
    fontWeight: '800',
    color: '#EF4444',
    textAlign: 'center',
    letterSpacing: 1.2,
    marginBottom: 10,
  },
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(245, 158, 11, 0.12)',
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: 'rgba(245, 158, 11, 0.3)',
    marginBottom: 16,
    gap: 6,
  },
  badgeText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#F59E0B',
    letterSpacing: 0.5,
  },
  description: {
    fontSize: 13,
    color: '#94A3B8',
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: 24,
  },
  detailBox: {
    width: '100%',
    backgroundColor: '#111827',
    padding: 14,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#1F2937',
    marginBottom: 20,
  },
  detailTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: '#E2E8F0',
    marginBottom: 6,
  },
  detailItem: {
    fontSize: 11,
    color: '#64748B',
    fontFamily: 'monospace',
    marginBottom: 4,
  },
  resumeButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: '#2563EB',
    paddingVertical: 12,
    paddingHorizontal: 20,
    borderRadius: 12,
    width: '100%',
  },
  resumeButtonText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 14,
  },
});
