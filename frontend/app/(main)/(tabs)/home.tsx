import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  Animated,
  AppState,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useFocusEffect } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useAuthStore } from '../../../src/store/authStore';
import { vendorAPI, orderAPI, productAPI, stockVerificationAPI } from '../../../src/utils/api';
import { Analytics, Order, Product } from '../../../src/types';
import { useAlert } from '../../../src/context/AlertContext';
import { useTheme, typography, spacing, borderRadius } from '../../../src/context/ThemeContext';
import { Card, Badge } from '../../../src/components/ios';
import StockVerificationModal from '../../../src/components/StockVerificationModal';
import LowStockAlert from '../../../src/components/LowStockAlert';

interface LowStockProduct {
  product_id: string;
  name: string;
  category: string;
  current_stock: number;
  initial_stock: number;
  stock_percentage: number;
  image?: string;
  unit: string;
}

export default function HomeScreen() {
  const router = useRouter();
  const { colors, isDark } = useTheme();
  const { user } = useAuthStore();
  const { showAlert } = useAlert();
  const [refreshing, setRefreshing] = useState(false);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [pendingOrders, setPendingOrders] = useState<Order[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  
  // Stock verification state
  const [showVerificationModal, setShowVerificationModal] = useState(false);
  const [showLowStockAlert, setShowLowStockAlert] = useState(false);
  const [currentLowStockProduct, setCurrentLowStockProduct] = useState<LowStockProduct | null>(null);
  const [lowStockQueue, setLowStockQueue] = useState<LowStockProduct[]>([]);
  const [verificationStatus, setVerificationStatus] = useState<any>(null);
  const [hasCheckedVerification, setHasCheckedVerification] = useState(false);
  
  const fadeAnim = useRef(new Animated.Value(0)).current;
  const slideAnim = useRef(new Animated.Value(20)).current;

  const lowStockProducts = products.filter(p => p.stock_quantity <= 10 && p.in_stock);
  const outOfStockProducts = products.filter(p => !p.in_stock);
  const hasInventoryAlerts = lowStockProducts.length > 0 || outOfStockProducts.length > 0;

  // Check stock verification status on app focus
  const checkVerificationStatus = async () => {
    try {
      const response = await stockVerificationAPI.getStatus();
      const data = response.data;
      setVerificationStatus(data);
      
      // Show verification modal if required and not verified today
      if (data.is_verification_required && !hasCheckedVerification) {
        setShowVerificationModal(true);
        setHasCheckedVerification(true);
      }
      
      // Queue low stock alerts (products below 35%)
      if (data.low_stock_products && data.low_stock_products.length > 0) {
        const dismissed = await getLocalDismissedAlerts();
        const newAlerts = data.low_stock_products.filter(
          (p: LowStockProduct) => !dismissed.includes(p.product_id)
        );
        if (newAlerts.length > 0 && !showVerificationModal) {
          setLowStockQueue(newAlerts);
          setCurrentLowStockProduct(newAlerts[0]);
          setShowLowStockAlert(true);
        }
      }
    } catch (error) {
      console.error('Check verification status error:', error);
    }
  };
  
  // Simple local storage for dismissed alerts (session-based)
  const dismissedAlerts: string[] = [];
  const getLocalDismissedAlerts = async () => dismissedAlerts;
  const addLocalDismissedAlert = (productId: string) => dismissedAlerts.push(productId);

  const loadData = async () => {
    try {
      const [analyticsRes, ordersRes, productsRes] = await Promise.all([
        vendorAPI.getAnalytics(),
        orderAPI.getPending(),
        productAPI.getAll(),
      ]);
      setAnalytics(analyticsRes.data);
      setPendingOrders(ordersRes.data);
      setProducts(productsRes.data);
    } catch (error) {
      console.error('Load data error:', error);
    }
  };

  useFocusEffect(
    useCallback(() => {
      loadData();
      checkVerificationStatus();
      const intervalId = setInterval(() => loadData(), 30000);
      return () => clearInterval(intervalId);
    }, [])
  );

  useEffect(() => {
    const subscription = AppState.addEventListener('change', (nextAppState) => {
      if (nextAppState === 'active') {
        loadData();
        checkVerificationStatus();
      }
    });
    return () => subscription.remove();
  }, []);

  useEffect(() => {
    Animated.parallel([
      Animated.timing(fadeAnim, { toValue: 1, duration: 400, useNativeDriver: true }),
      Animated.timing(slideAnim, { toValue: 0, duration: 400, useNativeDriver: true }),
    ]).start();
  }, []);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadData();
    await checkVerificationStatus();
    setRefreshing(false);
  }, []);

  // Handle low stock alert dismissal
  const handleLowStockAlertClose = () => {
    if (currentLowStockProduct) {
      addLocalDismissedAlert(currentLowStockProduct.product_id);
    }
    // Show next alert in queue
    const remainingAlerts = lowStockQueue.slice(1);
    if (remainingAlerts.length > 0) {
      setLowStockQueue(remainingAlerts);
      setCurrentLowStockProduct(remainingAlerts[0]);
    } else {
      setShowLowStockAlert(false);
      setCurrentLowStockProduct(null);
      setLowStockQueue([]);
    }
  };

  const handleLowStockUpdate = () => {
    handleLowStockAlertClose();
    loadData();
  };

  const handleVerificationComplete = () => {
    setShowVerificationModal(false);
    loadData();
    // Check for low stock alerts after verification
    checkVerificationStatus();
  };

  const totalOrders = analytics?.total_orders || 0;
  const level = Math.floor(totalOrders / 10) + 1;
  const xpProgress = (totalOrders % 10) / 10;

  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good Morning';
    if (hour < 17) return 'Good Afternoon';
    return 'Good Evening';
  };

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background.grouped }]} edges={['top']}>
      {/* Stock Verification Modal */}
      <StockVerificationModal
        visible={showVerificationModal}
        onClose={() => setShowVerificationModal(false)}
        onComplete={handleVerificationComplete}
      />
      
      {/* Low Stock Alert */}
      <LowStockAlert
        visible={showLowStockAlert}
        product={currentLowStockProduct}
        onClose={handleLowStockAlertClose}
        onUpdate={handleLowStockUpdate}
      />
      
      <ScrollView
        style={styles.scrollView}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />
        }
      >
        <Animated.View style={{ opacity: fadeAnim, transform: [{ translateY: slideAnim }] }}>
          {/* Header */}
          <View style={styles.header}>
            <View style={styles.headerLeft}>
              <Text style={[styles.greeting, { color: colors.text.secondary }]}>{getGreeting()}</Text>
              <Text style={[styles.shopName, { color: colors.text.primary }]}>
                {user?.vendor_shop_name || 'Your Shop'}
              </Text>
            </View>
            <View style={styles.headerRight}>
              <TouchableOpacity 
                style={[styles.headerBtn, { backgroundColor: colors.success }]}
                onPress={() => router.push('/(main)/wisher-orders')}
                testID="local-hub-btn"
              >
                <Ionicons name="globe-outline" size={20} color="#FFFFFF" />
              </TouchableOpacity>
              <TouchableOpacity 
                style={[styles.headerBtn, { backgroundColor: colors.primary }]}
                onPress={() => router.push('/(main)/profile')}
                testID="profile-btn"
              >
                <Ionicons name="storefront" size={20} color="#FFFFFF" />
              </TouchableOpacity>
            </View>
          </View>

          {/* Level Card */}
          <View style={[styles.levelCard, { backgroundColor: colors.card }]}>
            <View style={styles.levelHeader}>
              <View style={[styles.levelBadge, { backgroundColor: colors.primary }]}>
                <Ionicons name="trophy" size={18} color="#FFFFFF" />
                <Text style={styles.levelNumber}>Lv.{level}</Text>
              </View>
              <View style={styles.levelInfo}>
                <Text style={[styles.levelTitle, { color: colors.text.primary }]}>Vendor Level {level}</Text>
                <Text style={[styles.levelSubtitle, { color: colors.text.secondary }]}>
                  {10 - (totalOrders % 10)} orders to next level
                </Text>
              </View>
            </View>
            <View style={styles.xpBarContainer}>
              <View style={[styles.xpBar, { backgroundColor: isDark ? colors.background.tertiary : '#E5E7EB' }]}>
                <View style={[styles.xpProgress, { width: `${xpProgress * 100}%`, backgroundColor: colors.primary }]} />
              </View>
              <Text style={[styles.xpText, { color: colors.primary }]}>{totalOrders % 10}/10</Text>
            </View>
          </View>

          {/* Inventory Alerts */}
          {hasInventoryAlerts && (
            <View style={styles.alertsSection}>
              <View style={styles.sectionHeader}>
                <View style={styles.sectionTitleRow}>
                  <Ionicons name="warning" size={18} color={colors.danger} />
                  <Text style={[styles.sectionTitle, { color: colors.text.primary }]}>Inventory Alerts</Text>
                </View>
                <TouchableOpacity onPress={() => router.push('/(main)/warehouse')}>
                  <Text style={[styles.seeAllBtn, { color: colors.primary }]}>Manage</Text>
                </TouchableOpacity>
              </View>

              {outOfStockProducts.length > 0 && (
                <TouchableOpacity 
                  style={[styles.alertCard, { backgroundColor: colors.card }]}
                  onPress={() => router.push({ pathname: '/(main)/warehouse', params: { filter: 'out_of_stock' } })}
                >
                  <View style={[styles.alertIconBg, { backgroundColor: isDark ? 'rgba(255, 69, 58, 0.2)' : '#FEE2E2' }]}>
                    <Ionicons name="close-circle" size={22} color={colors.danger} />
                  </View>
                  <View style={styles.alertContent}>
                    <Text style={[styles.alertTitle, { color: colors.danger }]}>Out of Stock</Text>
                    <Text style={[styles.alertSubtitle, { color: colors.text.secondary }]}>
                      {outOfStockProducts.length} product{outOfStockProducts.length > 1 ? 's' : ''}
                    </Text>
                  </View>
                  <Ionicons name="chevron-forward" size={20} color={colors.text.tertiary} />
                </TouchableOpacity>
              )}

              {lowStockProducts.length > 0 && (
                <TouchableOpacity 
                  style={[styles.alertCard, { backgroundColor: colors.card }]}
                  onPress={() => router.push({ pathname: '/(main)/warehouse', params: { filter: 'low_stock' } })}
                >
                  <View style={[styles.alertIconBg, { backgroundColor: isDark ? 'rgba(255, 159, 10, 0.2)' : '#FEF3C7' }]}>
                    <Ionicons name="alert-circle" size={22} color={colors.warning} />
                  </View>
                  <View style={styles.alertContent}>
                    <Text style={[styles.alertTitle, { color: colors.warning }]}>Low Stock</Text>
                    <Text style={[styles.alertSubtitle, { color: colors.text.secondary }]}>
                      {lowStockProducts.length} product{lowStockProducts.length > 1 ? 's' : ''}
                    </Text>
                  </View>
                  <Ionicons name="chevron-forward" size={20} color={colors.text.tertiary} />
                </TouchableOpacity>
              )}
            </View>
          )}

          {/* Today's Performance */}
          <TouchableOpacity 
            style={[styles.performanceCard, { backgroundColor: colors.primary }]}
            onPress={() => router.push('/(main)/performance')}
            activeOpacity={0.9}
            testID="performance-card"
          >
            <View style={styles.performanceHeader}>
              <Text style={styles.performanceLabel}>TODAY'S PERFORMANCE</Text>
              <View style={styles.performanceArrow}>
                <Ionicons name="chevron-forward" size={18} color="rgba(255,255,255,0.7)" />
              </View>
            </View>
            <View style={styles.performanceStats}>
              <View style={styles.performanceMain}>
                <Text style={styles.performanceValue}>₹{(analytics?.today.earnings || 0).toLocaleString()}</Text>
                <Text style={styles.performanceSubtext}>Earnings</Text>
              </View>
              <View style={styles.performanceDivider} />
              <View style={styles.performanceSecondary}>
                <View style={styles.performanceStatItem}>
                  <Text style={styles.performanceStatValue}>{analytics?.today.orders || 0}</Text>
                  <Text style={styles.performanceStatLabel}>Orders</Text>
                </View>
                <View style={styles.performanceStatItem}>
                  <Text style={styles.performanceStatValue}>{analytics?.products?.in_stock || 0}</Text>
                  <Text style={styles.performanceStatLabel}>In Stock</Text>
                </View>
              </View>
            </View>
          </TouchableOpacity>

          {/* Recent Orders */}
          <View style={styles.ordersSection}>
            <View style={styles.sectionHeader}>
              <Text style={[styles.sectionTitle, { color: colors.text.primary }]}>Recent Orders</Text>
              <TouchableOpacity onPress={() => router.push('/(main)/orders')}>
                <Text style={[styles.seeAllBtn, { color: colors.primary }]}>See All</Text>
              </TouchableOpacity>
            </View>

            <View style={[styles.ordersCard, { backgroundColor: colors.card }]}>
              {pendingOrders.slice(0, 3).map((order, index) => (
                <TouchableOpacity
                  key={order.order_id}
                  style={[
                    styles.orderItem,
                    index < Math.min(pendingOrders.length - 1, 2) && { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.separator }
                  ]}
                  onPress={() => router.push('/(main)/orders')}
                  testID={`order-item-${index}`}
                >
                  <View style={styles.orderLeft}>
                    <View style={[
                      styles.orderIndex, 
                      { backgroundColor: order.status === 'pending' ? (isDark ? 'rgba(255, 69, 58, 0.2)' : '#FEE2E2') : colors.background.secondary }
                    ]}>
                      <Text style={[styles.orderIndexText, { color: colors.text.primary }]}>{index + 1}</Text>
                    </View>
                    <View style={styles.orderInfo}>
                      <Text style={[styles.orderId, { color: colors.text.primary }]}>
                        #{order.order_id.slice(-6).toUpperCase()}
                      </Text>
                      <Text style={[styles.orderCustomer, { color: colors.text.secondary }]}>
                        {order.customer_name || 'Customer'}
                      </Text>
                    </View>
                  </View>
                  <View style={styles.orderRight}>
                    <Text style={[styles.orderAmount, { color: colors.text.primary }]}>₹{order.total_amount}</Text>
                    <Badge 
                      text={order.status.toUpperCase()} 
                      variant={order.status === 'pending' ? 'warning' : 'success'} 
                    />
                  </View>
                </TouchableOpacity>
              ))}

              {pendingOrders.length === 0 && (
                <View style={styles.emptyState}>
                  <View style={[styles.emptyIconBg, { backgroundColor: colors.background.secondary }]}>
                    <Ionicons name="cube-outline" size={32} color={colors.text.tertiary} />
                  </View>
                  <Text style={[styles.emptyTitle, { color: colors.text.primary }]}>No orders yet</Text>
                  <Text style={[styles.emptySubtitle, { color: colors.text.secondary }]}>
                    Orders will appear here
                  </Text>
                </View>
              )}
            </View>
          </View>

          {/* Insights Card */}
          <TouchableOpacity 
            style={[styles.insightsCard, { backgroundColor: isDark ? colors.background.secondary : '#FFFBEB', borderColor: isDark ? colors.border : '#FDE68A' }]}
            onPress={() => router.push('/(main)/performance')}
            testID="insights-card"
          >
            <View style={[styles.insightsIcon, { backgroundColor: isDark ? colors.background.tertiary : '#FEF3C7' }]}>
              <Ionicons name="bulb" size={22} color={colors.warning} />
            </View>
            <View style={styles.insightsContent}>
              <Text style={[styles.insightsTitle, { color: isDark ? colors.warning : '#92400E' }]}>Business Insights</Text>
              <Text style={[styles.insightsText, { color: colors.text.secondary }]}>
                View detailed analytics and performance
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={20} color={colors.text.tertiary} />
          </TouchableOpacity>

          <View style={{ height: 100 }} />
        </Animated.View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  scrollView: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: spacing.l,
    paddingTop: spacing.m,
    paddingBottom: spacing.l,
  },
  headerLeft: {
    flex: 1,
  },
  greeting: {
    fontSize: typography.subhead.fontSize,
    fontWeight: '500',
  },
  shopName: {
    fontSize: typography.title2.fontSize,
    fontWeight: '700',
    marginTop: 2,
  },
  headerRight: {
    flexDirection: 'row',
    gap: spacing.s,
  },
  headerBtn: {
    width: 44,
    height: 44,
    borderRadius: borderRadius.m,
    justifyContent: 'center',
    alignItems: 'center',
  },
  levelCard: {
    marginHorizontal: spacing.l,
    padding: spacing.l,
    borderRadius: borderRadius.l,
  },
  levelHeader: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  levelBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.m,
    paddingVertical: spacing.s,
    borderRadius: borderRadius.s,
    gap: 6,
  },
  levelNumber: {
    fontSize: 15,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  levelInfo: {
    flex: 1,
    marginLeft: spacing.m,
  },
  levelTitle: {
    fontSize: typography.headline.fontSize,
    fontWeight: '600',
  },
  levelSubtitle: {
    fontSize: typography.footnote.fontSize,
    marginTop: 2,
  },
  xpBarContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: spacing.m,
    gap: spacing.m,
  },
  xpBar: {
    flex: 1,
    height: 6,
    borderRadius: 3,
    overflow: 'hidden',
  },
  xpProgress: {
    height: '100%',
    borderRadius: 3,
  },
  xpText: {
    fontSize: typography.footnote.fontSize,
    fontWeight: '600',
  },
  alertsSection: {
    marginHorizontal: spacing.l,
    marginTop: spacing.l,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.m,
  },
  sectionTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.s,
  },
  sectionTitle: {
    fontSize: typography.headline.fontSize,
    fontWeight: '600',
  },
  seeAllBtn: {
    fontSize: typography.subhead.fontSize,
    fontWeight: '600',
  },
  alertCard: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: spacing.m,
    borderRadius: borderRadius.m,
    marginBottom: spacing.s,
  },
  alertIconBg: {
    width: 40,
    height: 40,
    borderRadius: borderRadius.s,
    justifyContent: 'center',
    alignItems: 'center',
  },
  alertContent: {
    flex: 1,
    marginLeft: spacing.m,
  },
  alertTitle: {
    fontSize: typography.subhead.fontSize,
    fontWeight: '600',
  },
  alertSubtitle: {
    fontSize: typography.footnote.fontSize,
    marginTop: 2,
  },
  performanceCard: {
    marginHorizontal: spacing.l,
    marginTop: spacing.l,
    padding: spacing.l,
    borderRadius: borderRadius.l,
  },
  performanceHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.m,
  },
  performanceLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: 'rgba(255,255,255,0.7)',
    letterSpacing: 1,
  },
  performanceArrow: {
    width: 28,
    height: 28,
    backgroundColor: 'rgba(255,255,255,0.15)',
    borderRadius: 14,
    justifyContent: 'center',
    alignItems: 'center',
  },
  performanceStats: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  performanceMain: {
    flex: 1,
  },
  performanceValue: {
    fontSize: 32,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  performanceSubtext: {
    fontSize: typography.subhead.fontSize,
    color: 'rgba(255,255,255,0.8)',
    marginTop: 2,
  },
  performanceDivider: {
    width: 1,
    height: 50,
    backgroundColor: 'rgba(255,255,255,0.2)',
    marginHorizontal: spacing.l,
  },
  performanceSecondary: {
    gap: spacing.m,
  },
  performanceStatItem: {
    alignItems: 'flex-end',
  },
  performanceStatValue: {
    fontSize: typography.title3.fontSize,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  performanceStatLabel: {
    fontSize: typography.caption1.fontSize,
    color: 'rgba(255,255,255,0.7)',
  },
  ordersSection: {
    marginHorizontal: spacing.l,
    marginTop: spacing.xl,
  },
  ordersCard: {
    borderRadius: borderRadius.l,
    overflow: 'hidden',
  },
  orderItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: spacing.m,
  },
  orderLeft: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  orderIndex: {
    width: 32,
    height: 32,
    borderRadius: borderRadius.s,
    justifyContent: 'center',
    alignItems: 'center',
  },
  orderIndexText: {
    fontSize: typography.subhead.fontSize,
    fontWeight: '600',
  },
  orderInfo: {
    marginLeft: spacing.m,
  },
  orderId: {
    fontSize: typography.subhead.fontSize,
    fontWeight: '600',
  },
  orderCustomer: {
    fontSize: typography.footnote.fontSize,
    marginTop: 2,
  },
  orderRight: {
    alignItems: 'flex-end',
    gap: 4,
  },
  orderAmount: {
    fontSize: typography.headline.fontSize,
    fontWeight: '600',
  },
  emptyState: {
    alignItems: 'center',
    padding: spacing.xxl,
  },
  emptyIconBg: {
    width: 64,
    height: 64,
    borderRadius: 32,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: spacing.m,
  },
  emptyTitle: {
    fontSize: typography.headline.fontSize,
    fontWeight: '600',
  },
  emptySubtitle: {
    fontSize: typography.subhead.fontSize,
    marginTop: 4,
  },
  insightsCard: {
    flexDirection: 'row',
    alignItems: 'center',
    marginHorizontal: spacing.l,
    marginTop: spacing.xl,
    padding: spacing.m,
    borderRadius: borderRadius.m,
    borderWidth: 1,
  },
  insightsIcon: {
    width: 44,
    height: 44,
    borderRadius: borderRadius.m,
    justifyContent: 'center',
    alignItems: 'center',
  },
  insightsContent: {
    flex: 1,
    marginLeft: spacing.m,
  },
  insightsTitle: {
    fontSize: typography.subhead.fontSize,
    fontWeight: '600',
  },
  insightsText: {
    fontSize: typography.footnote.fontSize,
    marginTop: 2,
  },
});
