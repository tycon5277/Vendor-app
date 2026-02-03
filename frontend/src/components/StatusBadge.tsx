import React from 'react';
import { View, Text, StyleSheet } from 'react-native';

interface Props {
  status: string;
}

const statusColors: Record<string, { bg: string; text: string }> = {
  pending: { bg: '#FEF3C7', text: '#D97706' },
  confirmed: { bg: '#DBEAFE', text: '#2563EB' },
  preparing: { bg: '#E0E7FF', text: '#4F46E5' },
  ready: { bg: '#D1FAE5', text: '#059669' },
  picked_up: { bg: '#CFFAFE', text: '#0891B2' },
  on_the_way: { bg: '#FEE2E2', text: '#DC2626' },
  delivered: { bg: '#D1FAE5', text: '#059669' },
  cancelled: { bg: '#FEE2E2', text: '#DC2626' },
  rejected: { bg: '#FEE2E2', text: '#DC2626' },
  available: { bg: '#D1FAE5', text: '#059669' },
  offline: { bg: '#F3F4F6', text: '#6B7280' },
};

export const StatusBadge: React.FC<Props> = ({ status }) => {
  const colors = statusColors[status] || { bg: '#F3F4F6', text: '#6B7280' };

  return (
    <View style={[styles.badge, { backgroundColor: colors.bg }]}>
      <Text style={[styles.text, { color: colors.text }]}>
        {status.replace(/_/g, ' ').toUpperCase()}
      </Text>
    </View>
  );
};

const styles = StyleSheet.create({
  badge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  text: {
    fontSize: 11,
    fontWeight: '600',
    textTransform: 'uppercase',
  },
});
