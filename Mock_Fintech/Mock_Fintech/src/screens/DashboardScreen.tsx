import React, { useState } from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  Alert,
  Text,
  TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { FintechHeader } from '../components/FintechHeader';
import { BalanceCard } from '../components/BalanceCard';
import { KycPromptBanner } from '../components/KycPromptBanner';
import { QuickActions } from '../components/QuickActions';
import { TransactionList } from '../components/TransactionList';
import { KycModalScreen } from './KycModalScreen';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { UserProfile, AccountBalance, Transaction, KycSdkResult } from '../types';

interface DashboardScreenProps {
  initialLaunchKycTrigger?: boolean;
}

export const DashboardScreen: React.FC<DashboardScreenProps> = ({
  initialLaunchKycTrigger = true,
}) => {
  // Mock User Profile
  const [user, setUser] = useState<UserProfile>({
    id: 'usr_apex_9042',
    fullName: 'Alex Rivera',
    email: 'alex.rivera@apexvault.io',
    phone: '+1 (555) 234-5678',
    accountNumber: 'APX-4829-0192',
    kycStatus: 'NOT_STARTED', // Initial state triggers KYC on launch
    kycTier: 'Tier 0 (Restricted)',
    transferLimitDaily: 1000,
  });

  const [balance, setBalance] = useState<AccountBalance>({
    currency: 'USD',
    total: 48250.8,
    available: 36400.5,
    savings: 11850.3,
  });

  const [transactions] = useState<Transaction[]>([
    {
      id: 'tx_1',
      title: 'Stripe Payout',
      subtitle: 'Software Consulting',
      amount: 4500.0,
      type: 'credit',
      category: 'salary',
      date: 'Today, 2:45 PM',
      status: 'completed',
      iconName: 'cash-multiple',
    },
    {
      id: 'tx_2',
      title: 'Apple Store NYC',
      subtitle: 'Hardware Purchase',
      amount: 1299.0,
      type: 'debit',
      category: 'shopping',
      date: 'Yesterday',
      status: 'completed',
      iconName: 'laptop',
    },
    {
      id: 'tx_3',
      title: 'AWS Cloud Hosting',
      subtitle: 'Monthly Infrastructure',
      amount: 342.18,
      type: 'debit',
      category: 'shopping',
      date: 'Oct 14',
      status: 'completed',
      iconName: 'cloud-outline',
    },
    {
      id: 'tx_4',
      title: 'Dividend Yield',
      subtitle: 'Apex Global Equity Fund',
      amount: 215.4,
      type: 'credit',
      category: 'investment',
      date: 'Oct 12',
      status: 'completed',
      iconName: 'chart-arc',
    },
  ]);

  // Launch KYC trigger state
  const [isKycModalOpen, setIsKycModalOpen] = useState(initialLaunchKycTrigger);

  const isVerified = user.kycStatus === 'VERIFIED';

  const handleActionPress = (actionId: string) => {
    if (!isVerified && (actionId === 'send' || actionId === 'cards' || actionId === 'invest')) {
      Alert.alert(
        'Identity Verification Required',
        'Financial regulations require government identity verification (KYC) before sending money, provisioning debit cards, or investing.',
        [
          { text: 'Cancel', style: 'cancel' },
          {
            text: 'Verify Now (KYC)',
            style: 'default',
            onPress: () => setIsKycModalOpen(true),
          },
        ]
      );
      return;
    }

    Alert.alert('Action Triggered', `Action '${actionId}' selected.`);
  };

  const handleVerificationSuccess = (result: KycSdkResult) => {
    setUser((prev) => ({
      ...prev,
      kycStatus: 'VERIFIED',
      kycTier: 'Tier 1 (Basic Verified)',
      kycCompletedAt: new Date().toISOString(),
      verificationSessionId: result.verificationId,
      transferLimitDaily: 100000,
    }));
  };

  const handleResetKyc = () => {
    setUser((prev) => ({
      ...prev,
      kycStatus: 'NOT_STARTED',
      kycTier: 'Tier 0 (Restricted)',
      kycCompletedAt: undefined,
      verificationSessionId: undefined,
      transferLimitDaily: 1000,
    }));
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="dark" />
      <ScrollView style={styles.container} showsVerticalScrollIndicator={false}>
        {/* Header */}
        <FintechHeader
          user={user}
          onNotificationsPress={() => Alert.alert('Notifications', 'No unread notifications.')}
          onProfilePress={() => Alert.alert('Profile', `User ID: ${user.id}\nEmail: ${user.email}`)}
        />

        {/* KYC Interceptor / Prompt on Launch if unverified */}
        {!isVerified && (
          <KycPromptBanner onVerifyPress={() => setIsKycModalOpen(true)} />
        )}

        {/* Balance & Card Details */}
        <BalanceCard
          user={user}
          balance={balance}
          onKycPress={() => setIsKycModalOpen(true)}
        />

        {/* Quick Actions */}
        <QuickActions
          isVerified={isVerified}
          onActionPress={handleActionPress}
        />

        {/* Transaction History */}
        <TransactionList transactions={transactions} />

        {/* Developer Sandbox Controls */}
        <View style={styles.devControlsBox}>
          <Text style={styles.devControlsTitle}>App State / SDK Testing Controls</Text>
          <View style={styles.devButtonsRow}>
            <TouchableOpacity
              style={styles.devBtn}
              onPress={() => setIsKycModalOpen(true)}
              activeOpacity={0.8}
            >
              <MaterialCommunityIcons name="open-in-app" size={16} color="#2563EB" />
              <Text style={styles.devBtnText}>Launch KYC Flow</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.devBtn, styles.devBtnAmber]}
              onPress={handleResetKyc}
              activeOpacity={0.8}
            >
              <MaterialCommunityIcons name="refresh" size={16} color="#D97706" />
              <Text style={[styles.devBtnText, { color: '#D97706' }]}>Reset KYC to Unverified</Text>
            </TouchableOpacity>
          </View>
        </View>
      </ScrollView>

      {/* KYC SDK Modal Hosted in Secure Display Layer */}
      <KycModalScreen
        visible={isKycModalOpen}
        user={user}
        onClose={() => setIsKycModalOpen(false)}
        onVerificationSuccess={handleVerificationSuccess}
      />
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#F8FAFC',
  },
  container: {
    flex: 1,
  },
  devControlsBox: {
    marginHorizontal: 20,
    marginBottom: 40,
    backgroundColor: '#FFFFFF',
    borderRadius: 14,
    padding: 16,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 2,
  },
  devControlsTitle: {
    fontSize: 11,
    fontWeight: '700',
    color: '#64748B',
    marginBottom: 10,
    textTransform: 'uppercase',
  },
  devButtonsRow: {
    flexDirection: 'row',
    gap: 10,
  },
  devBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    backgroundColor: '#EFF6FF',
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#DBEAFE',
  },
  devBtnAmber: {
    borderColor: '#FDE68A',
    backgroundColor: '#FFFBEB',
  },
  devBtnText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#2563EB',
  },
});
