import React from 'react';
import { StatusBar } from 'expo-status-bar';
import { StyleSheet, View } from 'react-native';
import { DashboardScreen } from './src/screens/DashboardScreen';

/**
 * ApexPay Mock Fintech Mobile App
 * 
 * Features:
 * 1. Asks for KYC on launch (gatekeeper triggers KYC modal for unverified users).
 * 2. Gateway pathways for Custom KYC SDKs (IKycSdkGateway & KycGatewayRegistry - strictly no Razorpay).
 * 3. Anti-screencasting display layer (DRM / FLAG_SECURE protection like Netflix & streaming apps).
 */
export default function App() {
  return (
    <View style={styles.container}>
      <StatusBar style="dark" />
      <DashboardScreen initialLaunchKycTrigger={true} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F8FAFC',
  },
});
