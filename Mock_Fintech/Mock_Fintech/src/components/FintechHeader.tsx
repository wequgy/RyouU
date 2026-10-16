import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { UserProfile } from '../types';

interface FintechHeaderProps {
  user: UserProfile;
  onProfilePress?: () => void;
  onNotificationsPress?: () => void;
}

export const FintechHeader: React.FC<FintechHeaderProps> = ({
  user,
  onProfilePress,
  onNotificationsPress,
}) => {
  const isVerified = user.kycStatus === 'VERIFIED';

  return (
    <View style={styles.container}>
      <TouchableOpacity
        style={styles.profileSection}
        onPress={onProfilePress}
        activeOpacity={0.8}
      >
        <View style={styles.avatar}>
          <Text style={styles.avatarText}>
            {user.fullName
              .split(' ')
              .map((n) => n[0])
              .join('')
              .slice(0, 2)}
          </Text>
          <View
            style={[
              styles.avatarStatusBadge,
              isVerified ? styles.statusGreen : styles.statusAmber,
            ]}
          >
            <MaterialCommunityIcons
              name={isVerified ? 'check-decagram' : 'alert-circle'}
              size={12}
              color="#FFFFFF"
            />
          </View>
        </View>

        <View style={styles.nameBlock}>
          <View style={styles.nameRow}>
            <Text style={styles.greeting}>Welcome back,</Text>
            {isVerified && (
              <View style={styles.verifiedTag}>
                <Text style={styles.verifiedTagText}>VERIFIED</Text>
              </View>
            )}
          </View>
          <Text style={styles.userName}>{user.fullName}</Text>
        </View>
      </TouchableOpacity>

      <View style={styles.rightActions}>
        <View style={styles.securityIndicator}>
          <MaterialCommunityIcons name="shield-check" size={14} color="#10B981" />
          <Text style={styles.securityText}>DRM ARMED</Text>
        </View>

        <TouchableOpacity
          style={styles.iconButton}
          onPress={onNotificationsPress}
          activeOpacity={0.7}
        >
          <MaterialCommunityIcons name="bell-outline" size={20} color="#334155" />
          <View style={styles.unreadDot} />
        </TouchableOpacity>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 12,
  },
  profileSection: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  avatar: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#EFF6FF',
    borderWidth: 2,
    borderColor: '#BFDBFE',
    justifyContent: 'center',
    alignItems: 'center',
    position: 'relative',
  },
  avatarText: {
    color: '#2563EB',
    fontSize: 16,
    fontWeight: '700',
  },
  avatarStatusBadge: {
    position: 'absolute',
    bottom: -2,
    right: -2,
    width: 16,
    height: 16,
    borderRadius: 8,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 2,
    borderColor: '#FFFFFF',
  },
  statusGreen: {
    backgroundColor: '#10B981',
  },
  statusAmber: {
    backgroundColor: '#F59E0B',
  },
  nameBlock: {
    justifyContent: 'center',
  },
  nameRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  greeting: {
    fontSize: 11,
    color: '#64748B',
    fontWeight: '500',
  },
  verifiedTag: {
    backgroundColor: 'rgba(16, 185, 129, 0.12)',
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: 'rgba(16, 185, 129, 0.3)',
  },
  verifiedTagText: {
    color: '#059669',
    fontSize: 9,
    fontWeight: '800',
  },
  userName: {
    fontSize: 16,
    fontWeight: '700',
    color: '#0F172A',
  },
  rightActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  securityIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: 'rgba(16, 185, 129, 0.1)',
    borderWidth: 1,
    borderColor: 'rgba(16, 185, 129, 0.25)',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12,
  },
  securityText: {
    color: '#059669',
    fontSize: 9,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  iconButton: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#E2E8F0',
    justifyContent: 'center',
    alignItems: 'center',
    position: 'relative',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 3,
    elevation: 2,
  },
  unreadDot: {
    position: 'absolute',
    top: 8,
    right: 8,
    width: 7,
    height: 7,
    borderRadius: 3.5,
    backgroundColor: '#EF4444',
  },
});
