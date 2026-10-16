import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';

interface KycPromptBannerProps {
  onVerifyPress: () => void;
}

export const KycPromptBanner: React.FC<KycPromptBannerProps> = ({ onVerifyPress }) => {
  return (
    <View style={styles.container}>
      <LinearGradient
        colors={['#FFFBEB', '#FEF3C7']}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 0 }}
        style={styles.bannerGradient}
      >
        <View style={styles.leftIcon}>
          <MaterialCommunityIcons name="alert-decagram" size={28} color="#D97706" />
        </View>

        <View style={styles.content}>
          <Text style={styles.title}>Action Required: Complete KYC</Text>
          <Text style={styles.subtitle}>
            Verify your government ID to lift transfer restrictions, access virtual debit cards, and unlock Tier 1 limits.
          </Text>

          <TouchableOpacity
            style={styles.button}
            onPress={onVerifyPress}
            activeOpacity={0.8}
          >
            <Text style={styles.buttonText}>Launch Identity Verification</Text>
            <MaterialCommunityIcons name="arrow-right" size={16} color="#FFFFFF" />
          </TouchableOpacity>
        </View>
      </LinearGradient>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    paddingHorizontal: 20,
    marginBottom: 16,
  },
  bannerGradient: {
    flexDirection: 'row',
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: '#FDE68A',
    gap: 14,
    shadowColor: '#D97706',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 6,
    elevation: 2,
  },
  leftIcon: {
    paddingTop: 2,
  },
  content: {
    flex: 1,
  },
  title: {
    color: '#B45309',
    fontSize: 14,
    fontWeight: '700',
    marginBottom: 4,
  },
  subtitle: {
    color: '#475569',
    fontSize: 12,
    lineHeight: 17,
    marginBottom: 12,
  },
  button: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    backgroundColor: '#D97706',
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: 8,
    gap: 6,
  },
  buttonText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 12,
  },
});
