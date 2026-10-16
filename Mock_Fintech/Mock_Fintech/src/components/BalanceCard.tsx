import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { UserProfile, AccountBalance } from '../types';

interface BalanceCardProps {
  user: UserProfile;
  balance: AccountBalance;
  onKycPress?: () => void;
}

export const BalanceCard: React.FC<BalanceCardProps> = ({
  user,
  balance,
  onKycPress,
}) => {
  const [hideBalance, setHideBalance] = useState(false);
  const isVerified = user.kycStatus === 'VERIFIED';

  const formatAmount = (num: number) => {
    return num.toLocaleString('en-US', {
      style: 'currency',
      currency: balance.currency,
      minimumFractionDigits: 2,
    });
  };

  return (
    <View style={styles.outerContainer}>
      <LinearGradient
        colors={['#1E293B', '#0F172A', '#020617']}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={styles.cardGradient}
      >
        {/* Top Card Row */}
        <View style={styles.cardHeader}>
          <View style={styles.cardBrand}>
            <MaterialCommunityIcons name="integrated-circuit-chip" size={32} color="#F59E0B" />
            <MaterialCommunityIcons name="contactless-payment" size={24} color="#94A3B8" />
          </View>

          <TouchableOpacity
            style={[
              styles.tierPill,
              isVerified ? styles.tierVerified : styles.tierUnverified,
            ]}
            onPress={onKycPress}
            activeOpacity={0.8}
          >
            <MaterialCommunityIcons
              name={isVerified ? 'shield-check' : 'shield-alert'}
              size={14}
              color={isVerified ? '#10B981' : '#F59E0B'}
            />
            <Text
              style={[
                styles.tierText,
                isVerified ? styles.textVerified : styles.textUnverified,
              ]}
            >
              {isVerified ? 'KYC VERIFIED' : 'KYC REQUIRED'}
            </Text>
          </TouchableOpacity>
        </View>

        {/* Balance Section */}
        <View style={styles.balanceContainer}>
          <View style={styles.balanceHeader}>
            <Text style={styles.balanceLabel}>Total Available Balance</Text>
            <TouchableOpacity
              onPress={() => setHideBalance(!hideBalance)}
              hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
            >
              <MaterialCommunityIcons
                name={hideBalance ? 'eye-off-outline' : 'eye-outline'}
                size={18}
                color="#94A3B8"
              />
            </TouchableOpacity>
          </View>

          <Text style={styles.balanceValue}>
            {hideBalance ? '••••••••' : formatAmount(balance.available)}
          </Text>

          <View style={styles.savingsRow}>
            <Text style={styles.savingsLabel}>
              Savings Vault: {hideBalance ? '••••' : formatAmount(balance.savings)}
            </Text>
            <Text style={styles.limitLabel}>
              Daily Limit: {isVerified ? '$100,000' : '$1,000 (Locked)'}
            </Text>
          </View>
        </View>

        {/* Card Number & Expiry */}
        <View style={styles.cardFooter}>
          <View>
            <Text style={styles.cardNumber}>•••• •••• •••• 8492</Text>
            <Text style={styles.cardHolder}>{user.fullName.toUpperCase()}</Text>
          </View>

          <View style={styles.networkLogo}>
            <View style={[styles.cardCircle, { backgroundColor: '#EF4444' }]} />
            <View style={[styles.cardCircle, { backgroundColor: '#F59E0B', marginLeft: -10 }]} />
          </View>
        </View>
      </LinearGradient>
    </View>
  );
};

const styles = StyleSheet.create({
  outerContainer: {
    paddingHorizontal: 20,
    marginVertical: 12,
  },
  cardGradient: {
    borderRadius: 24,
    padding: 24,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.08)',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.35,
    shadowRadius: 20,
    elevation: 8,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 20,
  },
  cardBrand: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  tierPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingVertical: 5,
    paddingHorizontal: 10,
    borderRadius: 20,
    borderWidth: 1,
  },
  tierVerified: {
    backgroundColor: 'rgba(16, 185, 129, 0.12)',
    borderColor: 'rgba(16, 185, 129, 0.3)',
  },
  tierUnverified: {
    backgroundColor: 'rgba(245, 158, 11, 0.15)',
    borderColor: 'rgba(245, 158, 11, 0.4)',
  },
  tierText: {
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
  textVerified: {
    color: '#10B981',
  },
  textUnverified: {
    color: '#F59E0B',
  },
  balanceContainer: {
    marginBottom: 22,
  },
  balanceHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 4,
  },
  balanceLabel: {
    color: '#94A3B8',
    fontSize: 12,
    fontWeight: '500',
  },
  balanceValue: {
    color: '#F8FAFC',
    fontSize: 32,
    fontWeight: '800',
    letterSpacing: -0.5,
    marginBottom: 8,
  },
  savingsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  savingsLabel: {
    color: '#64748B',
    fontSize: 11,
    fontWeight: '500',
  },
  limitLabel: {
    color: '#38BDF8',
    fontSize: 11,
    fontWeight: '600',
  },
  cardFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-end',
    borderTopWidth: 1,
    borderTopColor: 'rgba(255, 255, 255, 0.06)',
    paddingTop: 16,
  },
  cardNumber: {
    color: '#CBD5E1',
    fontSize: 13,
    letterSpacing: 2,
    fontFamily: 'monospace',
    marginBottom: 4,
  },
  cardHolder: {
    color: '#64748B',
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 1,
  },
  networkLogo: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  cardCircle: {
    width: 24,
    height: 24,
    borderRadius: 12,
    opacity: 0.85,
  },
});
