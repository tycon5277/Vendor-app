import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  Alert,
  Switch,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useAuthStore } from '../../src/store/authStore';
import { vendorAPI, orderAPI } from '../../src/utils/api';
import { Analytics, Order } from '../../src/types';
import { StatusBadge } from '../../src/components/StatusBadge';

export default function HomeScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { user, setUser } = useAuthStore();
  const [refreshing, setRefreshing] = useState(false);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [pendingOrders, setPendingOrders] = useState<Order[]>([]);
  const [shopOpen, setShopOpen] = useState(user?.partner_status === 'available');

  const loadData = async () => {
    try {
      const [analyticsRes, ordersRes] = await Promise.all([
        vendorAPI.getAnalytics(),
        orderAPI.getPending(),
      ]);
      setAnalytics(analyticsRes.data);
      setPendingOrders(ordersRes.data);
    } catch (error) {
      console.error('Load data error:', error);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  }, []);

  const toggleShopStatus = async () => {
    const newStatus = shopOpen ? 'offline' : 'available';
    try {
      await vendorAPI.updateStatus(newStatus);
      setShopOpen(!shopOpen);
      if (user) {
        setUser({ ...user, partner_status: newStatus });
      }
    } catch (error) {
      Alert.alert('Error', 'Failed to update shop status');
    }
  };

  const handleSeedData = async () => {
    try {
      await vendorAPI.seedData();
      Alert.alert('Success', 'Sample data created!');
      loadData();
    } catch (error) {
      Alert.alert('Error', 'Failed to seed data');
    }
  };

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <ScrollView
        style={styles.scrollView}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
      >
        {/* Header */}
        <View style={styles.header}>
          <View>
            <Text style={styles.greeting}>Welcome back,</Text>
            <Text style={styles.shopName}>{user?.vendor_shop_name || 'Your Shop'}</Text>
          </View>
          <TouchableOpacity style={styles.notificationBtn}>
            <Ionicons name="notifications-outline" size={24} color="#374151" />
            {pendingOrders.length > 0 && (
              <View style={styles.badge}>
                <Text style={styles.badgeText}>{pendingOrders.length}</Text>
              </View>
            )}
          </TouchableOpacity>
        </View>

        {/* Shop Status Toggle */}
        <View style={styles.statusCard}>
          <View style={styles.statusLeft}>
            <View style={[styles.statusIndicator, shopOpen && styles.statusIndicatorOpen]} />
            <View>
              <Text style={styles.statusLabel}>Shop Status</Text>
              <Text style={styles.statusText}>{shopOpen ? 'OPEN' : 'CLOSED'}</Text>
            </View>
          </View>
          <Switch
            value={shopOpen}
            onValueChange={toggleShopStatus}
            trackColor={{ false: '#E5E7EB', true: '#86EFAC' }}
            thumbColor={shopOpen ? '#22C55E' : '#9CA3AF'}
          />
        </View>

        {/* Quick Stats */}
        <View style={styles.statsGrid}>
          <View style={styles.statCard}>
            <Ionicons name="receipt-outline" size={24} color="#6366F1" />
            <Text style={styles.statValue}>{analytics?.today.orders || 0}</Text>
            <Text style={styles.statLabel}>Today's Orders</Text>
          </View>
          <View style={styles.statCard}>
            <Ionicons name="cash-outline" size={24} color="#22C55E" />
            <Text style={styles.statValue}>₹{analytics?.today.earnings || 0}</Text>
            <Text style={styles.statLabel}>Today's Earnings</Text>
          </View>
          <View style={styles.statCard}>
            <Ionicons name="cube-outline" size={24} color="#F59E0B" />
            <Text style={styles.statValue}>{analytics?.products.in_stock || 0}</Text>
            <Text style={styles.statLabel}>Products In Stock</Text>
          </View>
          <View style={styles.statCard}>
            <Ionicons name="star-outline" size={24} color="#EC4899" />
            <Text style={styles.statValue}>{analytics?.rating?.toFixed(1) || '5.0'}</Text>
            <Text style={styles.statLabel}>Rating</Text>
          </View>
        </View>

        {/* Pending Orders Alert */}
        {pendingOrders.length > 0 && (
          <TouchableOpacity
            style={styles.alertCard}
            onPress={() => router.push('/(main)/orders')}
          >
            <View style={styles.alertIconContainer}>
              <Ionicons name="alert-circle" size={28} color="#DC2626" />
            </View>
            <View style={styles.alertContent}>
              <Text style={styles.alertTitle}>{pendingOrders.length} New Order{pendingOrders.length > 1 ? 's' : ''}</Text>
              <Text style={styles.alertSubtitle}>Tap to view and accept</Text>
            </View>
            <Ionicons name="chevron-forward" size={24} color="#DC2626" />
          </TouchableOpacity>
        )}

        {/* Recent Orders */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Recent Orders</Text>
            <TouchableOpacity onPress={() => router.push('/(main)/orders')}>
              <Text style={styles.seeAll}>See All</Text>
            </TouchableOpacity>
          </View>

          {pendingOrders.slice(0, 3).map((order) => (
            <TouchableOpacity
              key={order.order_id}
              style={styles.orderCard}
              onPress={() => router.push('/(main)/orders')}
            >
              <View style={styles.orderTop}>
                <Text style={styles.orderId}>#{order.order_id.slice(-8).toUpperCase()}</Text>
                <StatusBadge status={order.status} />
              </View>
              <Text style={styles.orderCustomer}>{order.customer_name || 'Customer'}</Text>
              <View style={styles.orderBottom}>
                <Text style={styles.orderItems}>{order.items.length} item{order.items.length > 1 ? 's' : ''}</Text>
                <Text style={styles.orderAmount}>₹{order.total_amount}</Text>
              </View>
            </TouchableOpacity>
          ))}

          {pendingOrders.length === 0 && (
            <View style={styles.emptyState}>
              <Ionicons name="receipt-outline" size={48} color="#D1D5DB" />
              <Text style={styles.emptyText}>No pending orders</Text>
              <TouchableOpacity style={styles.seedButton} onPress={handleSeedData}>
                <Text style={styles.seedButtonText}>Load Sample Data</Text>
              </TouchableOpacity>
            </View>
          )}
        </View>

        {/* Quick Actions */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Quick Actions</Text>
          <View style={styles.actionsGrid}>
            <TouchableOpacity style={styles.actionCard} onPress={() => router.push('/(main)/products')}>
              <Ionicons name="add-circle" size={32} color="#6366F1" />
              <Text style={styles.actionText}>Add Product</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.actionCard} onPress={() => router.push('/(main)/profile')}>
              <Ionicons name="qr-code" size={32} color="#6366F1" />
              <Text style={styles.actionText}>Shop QR</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.actionCard} onPress={() => router.push('/(main)/chats')}>
              <Ionicons name="chatbubbles" size={32} color="#6366F1" />
              <Text style={styles.actionText}>Messages</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.actionCard} onPress={() => router.push('/(main)/profile')}>
              <Ionicons name="analytics" size={32} color="#6366F1" />
              <Text style={styles.actionText}>Analytics</Text>
            </TouchableOpacity>
          </View>
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F9FAFB',
  },
  scrollView: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 16,
  },
  greeting: {
    fontSize: 14,
    color: '#6B7280',
  },
  shopName: {
    fontSize: 22,
    fontWeight: '700',
    color: '#111827',
    marginTop: 2,
  },
  notificationBtn: {
    width: 48,
    height: 48,
    backgroundColor: '#FFFFFF',
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 2,
  },
  badge: {
    position: 'absolute',
    top: 8,
    right: 8,
    backgroundColor: '#DC2626',
    width: 18,
    height: 18,
    borderRadius: 9,
    justifyContent: 'center',
    alignItems: 'center',
  },
  badgeText: {
    color: '#FFFFFF',
    fontSize: 10,
    fontWeight: '700',
  },
  statusCard: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#FFFFFF',
    marginHorizontal: 20,
    padding: 16,
    borderRadius: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 2,
  },
  statusLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  statusIndicator: {
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: '#9CA3AF',
  },
  statusIndicatorOpen: {
    backgroundColor: '#22C55E',
  },
  statusLabel: {
    fontSize: 12,
    color: '#6B7280',
  },
  statusText: {
    fontSize: 16,
    fontWeight: '700',
    color: '#111827',
  },
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    paddingHorizontal: 12,
    paddingTop: 16,
  },
  statCard: {
    width: '50%',
    padding: 8,
  },
  statCardInner: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 16,
    alignItems: 'center',
  },
  statValue: {
    fontSize: 22,
    fontWeight: '700',
    color: '#111827',
    marginTop: 8,
  },
  statLabel: {
    fontSize: 12,
    color: '#6B7280',
    marginTop: 4,
  },
  alertCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FEF2F2',
    marginHorizontal: 20,
    marginTop: 16,
    padding: 16,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#FECACA',
  },
  alertIconContainer: {
    width: 48,
    height: 48,
    backgroundColor: '#FFFFFF',
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
  },
  alertContent: {
    flex: 1,
    marginLeft: 12,
  },
  alertTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#DC2626',
  },
  alertSubtitle: {
    fontSize: 13,
    color: '#991B1B',
    marginTop: 2,
  },
  section: {
    paddingHorizontal: 20,
    paddingTop: 24,
    paddingBottom: 8,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#111827',
  },
  seeAll: {
    fontSize: 14,
    fontWeight: '600',
    color: '#6366F1',
  },
  orderCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 2,
  },
  orderTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  orderId: {
    fontSize: 14,
    fontWeight: '700',
    color: '#6366F1',
  },
  orderCustomer: {
    fontSize: 15,
    fontWeight: '600',
    color: '#111827',
    marginBottom: 8,
  },
  orderBottom: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  orderItems: {
    fontSize: 13,
    color: '#6B7280',
  },
  orderAmount: {
    fontSize: 16,
    fontWeight: '700',
    color: '#111827',
  },
  emptyState: {
    alignItems: 'center',
    paddingVertical: 40,
  },
  emptyText: {
    fontSize: 15,
    color: '#9CA3AF',
    marginTop: 12,
  },
  seedButton: {
    marginTop: 16,
    backgroundColor: '#EEF2FF',
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 12,
  },
  seedButtonText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#6366F1',
  },
  actionsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginTop: 8,
  },
  actionCard: {
    width: '25%',
    alignItems: 'center',
    paddingVertical: 16,
  },
  actionText: {
    fontSize: 11,
    color: '#6B7280',
    marginTop: 8,
    textAlign: 'center',
  },
});
