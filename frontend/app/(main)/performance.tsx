import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  Animated,
  Dimensions,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { vendorAPI, productAPI } from '../../src/utils/api';
import { Analytics, Product } from '../../src/types';

const { width } = Dimensions.get('window');

type TimeRange = 'today' | 'week' | 'month' | 'year';

export default function PerformanceScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedRange, setSelectedRange] = useState<TimeRange>('today');
  const fadeAnim = useRef(new Animated.Value(0)).current;
  const slideAnim = useRef(new Animated.Value(30)).current;

  const loadData = async () => {
    try {
      const [analyticsRes, productsRes] = await Promise.all([
        vendorAPI.getAnalytics(),
        productAPI.getAll(),
      ]);
      setAnalytics(analyticsRes.data);
      setProducts(productsRes.data);
    } catch (error) {
      console.error('Load performance data error:', error);
    }
  };

  useEffect(() => {
    loadData();
    Animated.parallel([
      Animated.timing(fadeAnim, {
        toValue: 1,
        duration: 500,
        useNativeDriver: true,
      }),
      Animated.timing(slideAnim, {
        toValue: 0,
        duration: 500,
        useNativeDriver: true,
      }),
    ]).start();
  }, []);

  // Back button handling - removed, handled in _layout.tsx

  const onRefresh = async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  };

  // Get data based on selected range
  const getRangeData = () => {
    switch (selectedRange) {
      case 'today':
        return { earnings: analytics?.today.earnings || 0, orders: analytics?.today.orders || 0 };
      case 'week':
        return { earnings: analytics?.week.earnings || 0, orders: analytics?.week.orders || 0 };
      case 'month':
        return { earnings: analytics?.month.earnings || 0, orders: analytics?.month.orders || 0 };
      case 'year':
        return { earnings: analytics?.total_earnings || 0, orders: analytics?.total_orders || 0 };
      default:
        return { earnings: 0, orders: 0 };
    }
  };

  const rangeData = getRangeData();
  const avgOrderValue = rangeData.orders > 0 ? Math.round(rangeData.earnings / rangeData.orders) : 0;

  // Low stock products
  const lowStockProducts = products.filter(p => p.stock_quantity <= 10 && p.in_stock);
  const outOfStockProducts = products.filter(p => !p.in_stock);

  // Simulated chart data for visualization
  const chartData = [40, 65, 45, 80, 55, 90, 75];
  const maxChartValue = Math.max(...chartData);

  const timeRanges: { key: TimeRange; label: string }[] = [
    { key: 'today', label: 'Today' },
    { key: 'week', label: 'Week' },
    { key: 'month', label: 'Month' },
    { key: 'year', label: 'Year' },
  ];

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.backBtn} onPress={() => router.push('/(main)/home')}>
          <Ionicons name="arrow-back" size={24} color="#374151" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Performance</Text>
        <TouchableOpacity style={styles.shareBtn}>
          <Ionicons name="share-outline" size={22} color="#6366F1" />
        </TouchableOpacity>
      </View>

      <ScrollView
        style={styles.scrollView}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={['#6366F1']} />
        }
      >
        <Animated.View style={{ opacity: fadeAnim, transform: [{ translateY: slideAnim }] }}>
          {/* Time Range Selector */}
          <View style={styles.rangeContainer}>
            <View style={styles.rangeSelector}>
              {timeRanges.map((range) => (
                <TouchableOpacity
                  key={range.key}
                  style={[
                    styles.rangeBtn,
                    selectedRange === range.key && styles.rangeBtnActive,
                  ]}
                  onPress={() => setSelectedRange(range.key)}
                >
                  <Text
                    style={[
                      styles.rangeBtnText,
                      selectedRange === range.key && styles.rangeBtnTextActive,
                    ]}
                  >
                    {range.label}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>

          {/* Main Stats Card */}
          <View style={styles.mainStatsCard}>
            <View style={styles.mainStatRow}>
              <View style={styles.mainStat}>
                <Text style={styles.mainStatLabel}>Total Earnings</Text>
                <Text style={styles.mainStatValue}>₹{rangeData.earnings.toLocaleString()}</Text>
              </View>
              <View style={[styles.mainStat, styles.mainStatBorder]}>
                <Text style={styles.mainStatLabel}>Total Orders</Text>
                <Text style={styles.mainStatValue}>{rangeData.orders}</Text>
              </View>
            </View>
            <View style={styles.mainStatRow}>
              <View style={styles.mainStat}>
                <Text style={styles.mainStatLabel}>Avg. Order Value</Text>
                <Text style={styles.mainStatValueSmall}>₹{avgOrderValue}</Text>
              </View>
              <View style={[styles.mainStat, styles.mainStatBorder]}>
                <Text style={styles.mainStatLabel}>Rating</Text>
                <View style={styles.ratingRow}>
                  <Ionicons name="star" size={18} color="#F59E0B" />
                  <Text style={styles.mainStatValueSmall}>{analytics?.rating?.toFixed(1) || '5.0'}</Text>
                </View>
              </View>
            </View>
          </View>

          {/* Chart Placeholder */}
          <View style={styles.chartCard}>
            <Text style={styles.chartTitle}>Earnings Trend</Text>
            <View style={styles.chartContainer}>
              {chartData.map((value, index) => (
                <View key={index} style={styles.chartBarContainer}>
                  <View
                    style={[
                      styles.chartBar,
                      { height: (value / maxChartValue) * 100 },
                      index === chartData.length - 1 && styles.chartBarActive,
                    ]}
                  />
                  <Text style={styles.chartLabel}>
                    {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][index]}
                  </Text>
                </View>
              ))}
            </View>
          </View>

          {/* Inventory Status */}
          <View style={styles.inventoryCard}>
            <View style={styles.inventoryHeader}>
              <Text style={styles.inventoryTitle}>Inventory Status</Text>
              <TouchableOpacity onPress={() => router.push('/(main)/products')}>
                <Text style={styles.manageBtn}>Manage →</Text>
              </TouchableOpacity>
            </View>

            <View style={styles.inventoryStats}>
              <View style={styles.inventoryStat}>
                <View style={[styles.inventoryIconBg, { backgroundColor: '#DCFCE7' }]}>
                  <Ionicons name="checkmark-circle" size={22} color="#22C55E" />
                </View>
                <Text style={styles.inventoryStatValue}>{analytics?.products?.in_stock || 0}</Text>
                <Text style={styles.inventoryStatLabel}>In Stock</Text>
              </View>
              <View style={styles.inventoryStat}>
                <View style={[styles.inventoryIconBg, { backgroundColor: '#FEF3C7' }]}>
                  <Ionicons name="alert-circle" size={22} color="#F59E0B" />
                </View>
                <Text style={styles.inventoryStatValue}>{lowStockProducts.length}</Text>
                <Text style={styles.inventoryStatLabel}>Low Stock</Text>
              </View>
              <View style={styles.inventoryStat}>
                <View style={[styles.inventoryIconBg, { backgroundColor: '#FEE2E2' }]}>
                  <Ionicons name="close-circle" size={22} color="#EF4444" />
                </View>
                <Text style={styles.inventoryStatValue}>{outOfStockProducts.length}</Text>
                <Text style={styles.inventoryStatLabel}>Out of Stock</Text>
              </View>
            </View>

            {/* Low Stock Alert */}
            {lowStockProducts.length > 0 && (
              <View style={styles.lowStockAlert}>
                <View style={styles.lowStockHeader}>
                  <Ionicons name="warning" size={18} color="#D97706" />
                  <Text style={styles.lowStockTitle}>Low Stock Items</Text>
                </View>
                {lowStockProducts.slice(0, 3).map((product) => (
                  <View key={product.product_id} style={styles.lowStockItem}>
                    <View style={styles.lowStockInfo}>
                      <Text style={styles.lowStockName} numberOfLines={1}>{product.name}</Text>
                      <Text style={styles.lowStockQty}>{product.stock_quantity} left</Text>
                    </View>
                    <TouchableOpacity
                      style={styles.restockBtn}
                      onPress={() => router.push(`/(main)/products/${product.product_id}`)}
                    >
                      <Text style={styles.restockBtnText}>Restock</Text>
                    </TouchableOpacity>
                  </View>
                ))}
                {lowStockProducts.length > 3 && (
                  <TouchableOpacity 
                    style={styles.viewAllBtn}
                    onPress={() => router.push('/(main)/warehouse')}
                  >
                    <Text style={styles.viewAllText}>View all {lowStockProducts.length} items</Text>
                  </TouchableOpacity>
                )}
              </View>
            )}

            {/* Out of Stock Alert */}
            {outOfStockProducts.length > 0 && (
              <View style={styles.outOfStockAlert}>
                <View style={styles.lowStockHeader}>
                  <Ionicons name="alert" size={18} color="#DC2626" />
                  <Text style={styles.outOfStockTitle}>Out of Stock</Text>
                </View>
                {outOfStockProducts.slice(0, 2).map((product) => (
                  <View key={product.product_id} style={styles.lowStockItem}>
                    <Text style={styles.lowStockName} numberOfLines={1}>{product.name}</Text>
                    <TouchableOpacity
                      style={styles.addStockBtn}
                      onPress={() => router.push(`/(main)/products/${product.product_id}`)}
                    >
                      <Text style={styles.addStockBtnText}>Add Stock</Text>
                    </TouchableOpacity>
                  </View>
                ))}
              </View>
            )}
          </View>

          {/* Performance Metrics */}
          <View style={styles.metricsCard}>
            <Text style={styles.metricsTitle}>Key Metrics</Text>
            
            <View style={styles.metricRow}>
              <View style={styles.metricInfo}>
                <Ionicons name="time-outline" size={20} color="#6366F1" />
                <Text style={styles.metricLabel}>Avg. Fulfillment Time</Text>
              </View>
              <Text style={styles.metricValue}>12 mins</Text>
            </View>

            <View style={styles.metricRow}>
              <View style={styles.metricInfo}>
                <Ionicons name="repeat-outline" size={20} color="#22C55E" />
                <Text style={styles.metricLabel}>Repeat Customers</Text>
              </View>
              <Text style={styles.metricValue}>34%</Text>
            </View>

            <View style={styles.metricRow}>
              <View style={styles.metricInfo}>
                <Ionicons name="close-circle-outline" size={20} color="#EF4444" />
                <Text style={styles.metricLabel}>Cancellation Rate</Text>
              </View>
              <Text style={styles.metricValue}>2%</Text>
            </View>

            <View style={[styles.metricRow, { borderBottomWidth: 0 }]}>
              <View style={styles.metricInfo}>
                <Ionicons name="happy-outline" size={20} color="#F59E0B" />
                <Text style={styles.metricLabel}>Customer Satisfaction</Text>
              </View>
              <Text style={styles.metricValue}>96%</Text>
            </View>
          </View>

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
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  backBtn: {
    width: 40,
    height: 40,
    justifyContent: 'center',
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#111827',
  },
  shareBtn: {
    width: 40,
    height: 40,
    backgroundColor: '#EEF2FF',
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
  },
  scrollView: {
    flex: 1,
  },
  // Time Range
  rangeContainer: {
    padding: 16,
  },
  rangeSelector: {
    flexDirection: 'row',
    backgroundColor: '#FFFFFF',
    borderRadius: 14,
    padding: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 8,
    elevation: 2,
  },
  rangeBtn: {
    flex: 1,
    paddingVertical: 12,
    alignItems: 'center',
    borderRadius: 10,
  },
  rangeBtnActive: {
    backgroundColor: '#6366F1',
  },
  rangeBtnText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#6B7280',
  },
  rangeBtnTextActive: {
    color: '#FFFFFF',
  },
  // Main Stats
  mainStatsCard: {
    backgroundColor: '#FFFFFF',
    marginHorizontal: 16,
    borderRadius: 20,
    padding: 20,
    shadowColor: '#6366F1',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 12,
    elevation: 4,
  },
  mainStatRow: {
    flexDirection: 'row',
  },
  mainStat: {
    flex: 1,
    paddingVertical: 12,
  },
  mainStatBorder: {
    borderLeftWidth: 1,
    borderLeftColor: '#E5E7EB',
    paddingLeft: 20,
  },
  mainStatLabel: {
    fontSize: 12,
    color: '#6B7280',
    marginBottom: 6,
  },
  mainStatValue: {
    fontSize: 28,
    fontWeight: '800',
    color: '#111827',
  },
  mainStatValueSmall: {
    fontSize: 22,
    fontWeight: '700',
    color: '#111827',
  },
  ratingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  // Chart
  chartCard: {
    backgroundColor: '#FFFFFF',
    marginHorizontal: 16,
    marginTop: 16,
    borderRadius: 20,
    padding: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 8,
    elevation: 2,
  },
  chartTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#111827',
    marginBottom: 20,
  },
  chartContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-end',
    height: 120,
  },
  chartBarContainer: {
    alignItems: 'center',
    flex: 1,
  },
  chartBar: {
    width: 28,
    backgroundColor: '#E5E7EB',
    borderRadius: 6,
    marginBottom: 8,
  },
  chartBarActive: {
    backgroundColor: '#6366F1',
  },
  chartLabel: {
    fontSize: 11,
    color: '#9CA3AF',
  },
  // Inventory
  inventoryCard: {
    backgroundColor: '#FFFFFF',
    marginHorizontal: 16,
    marginTop: 16,
    borderRadius: 20,
    padding: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 8,
    elevation: 2,
  },
  inventoryHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  inventoryTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#111827',
  },
  manageBtn: {
    fontSize: 14,
    fontWeight: '600',
    color: '#6366F1',
  },
  inventoryStats: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    paddingBottom: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#F3F4F6',
  },
  inventoryStat: {
    alignItems: 'center',
  },
  inventoryIconBg: {
    width: 48,
    height: 48,
    borderRadius: 14,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 8,
  },
  inventoryStatValue: {
    fontSize: 20,
    fontWeight: '700',
    color: '#111827',
  },
  inventoryStatLabel: {
    fontSize: 12,
    color: '#6B7280',
    marginTop: 2,
  },
  // Low Stock Alert
  lowStockAlert: {
    backgroundColor: '#FFFBEB',
    borderRadius: 14,
    padding: 14,
    marginTop: 16,
    borderWidth: 1,
    borderColor: '#FDE68A',
  },
  lowStockHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
  },
  lowStockTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#D97706',
  },
  lowStockItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#FDE68A',
  },
  lowStockInfo: {
    flex: 1,
  },
  lowStockName: {
    fontSize: 14,
    color: '#374151',
    flex: 1,
  },
  lowStockQty: {
    fontSize: 12,
    color: '#D97706',
    marginTop: 2,
  },
  restockBtn: {
    backgroundColor: '#FEF3C7',
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
  },
  restockBtnText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#D97706',
  },
  viewAllBtn: {
    alignItems: 'center',
    paddingTop: 12,
  },
  viewAllText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#D97706',
  },
  // Out of Stock Alert
  outOfStockAlert: {
    backgroundColor: '#FEF2F2',
    borderRadius: 14,
    padding: 14,
    marginTop: 12,
    borderWidth: 1,
    borderColor: '#FECACA',
  },
  outOfStockTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#DC2626',
  },
  addStockBtn: {
    backgroundColor: '#FEE2E2',
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
  },
  addStockBtnText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#DC2626',
  },
  // Metrics
  metricsCard: {
    backgroundColor: '#FFFFFF',
    marginHorizontal: 16,
    marginTop: 16,
    borderRadius: 20,
    padding: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 8,
    elevation: 2,
  },
  metricsTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#111827',
    marginBottom: 16,
  },
  metricRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#F3F4F6',
  },
  metricInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  metricLabel: {
    fontSize: 14,
    color: '#374151',
  },
  metricValue: {
    fontSize: 16,
    fontWeight: '700',
    color: '#111827',
  },
});
