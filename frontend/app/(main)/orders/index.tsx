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
  Modal,
  Vibration,
  AppState,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { useFocusEffect } from '@react-navigation/native';
import { Ionicons } from '@expo/vector-icons';
import { Audio } from 'expo-av';
import { orderAPI } from '../../../src/utils/api';
import { Order } from '../../../src/types';
import { useAlert } from '../../../src/context/AlertContext';
import { format } from 'date-fns';

const { width, height } = Dimensions.get('window');

type TabType = 'new' | 'active' | 'completed';

export default function OrdersScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { showAlert } = useAlert();
  const [allOrders, setAllOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState<TabType>('new');
  const slideAnim = useRef(new Animated.Value(0)).current;
  const pulseAnim = useRef(new Animated.Value(1)).current;
  
  // New Order Alert State
  const [showNewOrderAlert, setShowNewOrderAlert] = useState(false);
  const [newOrderData, setNewOrderData] = useState<Order | null>(null);
  const [countdown, setCountdown] = useState(0);
  const alertScaleAnim = useRef(new Animated.Value(0.5)).current;
  const alertOpacityAnim = useRef(new Animated.Value(0)).current;
  const countdownAnim = useRef(new Animated.Value(1)).current;
  const previousOrderIds = useRef<Set<string>>(new Set());
  const soundRef = useRef<Audio.Sound | null>(null);

  // Filter orders by tab
  const getFilteredOrders = () => {
    switch (activeTab) {
      case 'new':
        return allOrders.filter(o => o.status === 'pending');
      case 'active':
        return allOrders.filter(o => ['accepted', 'confirmed', 'preparing', 'ready', 'awaiting_pickup', 'picked_up', 'out_for_delivery'].includes(o.status));
      case 'completed':
        return allOrders.filter(o => ['delivered', 'cancelled', 'rejected'].includes(o.status));
      default:
        return allOrders;
    }
  };

  const filteredOrders = getFilteredOrders();
  const pendingOrders = allOrders.filter(o => o.status === 'pending');
  const newOrdersCount = pendingOrders.length;
  const activeOrdersCount = allOrders.filter(o => ['accepted', 'confirmed', 'preparing', 'ready', 'awaiting_pickup', 'picked_up', 'out_for_delivery'].includes(o.status)).length;
  const completedOrdersCount = allOrders.filter(o => ['delivered', 'cancelled', 'rejected'].includes(o.status)).length;

  // Play notification sound
  const playNotificationSound = async () => {
    try {
      // Use system sound via vibration pattern (since we can't load custom sounds easily)
      Vibration.vibrate([0, 500, 200, 500, 200, 500]);
    } catch (error) {
      console.error('Sound error:', error);
    }
  };

  // Check for new orders
  const checkForNewOrders = (orders: Order[]) => {
    const currentPendingIds = new Set(orders.filter(o => o.status === 'pending').map(o => o.order_id));
    
    // Find truly new orders (not seen before)
    const newOrders = orders.filter(
      o => o.status === 'pending' && !previousOrderIds.current.has(o.order_id)
    );
    
    if (newOrders.length > 0 && previousOrderIds.current.size > 0) {
      // Show alert for the newest order
      const newestOrder = newOrders[0];
      showNewOrderNotification(newestOrder);
    }
    
    // Update previous order IDs
    previousOrderIds.current = currentPendingIds;
  };

  // Show full-screen new order notification
  const showNewOrderNotification = (order: Order) => {
    setNewOrderData(order);
    setCountdown(order.auto_accept_seconds || 180);
    setShowNewOrderAlert(true);
    
    // Vibrate intensely
    playNotificationSound();
    
    // Animate alert appearance
    Animated.parallel([
      Animated.spring(alertScaleAnim, {
        toValue: 1,
        friction: 8,
        tension: 40,
        useNativeDriver: true,
      }),
      Animated.timing(alertOpacityAnim, {
        toValue: 1,
        duration: 200,
        useNativeDriver: true,
      }),
    ]).start();
  };

  // Countdown timer effect
  useEffect(() => {
    if (showNewOrderAlert && countdown > 0) {
      const timer = setInterval(() => {
        setCountdown(prev => {
          if (prev <= 1) {
            // Time's up - order will auto-accept
            hideNewOrderAlert();
            loadOrders();
            return 0;
          }
          
          // Pulse animation every second
          Animated.sequence([
            Animated.timing(countdownAnim, {
              toValue: 1.1,
              duration: 100,
              useNativeDriver: true,
            }),
            Animated.timing(countdownAnim, {
              toValue: 1,
              duration: 100,
              useNativeDriver: true,
            }),
          ]).start();
          
          return prev - 1;
        });
      }, 1000);
      
      return () => clearInterval(timer);
    }
  }, [showNewOrderAlert, countdown]);

  const hideNewOrderAlert = () => {
    Animated.parallel([
      Animated.timing(alertScaleAnim, {
        toValue: 0.5,
        duration: 200,
        useNativeDriver: true,
      }),
      Animated.timing(alertOpacityAnim, {
        toValue: 0,
        duration: 200,
        useNativeDriver: true,
      }),
    ]).start(() => {
      setShowNewOrderAlert(false);
      setNewOrderData(null);
    });
  };

  const loadOrders = async () => {
    try {
      const ordersRes = await orderAPI.getAll();
      const orders = ordersRes.data;
      
      // Check for new orders before updating state
      checkForNewOrders(orders);
      setAllOrders(orders);
    } catch (error) {
      console.error('Load orders error:', error);
    } finally {
      setLoading(false);
    }
  };

  // Auto-refresh when screen comes into focus
  useFocusEffect(
    useCallback(() => {
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
      
      // Set up interval for periodic refresh (every 5 seconds for orders - more frequent)
      const intervalId = setInterval(() => {
        loadOrders();
      }, 5000);
      
      return () => clearInterval(intervalId);
    }, [])
  );

  // Refresh when app comes to foreground
  useEffect(() => {
    const subscription = AppState.addEventListener('change', (nextAppState) => {
      if (nextAppState === 'active') {
        loadOrders();
      }
    });

    return () => subscription.remove();
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
      showAlert({
        type: 'success',
        title: 'Order Accepted! 🎉',
        message: 'Start preparing the order now',
      });
      hideNewOrderAlert();
      loadOrders();
    } catch (error) {
      showAlert({
        type: 'error',
        title: 'Error',
        message: 'Failed to accept order',
      });
    }
  };

  const handleRejectOrder = async (order: Order) => {
    showAlert({
      type: 'confirm',
      title: 'Reject Order?',
      message: 'Are you sure you want to reject this order? Customer will be notified.',
      buttons: [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Reject',
          style: 'destructive',
          onPress: async () => {
            try {
              await orderAPI.reject(order.order_id, 'Vendor rejected');
              hideNewOrderAlert();
              loadOrders();
            } catch (error) {
              showAlert({
                type: 'error',
                title: 'Error',
                message: 'Failed to reject order',
              });
            }
          },
        },
      ],
    });
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'pending': return { bg: '#FEF3C7', text: '#D97706', border: '#FDE68A' };
      // PRIORITY: Confirmed but not started - RED/URGENT
      case 'accepted': return { bg: '#FEE2E2', text: '#DC2626', border: '#FECACA' };
      case 'confirmed': return { bg: '#FEE2E2', text: '#DC2626', border: '#FECACA' };
      // Preparing - ORANGE/IN PROGRESS
      case 'preparing': return { bg: '#FEF3C7', text: '#D97706', border: '#FDE68A' };
      // Ready - GREEN/COMPLETED PREP
      case 'ready': return { bg: '#D1FAE5', text: '#059669', border: '#A7F3D0' };
      // Delivery stages - BLUE
      case 'awaiting_pickup': return { bg: '#DBEAFE', text: '#2563EB', border: '#BFDBFE' };
      case 'picked_up': return { bg: '#E0E7FF', text: '#4F46E5', border: '#C7D2FE' };
      case 'out_for_delivery': return { bg: '#EDE9FE', text: '#7C3AED', border: '#DDD6FE' };
      // Final statuses
      case 'delivered': return { bg: '#DCFCE7', text: '#22C55E', border: '#BBF7D0' };
      case 'cancelled': return { bg: '#FEE2E2', text: '#DC2626', border: '#FECACA' };
      case 'rejected': return { bg: '#FEE2E2', text: '#DC2626', border: '#FECACA' };
      default: return { bg: '#F3F4F6', text: '#6B7280', border: '#E5E7EB' };
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pending': return 'time';
      case 'accepted': return 'alert-circle'; // Changed to alert for urgency
      case 'confirmed': return 'alert-circle'; // Changed to alert for urgency
      case 'preparing': return 'flame'; // Changed to flame for cooking
      case 'ready': return 'checkmark-circle';
      case 'awaiting_pickup': return 'hourglass';
      case 'picked_up': return 'bicycle';
      case 'out_for_delivery': return 'navigate';
      case 'delivered': return 'checkmark-done-circle';
      case 'cancelled': return 'close-circle';
      case 'rejected': return 'close-circle';
      default: return 'ellipse';
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'pending': return 'NEW ORDER';
      case 'accepted': return 'START PREPARING!';
      case 'confirmed': return 'START PREPARING!';
      case 'preparing': return 'PREPARING';
      case 'ready': return 'READY';
      case 'awaiting_pickup': return 'AWAITING PICKUP';
      case 'picked_up': return 'PICKED UP';
      case 'out_for_delivery': return 'ON THE WAY';
      case 'delivered': return 'DELIVERED';
      case 'cancelled': return 'CANCELLED';
      case 'rejected': return 'REJECTED';
      default: return status.toUpperCase();
    }
  };

  const isPriorityOrder = (status: string) => {
    return status === 'accepted' || status === 'confirmed';
  };

  const formatCountdown = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Handle workflow action
  const handleWorkflowAction = async (order: Order, action: string) => {
    try {
      await orderAPI.workflowAction(order.order_id, action);
      const messages: Record<string, string> = {
        'start_preparing': 'Started preparing! 👨‍🍳',
        'mark_ready': 'Order is ready! 📦',
      };
      showAlert({
        type: 'success',
        title: messages[action] || 'Updated!',
        message: 'Order status updated',
      });
      loadOrders();
    } catch (error) {
      showAlert({
        type: 'error',
        title: 'Error',
        message: 'Failed to update order',
      });
    }
  };

  const renderOrder = ({ item, index }: { item: Order; index: number }) => {
    const statusColor = getStatusColor(item.status);
    const isPending = item.status === 'pending';
    const isConfirmed = item.status === 'confirmed' || item.status === 'accepted';
    const isPreparing = item.status === 'preparing';
    const isReady = item.status === 'ready';
    const isPriority = isPriorityOrder(item.status);
    const autoAcceptSeconds = (item as any).auto_accept_seconds;
    
    return (
      <TouchableOpacity
        activeOpacity={0.7}
        onPress={() => router.push(`/(main)/orders/${item.order_id}`)}
        style={[
          styles.orderCard,
          isPending && styles.orderCardPending,
          isPriority && styles.orderCardPriority,
          isPreparing && styles.orderCardPreparing,
          isReady && styles.orderCardReady,
        ]}
      >
        {/* Priority Badge for Confirmed Orders */}
        {isPriority && (
          <View style={styles.priorityBadge}>
            <Ionicons name="alert-circle" size={14} color="#FFFFFF" />
            <Text style={styles.priorityBadgeText}>ACTION NEEDED</Text>
          </View>
        )}

        {/* Countdown Badge for Pending */}
        {isPending && autoAcceptSeconds > 0 && (
          <View style={styles.countdownBadge}>
            <Ionicons name="timer" size={14} color="#FFFFFF" />
            <Text style={styles.countdownBadgeText}>
              {formatCountdown(autoAcceptSeconds)}
            </Text>
          </View>
        )}

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
              {getStatusLabel(item.status)}
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
          <Text style={styles.totalAmount}>₹{item.total_amount}</Text>
        </View>

        {/* Items Preview */}
        <View style={styles.itemsPreview}>
          <Text style={styles.itemsText}>
            {item.items.length} items • {item.items.slice(0, 2).map(i => i.name).join(', ')}
            {item.items.length > 2 ? ` +${item.items.length - 2} more` : ''}
          </Text>
        </View>

        {/* Quick Actions for Pending */}
        {isPending && (
          <View style={styles.quickActions}>
            <TouchableOpacity 
              style={styles.rejectBtnSmall}
              onPress={(e) => { e.stopPropagation(); handleRejectOrder(item); }}
            >
              <Ionicons name="close" size={18} color="#DC2626" />
            </TouchableOpacity>
            <TouchableOpacity 
              style={styles.acceptBtnSmall}
              onPress={(e) => { e.stopPropagation(); handleAcceptOrder(item); }}
            >
              <Ionicons name="checkmark" size={18} color="#FFFFFF" />
              <Text style={styles.acceptBtnTextSmall}>Accept</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Quick Action for Confirmed - Start Preparing */}
        {isConfirmed && (
          <View style={styles.quickActions}>
            <TouchableOpacity 
              style={styles.startPreparingBtn}
              onPress={(e) => { e.stopPropagation(); handleWorkflowAction(item, 'start_preparing'); }}
            >
              <Ionicons name="flame" size={18} color="#FFFFFF" />
              <Text style={styles.startPreparingBtnText}>Start Preparing</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Quick Action for Preparing - Mark Ready */}
        {isPreparing && (
          <View style={styles.quickActions}>
            <TouchableOpacity 
              style={styles.markReadyBtn}
              onPress={(e) => { e.stopPropagation(); handleWorkflowAction(item, 'mark_ready'); }}
            >
              <Ionicons name="checkmark-circle" size={18} color="#FFFFFF" />
              <Text style={styles.markReadyBtnText}>Mark Ready</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Quick Action for Ready - Assign Delivery */}
        {isReady && (
          <View style={styles.quickActionsRow}>
            <TouchableOpacity 
              style={styles.assignDeliveryBtn}
              onPress={() => router.push(`/(main)/orders/${item.order_id}`)}
            >
              <Ionicons name="bicycle" size={16} color="#059669" />
              <Text style={styles.assignDeliveryBtnText}>Assign Delivery</Text>
            </TouchableOpacity>
          </View>
        )}
      </TouchableOpacity>
    );
  };

  const indicatorPosition = slideAnim.interpolate({
    inputRange: [0, 1, 2],
    outputRange: [0, (width - 32) / 3, ((width - 32) / 3) * 2],
  });

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Text style={styles.title}>Orders</Text>
          {newOrdersCount > 0 && (
            <Animated.View style={[styles.newOrderIndicator, { transform: [{ scale: pulseAnim }] }]}>
              <View style={styles.newOrderDot} />
              <Text style={styles.newOrderText}>{newOrdersCount} new</Text>
            </Animated.View>
          )}
        </View>
        <TouchableOpacity style={styles.refreshBtn} onPress={onRefresh}>
          <Ionicons name="refresh" size={22} color="#6366F1" />
        </TouchableOpacity>
      </View>

      {/* Tab Bar */}
      <View style={styles.tabContainer}>
        <View style={styles.tabBar}>
          <TouchableOpacity
            style={styles.tab}
            onPress={() => handleTabChange('new')}
          >
            <Text style={[styles.tabText, activeTab === 'new' && styles.tabTextActive]}>
              Pending
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
              History
            </Text>
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
              {activeTab === 'new' ? 'No pending orders' :
               activeTab === 'active' ? 'No active orders' : 'No order history'}
            </Text>
            <Text style={styles.emptySubtitle}>
              {activeTab === 'new' ? 'New orders will appear here instantly' :
               activeTab === 'active' ? 'Orders being processed will show here' :
               'Completed orders will be archived here'}
            </Text>
          </View>
        }
      />

      {/* Full-Screen New Order Alert Modal */}
      <Modal
        visible={showNewOrderAlert}
        transparent
        animationType="none"
        onRequestClose={hideNewOrderAlert}
      >
        <Animated.View 
          style={[
            styles.newOrderOverlay,
            { opacity: alertOpacityAnim }
          ]}
        >
          <Animated.View 
            style={[
              styles.newOrderModal,
              { transform: [{ scale: alertScaleAnim }] }
            ]}
          >
            {/* Pulsing Ring Animation */}
            <View style={styles.alertRingContainer}>
              <View style={styles.alertRing1} />
              <View style={styles.alertRing2} />
              <View style={styles.alertIconCircle}>
                <Ionicons name="receipt" size={40} color="#FFFFFF" />
              </View>
            </View>

            <Text style={styles.newOrderTitle}>NEW ORDER!</Text>
            
            {/* Countdown Timer */}
            <Animated.View style={[styles.countdownContainer, { transform: [{ scale: countdownAnim }] }]}>
              <Text style={styles.countdownLabel}>Auto-accepts in</Text>
              <Text style={styles.countdownTime}>{formatCountdown(countdown)}</Text>
              <View style={styles.countdownProgressBg}>
                <View 
                  style={[
                    styles.countdownProgress,
                    { width: `${(countdown / 180) * 100}%` }
                  ]} 
                />
              </View>
            </Animated.View>

            {newOrderData && (
              <>
                {/* Order Summary */}
                <View style={styles.orderSummaryCard}>
                  <View style={styles.orderSummaryHeader}>
                    <Text style={styles.orderSummaryId}>
                      #{newOrderData.order_id.slice(-8).toUpperCase()}
                    </Text>
                    <Text style={styles.orderSummaryTotal}>₹{newOrderData.total_amount}</Text>
                  </View>
                  
                  <View style={styles.orderSummaryCustomer}>
                    <View style={styles.customerAvatarLarge}>
                      <Text style={styles.customerInitialLarge}>
                        {(newOrderData.customer_name || 'C')[0].toUpperCase()}
                      </Text>
                    </View>
                    <View style={styles.customerDetails}>
                      <Text style={styles.customerNameLarge}>{newOrderData.customer_name || 'Customer'}</Text>
                      <Text style={styles.customerPhoneLarge}>{newOrderData.customer_phone}</Text>
                    </View>
                  </View>

                  <View style={styles.orderSummaryItems}>
                    <Text style={styles.itemsLabel}>{newOrderData.items.length} items</Text>
                    {newOrderData.items.slice(0, 3).map((item, idx) => (
                      <Text key={idx} style={styles.itemLine}>
                        {item.quantity}x {item.name}
                      </Text>
                    ))}
                    {newOrderData.items.length > 3 && (
                      <Text style={styles.moreItemsText}>+{newOrderData.items.length - 3} more items</Text>
                    )}
                  </View>

                  <View style={styles.deliveryBadgeLarge}>
                    <Ionicons 
                      name={newOrderData.delivery_type === 'self_pickup' ? 'storefront' : 'bicycle'} 
                      size={16} 
                      color="#6366F1" 
                    />
                    <Text style={styles.deliveryTextLarge}>
                      {newOrderData.delivery_type === 'self_pickup' ? 'Customer Pickup' : 'Delivery'}
                    </Text>
                  </View>
                </View>

                {/* Action Buttons */}
                <View style={styles.alertActions}>
                  <TouchableOpacity 
                    style={styles.rejectBtnLarge}
                    onPress={() => handleRejectOrder(newOrderData)}
                  >
                    <Ionicons name="close" size={24} color="#DC2626" />
                    <Text style={styles.rejectBtnTextLarge}>Reject</Text>
                  </TouchableOpacity>
                  
                  <TouchableOpacity 
                    style={styles.acceptBtnLarge}
                    onPress={() => handleAcceptOrder(newOrderData)}
                  >
                    <Ionicons name="checkmark" size={24} color="#FFFFFF" />
                    <Text style={styles.acceptBtnTextLarge}>Accept Order</Text>
                  </TouchableOpacity>
                </View>
              </>
            )}
          </Animated.View>
        </Animated.View>
      </Modal>
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
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  title: {
    fontSize: 28,
    fontWeight: '800',
    color: '#111827',
  },
  newOrderIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FEE2E2',
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 12,
    gap: 6,
  },
  newOrderDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#EF4444',
  },
  newOrderText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#DC2626',
  },
  refreshBtn: {
    width: 44,
    height: 44,
    backgroundColor: '#EEF2FF',
    borderRadius: 22,
    justifyContent: 'center',
    alignItems: 'center',
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
  tabBadgeText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#FFFFFF',
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
    borderRadius: 16,
    padding: 14,
    marginBottom: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 6,
    elevation: 2,
  },
  orderCardPending: {
    borderWidth: 2,
    borderColor: '#FDE68A',
    backgroundColor: '#FFFEF7',
  },
  countdownBadge: {
    position: 'absolute',
    top: -8,
    right: 12,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#EF4444',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    gap: 4,
    zIndex: 1,
  },
  countdownBadgeText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  orderHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  orderIdRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  statusIconBg: {
    width: 36,
    height: 36,
    borderRadius: 10,
    justifyContent: 'center',
    alignItems: 'center',
  },
  orderId: {
    fontSize: 15,
    fontWeight: '700',
    color: '#111827',
  },
  orderTime: {
    fontSize: 11,
    color: '#9CA3AF',
    marginTop: 1,
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  statusText: {
    fontSize: 9,
    fontWeight: '700',
  },
  customerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingBottom: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#F3F4F6',
  },
  customerAvatar: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#EEF2FF',
    justifyContent: 'center',
    alignItems: 'center',
  },
  customerInitial: {
    fontSize: 14,
    fontWeight: '700',
    color: '#6366F1',
  },
  customerInfo: {
    flex: 1,
    marginLeft: 10,
  },
  customerName: {
    fontSize: 14,
    fontWeight: '600',
    color: '#111827',
  },
  customerPhone: {
    fontSize: 12,
    color: '#6B7280',
  },
  totalAmount: {
    fontSize: 18,
    fontWeight: '800',
    color: '#111827',
  },
  itemsPreview: {
    paddingVertical: 10,
  },
  itemsText: {
    fontSize: 13,
    color: '#6B7280',
  },
  quickActions: {
    flexDirection: 'row',
    gap: 10,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: '#FDE68A',
  },
  rejectBtnSmall: {
    width: 44,
    height: 44,
    backgroundColor: '#FEE2E2',
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
  },
  acceptBtnSmall: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#22C55E',
    paddingVertical: 12,
    borderRadius: 12,
    gap: 6,
  },
  acceptBtnTextSmall: {
    fontSize: 14,
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
  // Full-Screen New Order Alert
  newOrderOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.85)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  newOrderModal: {
    width: '100%',
    maxWidth: 380,
    backgroundColor: '#FFFFFF',
    borderRadius: 28,
    padding: 24,
    alignItems: 'center',
  },
  alertRingContainer: {
    position: 'relative',
    width: 120,
    height: 120,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
  },
  alertRing1: {
    position: 'absolute',
    width: 120,
    height: 120,
    borderRadius: 60,
    borderWidth: 3,
    borderColor: 'rgba(239, 68, 68, 0.2)',
  },
  alertRing2: {
    position: 'absolute',
    width: 100,
    height: 100,
    borderRadius: 50,
    borderWidth: 3,
    borderColor: 'rgba(239, 68, 68, 0.4)',
  },
  alertIconCircle: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: '#EF4444',
    justifyContent: 'center',
    alignItems: 'center',
  },
  newOrderTitle: {
    fontSize: 28,
    fontWeight: '900',
    color: '#111827',
    marginBottom: 16,
  },
  countdownContainer: {
    alignItems: 'center',
    marginBottom: 20,
  },
  countdownLabel: {
    fontSize: 14,
    color: '#6B7280',
    marginBottom: 4,
  },
  countdownTime: {
    fontSize: 48,
    fontWeight: '800',
    color: '#EF4444',
  },
  countdownProgressBg: {
    width: 200,
    height: 6,
    backgroundColor: '#FEE2E2',
    borderRadius: 3,
    marginTop: 8,
    overflow: 'hidden',
  },
  countdownProgress: {
    height: '100%',
    backgroundColor: '#EF4444',
    borderRadius: 3,
  },
  orderSummaryCard: {
    width: '100%',
    backgroundColor: '#F9FAFB',
    borderRadius: 16,
    padding: 16,
    marginBottom: 20,
  },
  orderSummaryHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  orderSummaryId: {
    fontSize: 16,
    fontWeight: '700',
    color: '#6366F1',
  },
  orderSummaryTotal: {
    fontSize: 24,
    fontWeight: '800',
    color: '#111827',
  },
  orderSummaryCustomer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  customerAvatarLarge: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: '#EEF2FF',
    justifyContent: 'center',
    alignItems: 'center',
  },
  customerInitialLarge: {
    fontSize: 18,
    fontWeight: '700',
    color: '#6366F1',
  },
  customerDetails: {
    marginLeft: 12,
  },
  customerNameLarge: {
    fontSize: 16,
    fontWeight: '600',
    color: '#111827',
  },
  customerPhoneLarge: {
    fontSize: 14,
    color: '#6B7280',
  },
  orderSummaryItems: {
    marginBottom: 12,
  },
  itemsLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: '#6B7280',
    marginBottom: 6,
  },
  itemLine: {
    fontSize: 14,
    color: '#374151',
    marginBottom: 2,
  },
  moreItemsText: {
    fontSize: 13,
    color: '#6366F1',
    fontWeight: '600',
    marginTop: 4,
  },
  deliveryBadgeLarge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#EEF2FF',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 10,
    alignSelf: 'flex-start',
    gap: 6,
  },
  deliveryTextLarge: {
    fontSize: 13,
    fontWeight: '600',
    color: '#6366F1',
  },
  alertActions: {
    flexDirection: 'row',
    width: '100%',
    gap: 12,
  },
  rejectBtnLarge: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FEE2E2',
    paddingVertical: 16,
    borderRadius: 14,
    gap: 8,
  },
  rejectBtnTextLarge: {
    fontSize: 16,
    fontWeight: '700',
    color: '#DC2626',
  },
  acceptBtnLarge: {
    flex: 2,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#22C55E',
    paddingVertical: 16,
    borderRadius: 14,
    gap: 8,
  },
  acceptBtnTextLarge: {
    fontSize: 16,
    fontWeight: '700',
    color: '#FFFFFF',
  },
});
