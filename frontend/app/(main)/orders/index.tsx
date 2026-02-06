import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  Animated,
  Dimensions,
  Alert,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { orderAPI, productAPI } from '../../../src/utils/api';
import { Order, Product } from '../../../src/types';
import { format } from 'date-fns';

const { width } = Dimensions.get('window');

type TabType = 'new' | 'active' | 'completed';

export default function OrdersScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [allOrders, setAllOrders] = useState<Order[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState<TabType>('new');
  const slideAnim = useRef(new Animated.Value(0)).current;
  const pulseAnim = useRef(new Animated.Value(1)).current;

  // Filter orders by tab
  const getFilteredOrders = () => {
    switch (activeTab) {
      case 'new':
        return allOrders.filter(o => o.status === 'pending');
      case 'active':
        return allOrders.filter(o => ['accepted', 'confirmed', 'preparing', 'ready', 'picked_up'].includes(o.status));
      case 'completed':
        return allOrders.filter(o => ['delivered', 'cancelled', 'rejected'].includes(o.status));
      default:
        return allOrders;
    }
  };

  const filteredOrders = getFilteredOrders();
  const newOrdersCount = allOrders.filter(o => o.status === 'pending').length;
  const activeOrdersCount = allOrders.filter(o => ['accepted', 'confirmed', 'preparing', 'ready', 'picked_up'].includes(o.status)).length;
  const completedOrdersCount = allOrders.filter(o => ['delivered', 'cancelled', 'rejected'].includes(o.status)).length;

  // Get low stock products
  const lowStockProducts = products.filter(p => p.stock_quantity <= 10 && p.in_stock);
  const outOfStockProducts = products.filter(p => !p.in_stock);

  const loadOrders = async () => {
    try {
      const [ordersRes, productsRes] = await Promise.all([
        orderAPI.getAll(),
        productAPI.getAll(),
      ]);
      setAllOrders(ordersRes.data);
      setProducts(productsRes.data);
    } catch (error) {
      console.error('Load orders error:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadOrders();
    
    // Pulse animation for new orders badge
    Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, {
          toValue: 1.2,
          duration: 600,
          useNativeDriver: true,
        }),
        Animated.timing(pulseAnim, {
          toValue: 1,
          duration: 600,
          useNativeDriver: true,
        }),
      ])
    ).start();
  }, []);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadOrders();
    setRefreshing(false);
  }, []);

  const handleTabChange = (tab: TabType) => {
    const tabIndex = tab === 'new' ? 0 : tab === 'active' ? 1 : 2;
    Animated.spring(slideAnim, {
      toValue: tabIndex,
      useNativeDriver: true,
    }).start();
    setActiveTab(tab);
  };

  const handleAcceptOrder = async (order: Order) => {
    try {
      await orderAPI.accept(order.order_id);
      showClaymorphismAlert('success', 'Order Accepted! 🎉', 'Start preparing the order');
      loadOrders();
    } catch (error) {
      showClaymorphismAlert('error', 'Oops!', 'Failed to accept order');
    }
  };

  // Claymorphism Alert State
  const [alertVisible, setAlertVisible] = useState(false);
  const [alertType, setAlertType] = useState<'success' | 'error' | 'warning'>('success');
  const [alertTitle, setAlertTitle] = useState('');
  const [alertMessage, setAlertMessage] = useState('');
  const alertAnim = useRef(new Animated.Value(0)).current;
  const alertScale = useRef(new Animated.Value(0.8)).current;

  const showClaymorphismAlert = (type: 'success' | 'error' | 'warning', title: string, message: string) => {
    setAlertType(type);
    setAlertTitle(title);
    setAlertMessage(message);
    setAlertVisible(true);
    
    Animated.parallel([
      Animated.spring(alertAnim, {
        toValue: 1,
        friction: 8,
        tension: 40,
        useNativeDriver: true,
      }),
      Animated.spring(alertScale, {
        toValue: 1,
        friction: 8,
        tension: 40,
        useNativeDriver: true,
      }),
    ]).start();

    setTimeout(() => {
      hideClaymorphismAlert();
    }, 3000);
  };

  const hideClaymorphismAlert = () => {
    Animated.parallel([
      Animated.timing(alertAnim, {
        toValue: 0,
        duration: 200,
        useNativeDriver: true,
      }),
      Animated.timing(alertScale, {
        toValue: 0.8,
        duration: 200,
        useNativeDriver: true,
      }),
    ]).start(() => {
      setAlertVisible(false);
    });
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'pending': return { bg: '#FEF3C7', text: '#D97706' };
      case 'accepted': return { bg: '#DBEAFE', text: '#2563EB' };
      case 'confirmed': return { bg: '#DBEAFE', text: '#2563EB' };
      case 'preparing': return { bg: '#E0E7FF', text: '#4F46E5' };
      case 'ready': return { bg: '#D1FAE5', text: '#059669' };
      case 'picked_up': return { bg: '#CFFAFE', text: '#0891B2' };
      case 'delivered': return { bg: '#DCFCE7', text: '#22C55E' };
      case 'cancelled': return { bg: '#FEE2E2', text: '#DC2626' };
      case 'rejected': return { bg: '#FEE2E2', text: '#DC2626' };
      default: return { bg: '#F3F4F6', text: '#6B7280' };
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pending': return 'time';
      case 'accepted': return 'checkmark-circle';
      case 'confirmed': return 'checkmark-circle';
      case 'preparing': return 'restaurant';
      case 'ready': return 'bag-check';
      case 'picked_up': return 'bicycle';
      case 'delivered': return 'checkmark-done-circle';
      case 'cancelled': return 'close-circle';
      case 'rejected': return 'close-circle';
      default: return 'ellipse';
    }
  };

  const handleRejectOrder = async (order: Order) => {
    try {
      await orderAPI.reject(order.order_id, 'Vendor rejected');
      showClaymorphismAlert('warning', 'Order Rejected', 'The order has been declined');
      loadOrders();
    } catch (error) {
      showClaymorphismAlert('error', 'Oops!', 'Failed to reject order');
    }
  };

  const renderOrder = ({ item, index }: { item: Order; index: number }) => {
    const statusColor = getStatusColor(item.status);
    const isNew = item.status === 'pending';
    
    return (
      <Animated.View
        style={[
          styles.orderCard,
          isNew && styles.orderCardNew,
          { opacity: 1, transform: [{ translateY: 0 }] }
        ]}
      >
        <TouchableOpacity
          activeOpacity={0.7}
          onPress={() => router.push(`/(main)/orders/${item.order_id}`)}
        >
          {/* Order Header */}
          <View style={styles.orderHeader}>
            <View style={styles.orderIdRow}>
              <View style={[styles.statusIconBg, { backgroundColor: statusColor.bg }]}>
                <Ionicons name={getStatusIcon(item.status) as any} size={18} color={statusColor.text} />
              </View>
              <View>
                <Text style={styles.orderId}>#{item.order_id.slice(-6).toUpperCase()}</Text>
                <Text style={styles.orderTime}>
                  {format(new Date(item.created_at), 'MMM d, h:mm a')}
                </Text>
              </View>
            </View>
            <View style={[styles.statusBadge, { backgroundColor: statusColor.bg }]}>
              <Text style={[styles.statusText, { color: statusColor.text }]}>
                {item.status.replace('_', ' ').toUpperCase()}
              </Text>
            </View>
          </View>

          {/* Customer Info */}
          <View style={styles.customerRow}>
            <View style={styles.customerAvatar}>
              <Text style={styles.customerInitial}>
                {(item.customer_name || 'C')[0].toUpperCase()}
              </Text>
            </View>
            <View style={styles.customerInfo}>
              <Text style={styles.customerName}>{item.customer_name || 'Customer'}</Text>
              {item.customer_phone && (
                <Text style={styles.customerPhone}>{item.customer_phone}</Text>
              )}
            </View>
            <TouchableOpacity style={styles.callBtn}>
              <Ionicons name="call" size={18} color="#22C55E" />
            </TouchableOpacity>
          </View>

          {/* Items Preview */}
          <View style={styles.itemsContainer}>
            <View style={styles.itemsHeader}>
              <Ionicons name="cart" size={16} color="#6B7280" />
              <Text style={styles.itemsCount}>{item.items.length} items</Text>
            </View>
            <View style={styles.itemsList}>
              {item.items.slice(0, 3).map((orderItem, idx) => (
                <View key={idx} style={styles.itemRow}>
                  <Text style={styles.itemQty}>{orderItem.quantity}x</Text>
                  <Text style={styles.itemName} numberOfLines={1}>{orderItem.name}</Text>
                  <Text style={styles.itemPrice}>₹{orderItem.price * orderItem.quantity}</Text>
                </View>
              ))}
              {item.items.length > 3 && (
                <Text style={styles.moreItems}>+{item.items.length - 3} more items</Text>
              )}
            </View>
          </View>

          {/* Order Footer */}
          <View style={styles.orderFooter}>
            <View style={styles.deliveryInfo}>
              <View style={[styles.deliveryBadge, item.delivery_type === 'delivery' && styles.deliveryBadgeActive]}>
                <Ionicons
                  name={item.delivery_type === 'self_pickup' ? 'storefront' : 'bicycle'}
                  size={16}
                  color={item.delivery_type === 'delivery' ? '#6366F1' : '#6B7280'}
                />
                <Text style={[
                  styles.deliveryText,
                  item.delivery_type === 'delivery' && styles.deliveryTextActive
                ]}>
                  {item.delivery_type === 'self_pickup' ? 'Self Pickup' : 'Delivery'}
                </Text>
              </View>
            </View>
            <View style={styles.totalContainer}>
              <Text style={styles.totalLabel}>Total</Text>
              <Text style={styles.totalAmount}>₹{item.total_amount}</Text>
            </View>
          </View>

          {/* Action Buttons for New Orders */}
          {isNew && (
            <View style={styles.actionButtons}>
              <TouchableOpacity 
                style={styles.rejectBtn}
                onPress={() => Alert.alert('Reject Order', 'Are you sure?', [
                  { text: 'Cancel' },
                  { text: 'Reject', style: 'destructive', onPress: () => orderAPI.updateStatus(item.order_id, 'cancelled').then(loadOrders) }
                ])}
              >
                <Ionicons name="close" size={20} color="#DC2626" />
                <Text style={styles.rejectBtnText}>Reject</Text>
              </TouchableOpacity>
              <TouchableOpacity 
                style={styles.acceptBtn}
                onPress={() => handleAcceptOrder(item)}
              >
                <Ionicons name="checkmark" size={20} color="#FFFFFF" />
                <Text style={styles.acceptBtnText}>Accept Order</Text>
              </TouchableOpacity>
            </View>
          )}
        </TouchableOpacity>
      </Animated.View>
    );
  };

  const indicatorPosition = slideAnim.interpolate({
    inputRange: [0, 1, 2],
    outputRange: [0, (width - 32) / 3, ((width - 32) / 3) * 2],
  });

  // Stock Alert Component
  const StockAlert = () => {
    if (lowStockProducts.length === 0 && outOfStockProducts.length === 0) return null;
    
    return (
      <View style={styles.stockAlertContainer}>
        {outOfStockProducts.length > 0 && (
          <TouchableOpacity 
            style={styles.stockAlertCard}
            onPress={() => router.push('/(main)/products')}
          >
            <View style={[styles.stockAlertIcon, { backgroundColor: '#FEE2E2' }]}>
              <Ionicons name="alert-circle" size={20} color="#DC2626" />
            </View>
            <View style={styles.stockAlertContent}>
              <Text style={styles.stockAlertTitle}>{outOfStockProducts.length} Out of Stock</Text>
              <Text style={styles.stockAlertText} numberOfLines={1}>
                {outOfStockProducts.slice(0, 2).map(p => p.name).join(', ')}
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color="#9CA3AF" />
          </TouchableOpacity>
        )}
        
        {lowStockProducts.length > 0 && (
          <TouchableOpacity 
            style={styles.stockAlertCard}
            onPress={() => router.push('/(main)/products')}
          >
            <View style={[styles.stockAlertIcon, { backgroundColor: '#FEF3C7' }]}>
              <Ionicons name="warning" size={20} color="#D97706" />
            </View>
            <View style={styles.stockAlertContent}>
              <Text style={styles.stockAlertTitleWarning}>{lowStockProducts.length} Low Stock</Text>
              <Text style={styles.stockAlertText} numberOfLines={1}>
                {lowStockProducts.slice(0, 2).map(p => `${p.name} (${p.stock_quantity})`).join(', ')}
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color="#9CA3AF" />
          </TouchableOpacity>
        )}
      </View>
    );
  };

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      {/* Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>Orders</Text>
          <Text style={styles.subtitle}>Manage your incoming orders</Text>
        </View>
        <TouchableOpacity style={styles.refreshBtn} onPress={onRefresh}>
          <Ionicons name="refresh" size={22} color="#6366F1" />
        </TouchableOpacity>
      </View>

      {/* Stock Alert */}
      <StockAlert />

      {/* Tab Bar */}
      <View style={styles.tabContainer}>
        <View style={styles.tabBar}>
          <TouchableOpacity
            style={styles.tab}
            onPress={() => handleTabChange('new')}
          >
            <Text style={[styles.tabText, activeTab === 'new' && styles.tabTextActive]}>
              New
            </Text>
            {newOrdersCount > 0 && (
              <Animated.View style={[styles.tabBadge, styles.tabBadgeNew, { transform: [{ scale: pulseAnim }] }]}>
                <Text style={styles.tabBadgeText}>{newOrdersCount}</Text>
              </Animated.View>
            )}
          </TouchableOpacity>
          
          <TouchableOpacity
            style={styles.tab}
            onPress={() => handleTabChange('active')}
          >
            <Text style={[styles.tabText, activeTab === 'active' && styles.tabTextActive]}>
              Active
            </Text>
            {activeOrdersCount > 0 && (
              <View style={[styles.tabBadge, styles.tabBadgeActive]}>
                <Text style={styles.tabBadgeText}>{activeOrdersCount}</Text>
              </View>
            )}
          </TouchableOpacity>
          
          <TouchableOpacity
            style={styles.tab}
            onPress={() => handleTabChange('completed')}
          >
            <Text style={[styles.tabText, activeTab === 'completed' && styles.tabTextActive]}>
              Completed
            </Text>
            {completedOrdersCount > 0 && (
              <View style={[styles.tabBadge, styles.tabBadgeCompleted]}>
                <Text style={styles.tabBadgeTextDark}>{completedOrdersCount}</Text>
              </View>
            )}
          </TouchableOpacity>
          
          {/* Animated Indicator */}
          <Animated.View
            style={[
              styles.tabIndicator,
              { transform: [{ translateX: indicatorPosition }] }
            ]}
          />
        </View>
      </View>

      {/* Orders List */}
      <FlatList
        data={filteredOrders}
        renderItem={renderOrder}
        keyExtractor={(item) => item.order_id}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={['#6366F1']} />
        }
        showsVerticalScrollIndicator={false}
        ListEmptyComponent={
          <View style={styles.emptyState}>
            <View style={styles.emptyIconBg}>
              <Ionicons
                name={
                  activeTab === 'new' ? 'notifications-off' :
                  activeTab === 'active' ? 'hourglass-outline' : 'archive-outline'
                }
                size={48}
                color="#D1D5DB"
              />
            </View>
            <Text style={styles.emptyTitle}>
              {activeTab === 'new' ? 'No new orders' :
               activeTab === 'active' ? 'No active orders' : 'No completed orders'}
            </Text>
            <Text style={styles.emptySubtitle}>
              {activeTab === 'new' ? 'New orders will appear here when customers place them' :
               activeTab === 'active' ? 'Orders you\'re working on will show here' :
               'Completed and cancelled orders will be archived here'}
            </Text>
          </View>
        }
      />
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
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 16,
  },
  title: {
    fontSize: 28,
    fontWeight: '800',
    color: '#111827',
  },
  subtitle: {
    fontSize: 14,
    color: '#6B7280',
    marginTop: 2,
  },
  refreshBtn: {
    width: 44,
    height: 44,
    backgroundColor: '#EEF2FF',
    borderRadius: 22,
    justifyContent: 'center',
    alignItems: 'center',
  },
  // Stock Alert
  stockAlertContainer: {
    paddingHorizontal: 16,
    marginBottom: 8,
    gap: 8,
  },
  stockAlertCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    padding: 12,
    borderRadius: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 1,
  },
  stockAlertIcon: {
    width: 36,
    height: 36,
    borderRadius: 10,
    justifyContent: 'center',
    alignItems: 'center',
  },
  stockAlertContent: {
    flex: 1,
    marginLeft: 12,
  },
  stockAlertTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: '#DC2626',
  },
  stockAlertTitleWarning: {
    fontSize: 13,
    fontWeight: '700',
    color: '#D97706',
  },
  stockAlertText: {
    fontSize: 12,
    color: '#6B7280',
    marginTop: 2,
  },
  // Tab Bar
  tabContainer: {
    paddingHorizontal: 16,
    marginBottom: 8,
  },
  tabBar: {
    flexDirection: 'row',
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 4,
    position: 'relative',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  tab: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 14,
    gap: 6,
    zIndex: 1,
  },
  tabText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#6B7280',
  },
  tabTextActive: {
    color: '#6366F1',
  },
  tabBadge: {
    minWidth: 20,
    height: 20,
    borderRadius: 10,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 6,
  },
  tabBadgeNew: {
    backgroundColor: '#EF4444',
  },
  tabBadgeActive: {
    backgroundColor: '#6366F1',
  },
  tabBadgeCompleted: {
    backgroundColor: '#E5E7EB',
  },
  tabBadgeText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  tabBadgeTextDark: {
    fontSize: 11,
    fontWeight: '700',
    color: '#6B7280',
  },
  tabIndicator: {
    position: 'absolute',
    bottom: 4,
    left: 4,
    width: (width - 32 - 8) / 3,
    height: 44,
    backgroundColor: '#EEF2FF',
    borderRadius: 12,
  },
  // List
  listContent: {
    paddingHorizontal: 16,
    paddingBottom: 100,
  },
  // Order Card
  orderCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 16,
    marginBottom: 14,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  orderCardNew: {
    borderWidth: 2,
    borderColor: '#FDE68A',
    backgroundColor: '#FFFEF7',
  },
  orderHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 14,
  },
  orderIdRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  statusIconBg: {
    width: 40,
    height: 40,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
  },
  orderId: {
    fontSize: 16,
    fontWeight: '700',
    color: '#111827',
  },
  orderTime: {
    fontSize: 12,
    color: '#9CA3AF',
    marginTop: 2,
  },
  statusBadge: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 8,
  },
  statusText: {
    fontSize: 10,
    fontWeight: '700',
  },
  // Customer Row
  customerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingBottom: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#F3F4F6',
  },
  customerAvatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#EEF2FF',
    justifyContent: 'center',
    alignItems: 'center',
  },
  customerInitial: {
    fontSize: 16,
    fontWeight: '700',
    color: '#6366F1',
  },
  customerInfo: {
    flex: 1,
    marginLeft: 12,
  },
  customerName: {
    fontSize: 15,
    fontWeight: '600',
    color: '#111827',
  },
  customerPhone: {
    fontSize: 13,
    color: '#6B7280',
    marginTop: 2,
  },
  callBtn: {
    width: 40,
    height: 40,
    backgroundColor: '#DCFCE7',
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
  },
  // Items
  itemsContainer: {
    paddingVertical: 14,
  },
  itemsHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 10,
  },
  itemsCount: {
    fontSize: 13,
    fontWeight: '600',
    color: '#6B7280',
  },
  itemsList: {
    backgroundColor: '#F9FAFB',
    borderRadius: 12,
    padding: 12,
  },
  itemRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  itemQty: {
    fontSize: 13,
    fontWeight: '700',
    color: '#6366F1',
    width: 30,
  },
  itemName: {
    flex: 1,
    fontSize: 14,
    color: '#374151',
  },
  itemPrice: {
    fontSize: 14,
    fontWeight: '600',
    color: '#111827',
  },
  moreItems: {
    fontSize: 13,
    fontWeight: '600',
    color: '#6366F1',
    marginTop: 4,
  },
  // Footer
  orderFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingTop: 14,
    borderTopWidth: 1,
    borderTopColor: '#F3F4F6',
  },
  deliveryInfo: {},
  deliveryBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F3F4F6',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
    gap: 6,
  },
  deliveryBadgeActive: {
    backgroundColor: '#EEF2FF',
  },
  deliveryText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#6B7280',
  },
  deliveryTextActive: {
    color: '#6366F1',
  },
  totalContainer: {
    alignItems: 'flex-end',
  },
  totalLabel: {
    fontSize: 11,
    color: '#9CA3AF',
  },
  totalAmount: {
    fontSize: 22,
    fontWeight: '800',
    color: '#111827',
  },
  // Action Buttons
  actionButtons: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 16,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: '#FDE68A',
  },
  rejectBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FEE2E2',
    paddingVertical: 14,
    borderRadius: 12,
    gap: 6,
  },
  rejectBtnText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#DC2626',
  },
  acceptBtn: {
    flex: 2,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#22C55E',
    paddingVertical: 14,
    borderRadius: 12,
    gap: 6,
  },
  acceptBtnText: {
    fontSize: 15,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  // Empty State
  emptyState: {
    alignItems: 'center',
    paddingVertical: 60,
    paddingHorizontal: 32,
  },
  emptyIconBg: {
    width: 96,
    height: 96,
    backgroundColor: '#F3F4F6',
    borderRadius: 48,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 20,
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#374151',
    marginBottom: 8,
  },
  emptySubtitle: {
    fontSize: 14,
    color: '#9CA3AF',
    textAlign: 'center',
    lineHeight: 22,
  },
});
