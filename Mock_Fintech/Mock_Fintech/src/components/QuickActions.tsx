import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';

interface QuickActionsProps {
  isVerified: boolean;
  onActionPress: (action: string) => void;
}

interface ActionItem {
  id: string;
  label: string;
  icon: keyof typeof MaterialCommunityIcons.glyphMap;
  color: string;
  requiresKyc: boolean;
}

export const QuickActions: React.FC<QuickActionsProps> = ({
  isVerified,
  onActionPress,
}) => {
  const actions: ActionItem[] = [
    {
      id: 'send',
      label: 'Send',
      icon: 'arrow-top-right',
      color: '#38BDF8',
      requiresKyc: true,
    },
    {
      id: 'receive',
      label: 'Request',
      icon: 'arrow-bottom-left',
      color: '#10B981',
      requiresKyc: false,
    },
    {
      id: 'add_cash',
      label: 'Add Cash',
      icon: 'plus-circle-outline',
      color: '#818CF8',
      requiresKyc: false,
    },
    {
      id: 'cards',
      label: 'Cards',
      icon: 'credit-card-outline',
      color: '#F472B6',
      requiresKyc: true,
    },
    {
      id: 'invest',
      label: 'Invest',
      icon: 'chart-line',
      color: '#FBBF24',
      requiresKyc: true,
    },
  ];

  return (
    <View style={styles.container}>
      <Text style={styles.sectionTitle}>Quick Actions</Text>
      <View style={styles.actionsRow}>
        {actions.map((action) => {
          const isLocked = action.requiresKyc && !isVerified;

          return (
            <TouchableOpacity
              key={action.id}
              style={styles.actionBtn}
              onPress={() => onActionPress(action.id)}
              activeOpacity={0.7}
            >
              <View style={styles.iconContainer}>
                <MaterialCommunityIcons
                  name={action.icon}
                  size={24}
                  color={isLocked ? '#94A3B8' : action.color}
                />
                {isLocked && (
                  <View style={styles.lockBadge}>
                    <MaterialCommunityIcons name="lock" size={10} color="#D97706" />
                  </View>
                )}
              </View>
              <Text style={[styles.actionLabel, isLocked && styles.labelLocked]}>
                {action.label}
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    paddingHorizontal: 20,
    marginBottom: 20,
  },
  sectionTitle: {
    color: '#475569',
    fontSize: 13,
    fontWeight: '700',
    letterSpacing: 0.5,
    marginBottom: 12,
  },
  actionsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  actionBtn: {
    alignItems: 'center',
    gap: 8,
  },
  iconContainer: {
    width: 54,
    height: 54,
    borderRadius: 27,
    backgroundColor: '#FFFFFF',
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#E2E8F0',
    position: 'relative',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 2,
  },
  lockBadge: {
    position: 'absolute',
    top: -2,
    right: -2,
    backgroundColor: '#FEF3C7',
    width: 18,
    height: 18,
    borderRadius: 9,
    borderWidth: 1.5,
    borderColor: '#F59E0B',
    justifyContent: 'center',
    alignItems: 'center',
  },
  actionLabel: {
    color: '#1E293B',
    fontSize: 12,
    fontWeight: '600',
  },
  labelLocked: {
    color: '#94A3B8',
  },
});
