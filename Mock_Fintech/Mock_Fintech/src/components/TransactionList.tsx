import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Transaction } from '../types';

interface TransactionListProps {
  transactions: Transaction[];
  onTransactionPress?: (tx: Transaction) => void;
}

export const TransactionList: React.FC<TransactionListProps> = ({
  transactions,
  onTransactionPress,
}) => {
  return (
    <View style={styles.container}>
      <View style={styles.headerRow}>
        <Text style={styles.title}>Recent Activity</Text>
        <TouchableOpacity>
          <Text style={styles.seeAllText}>See All</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.list}>
        {transactions.map((tx) => {
          const isCredit = tx.type === 'credit';

          return (
            <TouchableOpacity
              key={tx.id}
              style={styles.txItem}
              onPress={() => onTransactionPress && onTransactionPress(tx)}
              activeOpacity={0.7}
            >
              <View style={styles.iconCircle}>
                <MaterialCommunityIcons
                  name={tx.iconName as any}
                  size={20}
                  color={isCredit ? '#10B981' : '#38BDF8'}
                />
              </View>

              <View style={styles.txInfo}>
                <Text style={styles.txTitle}>{tx.title}</Text>
                <Text style={styles.txSubtitle}>
                  {tx.date} • {tx.subtitle}
                </Text>
              </View>

              <View style={styles.amountBlock}>
                <Text
                  style={[
                    styles.txAmount,
                    isCredit ? styles.amountCredit : styles.amountDebit,
                  ]}
                >
                  {isCredit ? '+' : '-'}${tx.amount.toFixed(2)}
                </Text>
                <View
                  style={[
                    styles.statusPill,
                    tx.status === 'completed'
                      ? styles.statusCompleted
                      : styles.statusPending,
                  ]}
                >
                  <Text
                    style={[
                      styles.statusPillText,
                      tx.status === 'completed'
                        ? styles.textCompleted
                        : styles.textPending,
                    ]}
                  >
                    {tx.status.toUpperCase()}
                  </Text>
                </View>
              </View>
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
    marginBottom: 40,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 14,
  },
  title: {
    color: '#475569',
    fontSize: 13,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  seeAllText: {
    color: '#2563EB',
    fontSize: 12,
    fontWeight: '600',
  },
  list: {
    backgroundColor: '#FFFFFF',
    borderRadius: 18,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    overflow: 'hidden',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 6,
    elevation: 2,
  },
  txItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 14,
    paddingHorizontal: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#F1F5F9',
  },
  iconCircle: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: '#F8FAFC',
    borderWidth: 1,
    borderColor: '#E2E8F0',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  txInfo: {
    flex: 1,
  },
  txTitle: {
    color: '#0F172A',
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 3,
  },
  txSubtitle: {
    color: '#64748B',
    fontSize: 11,
  },
  amountBlock: {
    alignItems: 'flex-end',
  },
  txAmount: {
    fontSize: 14,
    fontWeight: '700',
    marginBottom: 4,
  },
  amountCredit: {
    color: '#059669',
  },
  amountDebit: {
    color: '#0F172A',
  },
  statusPill: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  statusCompleted: {
    backgroundColor: 'rgba(16, 185, 129, 0.1)',
  },
  statusPending: {
    backgroundColor: 'rgba(245, 158, 11, 0.1)',
  },
  statusPillText: {
    fontSize: 8,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
  textCompleted: {
    color: '#059669',
  },
  textPending: {
    color: '#D97706',
  },
});
