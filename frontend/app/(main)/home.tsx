import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  Alert,
  Animated,
  Dimensions,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useAuthStore } from '../../src/store/authStore';
import { vendorAPI, orderAPI } from '../../src/utils/api';
import { Analytics, Order } from '../../src/types';

const { width } = Dimensions.get('window');

export default function HomeScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { user } = useAuthStore();
  const [refreshing, setRefreshing] = useState(false);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [pendingOrders, setPendingOrders] = useState<Order[]>([]);
  
  // Animations
  const fadeAnim = useRef(new Animated.Value(0)).current;
  const slideAnim = useRef(new Animated.Value(30)).current;

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
    
    // Entrance animation
    Animated.parallel([
      Animated.timing(fadeAnim, {
        toValue: 1,
        duration: 600,
        useNativeDriver: true,
      }),
      Animated.timing(slideAnim, {
        toValue: 0,
        duration: 600,
        useNativeDriver: true,
      }),
    ]).start();
  }, []);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  }, []);

  const handleSeedData = async () => {
    try {
      await vendorAPI.seedData();
      Alert.alert('Success! 🎉', 'Sample data created!');
      loadData();
    } catch (error) {
      Alert.alert('Error', 'Failed to seed data');
    }
  };

  // Calculate level based on total orders
  const totalOrders = analytics?.total_orders || 0;
  const level = Math.floor(totalOrders / 10) + 1;
  const xpProgress = (totalOrders % 10) / 10;
  const xpToNext = 10 - (totalOrders % 10);

  // Get greeting based on time
  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good Morning';
    if (hour < 17) return 'Good Afternoon';
    return 'Good Evening';
  };

  // Get level badge color
  const getLevelColor = () => {
    if (level >= 10) return '#F59E0B'; // Gold
    if (level >= 5) return '#8B5CF6'; // Purple
    return '#6366F1'; // Indigo
  };

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <ScrollView
        style={styles.scrollView}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={['#6366F1']} />
        }
      >
        <Animated.View style={{ opacity: fadeAnim, transform: [{ translateY: slideAnim }] }}>
          {/* Header */}
          <View style={styles.header}>
            <View style={styles.headerLeft}>
              <Text style={styles.greeting}>{getGreeting()} 👋</Text>
              <Text style={styles.shopName}>{user?.vendor_shop_name || 'Your Shop'}</Text>
            </View>
            <TouchableOpacity 
              style={styles.profileBtn}
              onPress={() => router.push('/(main)/profile')}
            >
              <View style={styles.profileAvatar}>
                <Ionicons name="storefront" size={20} color="#FFFFFF" />
              </View>
            </TouchableOpacity>
          </View>

          {/* Level Card - Gamified */}
          <View style={styles.levelCard}>
            <View style={styles.levelHeader}>
              <View style={[styles.levelBadge, { backgroundColor: getLevelColor() }]}>
                <Ionicons name="trophy" size={20} color="#FFFFFF" />
                <Text style={styles.levelNumber}>Lv.{level}</Text>
              </View>
              <View style={styles.levelInfo}>
                <Text style={styles.levelTitle}>Vendor Level {level}</Text>
                <Text style={styles.levelSubtitle}>{xpToNext} orders to next level</Text>
              </View>
              <View style={styles.levelStars}>
                {[...Array(Math.min(level, 5))].map((_, i) => (
                  <Ionicons key={i} name="star" size={14} color="#F59E0B" />
                ))}
              </View>
            </View>
            <View style={styles.xpBarContainer}>
              <View style={styles.xpBar}>
                <View style={[styles.xpProgress, { width: `${xpProgress * 100}%` }]} />
              </View>
              <Text style={styles.xpText}>{totalOrders % 10}/10 XP</Text>
            </View>
          </View>

          {/* Today's Performance - Clickable */}
          <TouchableOpacity 
            style={styles.heroSection}
            onPress={() => router.push('/(main)/performance')}
            activeOpacity={0.9}
          >
            <View style={styles.heroHeader}>
              <Text style={styles.heroLabel}>TODAY'S PERFORMANCE</Text>
              <View style={styles.heroArrow}>
                <Ionicons name="chevron-forward" size={20} color="rgba(255,255,255,0.7)" />
              </View>
            </View>
            <View style={styles.heroStats}>
              <View style={styles.heroStatMain}>
                <Text style={styles.heroValue}>₹{(analytics?.today.earnings || 0).toLocaleString()}</Text>
                <Text style={styles.heroSubtext}>Earnings</Text>
              </View>
              <View style={styles.heroDivider} />
              <View style={styles.heroStatSecondary}>
                <View style={styles.heroStatItem}>
                  <Text style={styles.heroStatValue}>{analytics?.today.orders || 0}</Text>
                  <Text style={styles.heroStatLabel}>Orders</Text>
                </View>
                <View style={styles.heroStatItem}>
                  <Text style={styles.heroStatValue}>{analytics?.products?.in_stock || 0}</Text>
                  <Text style={styles.heroStatLabel}>In Stock</Text>
                </View>
              </View>
            </View>
            <View style={styles.heroFooter}>
              <Ionicons name="analytics" size={16} color="rgba(255,255,255,0.6)" />
              <Text style={styles.heroFooterText}>Tap to see detailed analytics</Text>
            </View>
          </TouchableOpacity>

          {/* Recent Orders */}
          <View style={styles.ordersSection}>
            <View style={styles.sectionHeader}>
              <Text style={styles.sectionTitle}>Recent Orders</Text>
              <TouchableOpacity onPress={() => router.push('/(main)/orders')}>
                <Text style={styles.seeAllBtn}>See All →</Text>
              </TouchableOpacity>
            </View>

            {pendingOrders.slice(0, 3).map((order, index) => (
              <TouchableOpacity
                key={order.order_id}
                style={styles.orderCard}
                onPress={() => router.push('/(main)/orders')}
                activeOpacity={0.7}
              >
                <View style={styles.orderLeft}>
                  <View style={[styles.orderIndex, order.status === 'pending' && styles.orderIndexPending]}>
                    <Text style={styles.orderIndexText}>{index + 1}</Text>
                  </View>
                  <View style={styles.orderInfo}>
                    <Text style={styles.orderId}>#{order.order_id.slice(-6).toUpperCase()}</Text>
                    <Text style={styles.orderCustomer}>{order.customer_name || 'Customer'}</Text>
                  </View>
                </View>
                <View style={styles.orderRight}>
                  <Text style={styles.orderAmount}>₹{order.total_amount}</Text>
                  <View style={[
                    styles.orderStatus,
                    order.status === 'pending' ? styles.orderStatusPending : styles.orderStatusActive
                  ]}>
                    <Text style={[
                      styles.orderStatusText,
                      order.status === 'pending' ? styles.orderStatusTextPending : styles.orderStatusTextActive
                    ]}>
                      {order.status.toUpperCase()}
                    </Text>
                  </View>
                </View>
              </TouchableOpacity>
            ))}

            {pendingOrders.length === 0 && (
              <View style={styles.emptyState}>
                <View style={styles.emptyIconBg}>
                  <Ionicons name="cube-outline" size={40} color="#D1D5DB" />
                </View>
                <Text style={styles.emptyTitle}>No orders yet</Text>
                <Text style={styles.emptySubtitle}>Orders will appear here when customers place them</Text>
                <TouchableOpacity style={styles.seedBtn} onPress={handleSeedData}>
                  <Ionicons name="sparkles" size={18} color="#6366F1" />
                  <Text style={styles.seedBtnText}>Load Demo Data</Text>
                </TouchableOpacity>
              </View>
            )}
          </View>

          {/* Insights Card */}
          <TouchableOpacity 
            style={styles.insightsCard}
            onPress={() => router.push('/(main)/performance')}
          >
            <View style={styles.insightsIcon}>
              <Ionicons name="bulb" size={24} color="#F59E0B" />
            </View>
            <View style={styles.insightsContent}>
              <Text style={styles.insightsTitle}>Business Insights</Text>
              <Text style={styles.insightsText}>
                {analytics?.products?.out_of_stock || 0} products are out of stock. 
                Keep inventory updated for better sales!
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={20} color="#9CA3AF" />
          </TouchableOpacity>

          <View style={{ height: 100 }} />
        </Animated.View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F8FAFC',
  },
  scrollView: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingTop: 12,
    paddingBottom: 16,
  },
  headerLeft: {
    flex: 1,
  },
  greeting: {
    fontSize: 14,
    color: '#6B7280',
    fontWeight: '500',
  },
  shopName: {
    fontSize: 24,
    fontWeight: '800',
    color: '#111827',
    marginTop: 2,
  },
  profileBtn: {
    marginLeft: 12,
  },
  profileAvatar: {
    width: 48,
    height: 48,
    backgroundColor: '#6366F1',
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
  },
  // Level Card
  levelCard: {
    backgroundColor: '#FFFFFF',
    marginHorizontal: 16,
    padding: 16,
    borderRadius: 20,
    shadowColor: '#6366F1',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 12,
    elevation: 4,
  },
  levelHeader: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  levelBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 12,
    gap: 6,
  },
  levelNumber: {
    fontSize: 16,
    fontWeight: '800',
    color: '#FFFFFF',
  },
  levelInfo: {
    flex: 1,
    marginLeft: 14,
  },
  levelTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#111827',
  },
  levelSubtitle: {
    fontSize: 12,
    color: '#6B7280',
    marginTop: 2,
  },
  levelStars: {
    flexDirection: 'row',
    gap: 2,
  },
  xpBarContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 14,
    gap: 12,
  },
  xpBar: {
    flex: 1,
    height: 8,
    backgroundColor: '#E5E7EB',
    borderRadius: 4,
    overflow: 'hidden',
  },
  xpProgress: {
    height: '100%',
    backgroundColor: '#6366F1',
    borderRadius: 4,
  },
  xpText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#6366F1',
  },
  // Hero Section - Clickable
  heroSection: {
    backgroundColor: '#6366F1',
    marginHorizontal: 16,
    marginTop: 16,
    padding: 20,
    borderRadius: 20,
  },
  heroHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  heroLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: 'rgba(255,255,255,0.7)',
    letterSpacing: 1,
  },
  heroArrow: {
    width: 28,
    height: 28,
    backgroundColor: 'rgba(255,255,255,0.15)',
    borderRadius: 14,
    justifyContent: 'center',
    alignItems: 'center',
  },
  heroStats: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  heroStatMain: {
    flex: 1,
  },
  heroValue: {
    fontSize: 36,
    fontWeight: '800',
    color: '#FFFFFF',
  },
  heroSubtext: {
    fontSize: 14,
    color: 'rgba(255,255,255,0.8)',
    marginTop: 2,
  },
  heroDivider: {
    width: 1,
    height: 50,
    backgroundColor: 'rgba(255,255,255,0.2)',
    marginHorizontal: 20,
  },
  heroStatSecondary: {
    gap: 16,
  },
  heroStatItem: {
    alignItems: 'flex-end',
  },
  heroStatValue: {
    fontSize: 20,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  heroStatLabel: {
    fontSize: 12,
    color: 'rgba(255,255,255,0.7)',
  },
  heroFooter: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 16,
    paddingTop: 14,
    borderTopWidth: 1,
    borderTopColor: 'rgba(255,255,255,0.15)',
    gap: 6,
  },
  heroFooterText: {
    fontSize: 12,
    color: 'rgba(255,255,255,0.6)',
  },
  // Orders Section
  ordersSection: {
    paddingHorizontal: 16,
    marginTop: 24,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#111827',
    marginBottom: 14,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 14,
  },
  seeAllBtn: {
    fontSize: 14,
    fontWeight: '600',
    color: '#6366F1',
  },
  orderCard: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#FFFFFF',
    padding: 14,
    borderRadius: 14,
    marginBottom: 10,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 1,
  },
  orderLeft: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  orderIndex: {
    width: 32,
    height: 32,
    backgroundColor: '#E5E7EB',
    borderRadius: 10,
    justifyContent: 'center',
    alignItems: 'center',
  },
  orderIndexPending: {
    backgroundColor: '#FEE2E2',
  },
  orderIndexText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#374151',
  },
  orderInfo: {
    marginLeft: 12,
  },
  orderId: {
    fontSize: 14,
    fontWeight: '700',
    color: '#111827',
  },
  orderCustomer: {
    fontSize: 12,
    color: '#6B7280',
    marginTop: 2,
  },
  orderRight: {
    alignItems: 'flex-end',
  },
  orderAmount: {
    fontSize: 16,
    fontWeight: '700',
    color: '#111827',
  },
  orderStatus: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    marginTop: 4,
  },
  orderStatusPending: {
    backgroundColor: '#FEF3C7',
  },
  orderStatusActive: {
    backgroundColor: '#DCFCE7',
  },
  orderStatusText: {
    fontSize: 10,
    fontWeight: '700',
  },
  orderStatusTextPending: {
    color: '#D97706',
  },
  orderStatusTextActive: {
    color: '#22C55E',
  },
  // Empty State
  emptyState: {
    alignItems: 'center',
    paddingVertical: 32,
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
  },
  emptyIconBg: {
    width: 72,
    height: 72,
    backgroundColor: '#F3F4F6',
    borderRadius: 36,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
  },
  emptyTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#374151',
  },
  emptySubtitle: {
    fontSize: 13,
    color: '#9CA3AF',
    marginTop: 4,
    textAlign: 'center',
    paddingHorizontal: 40,
  },
  seedBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#EEF2FF',
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 12,
    marginTop: 20,
    gap: 8,
  },
  seedBtnText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#6366F1',
  },
  // Insights Card
  insightsCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFBEB',
    marginHorizontal: 16,
    marginTop: 24,
    padding: 16,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#FDE68A',
  },
  insightsIcon: {
    width: 48,
    height: 48,
    backgroundColor: '#FEF3C7',
    borderRadius: 14,
    justifyContent: 'center',
    alignItems: 'center',
  },
  insightsContent: {
    flex: 1,
    marginLeft: 14,
  },
  insightsTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#92400E',
  },
  insightsText: {
    fontSize: 12,
    color: '#78350F',
    marginTop: 4,
    lineHeight: 18,
  },
  // Claymorphism Exit Toast
  exitToastContainer: {
    position: 'absolute',
    bottom: 100,
    left: 20,
    right: 20,
    alignItems: 'center',
  },
  exitToast: {
    width: '100%',
    backgroundColor: '#FFFFFF',
    borderRadius: 24,
    padding: 4,
    // Claymorphism shadows
    shadowColor: '#6366F1',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.25,
    shadowRadius: 24,
    elevation: 12,
    // Inner glow effect
    borderWidth: 2,
    borderColor: 'rgba(99, 102, 241, 0.1)',
  },
  exitToastInner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'linear-gradient(145deg, #FFFFFF 0%, #F8FAFC 100%)',
    borderRadius: 20,
    padding: 16,
    // Claymorphism inner styling
    shadowColor: '#000',
    shadowOffset: { width: 2, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
  },
  exitToastIcon: {
    width: 56,
    height: 56,
    backgroundColor: '#EEF2FF',
    borderRadius: 18,
    justifyContent: 'center',
    alignItems: 'center',
    // Claymorphism bulge effect
    shadowColor: '#6366F1',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
    elevation: 4,
  },
  exitToastContent: {
    flex: 1,
    marginLeft: 14,
  },
  exitToastTitle: {
    fontSize: 17,
    fontWeight: '700',
    color: '#111827',
  },
  exitToastText: {
    fontSize: 14,
    color: '#6B7280',
    marginTop: 2,
  },
  exitToastBadge: {
    width: 36,
    height: 36,
    backgroundColor: '#6366F1',
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
    // Soft shadow for badge
    shadowColor: '#6366F1',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.4,
    shadowRadius: 8,
    elevation: 4,
  },
  exitToastProgress: {
    height: 4,
    backgroundColor: '#E5E7EB',
    borderRadius: 2,
    marginTop: 4,
    marginHorizontal: 12,
    marginBottom: 8,
    overflow: 'hidden',
  },
  exitToastProgressBar: {
    width: '100%',
    height: '100%',
    backgroundColor: '#6366F1',
    borderRadius: 2,
  },
});
