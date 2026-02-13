import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  Animated,
  Dimensions,
  Modal,
  ActivityIndicator,
  TextInput,
  Image,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { useFocusEffect } from '@react-navigation/native';
import { Ionicons } from '@expo/vector-icons';
import { orderAPI } from '../../../src/utils/api';
import { useAlert } from '../../../src/context/AlertContext';
import { format } from 'date-fns';
import { OrderTimeline } from '../../../src/components/OrderTimeline';

const { width } = Dimensions.get('window');

interface OrderItem {
  product_id: string;
  name: string;
  price: number;
  quantity: number;
  image?: string;
  unavailable?: boolean;
  unavailable_reason?: string;
  adjusted_quantity?: number;
}

interface StatusCheckpoint {
  key: string;
  label: string;
  icon: string;
  description: string;
  completed: boolean;
  current: boolean;
  timestamp?: string;
}

interface NextAction {
  action: string;
  label: string;
  primary: boolean;
  destructive?: boolean;
}

export default function OrderDetailScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ id: string }>();
  const insets = useSafeAreaInsets();
  const { showAlert } = useAlert();
  
  const [order, setOrder] = useState<any>(null);
  const [orderItems, setOrderItems] = useState<OrderItem[]>([]);
  const [checkpoints, setCheckpoints] = useState<StatusCheckpoint[]>([]);
  const [nextActions, setNextActions] = useState<NextAction[]>([]);
  const [vendorCanDeliver, setVendorCanDeliver] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [showItemModal, setShowItemModal] = useState(false);
  const [selectedItem, setSelectedItem] = useState<OrderItem | null>(null);
  const [unavailableReason, setUnavailableReason] = useState('');
  const [adjustedQty, setAdjustedQty] = useState('');
  const [showTimeline, setShowTimeline] = useState(false);
  const [selectedDeliveryOption, setSelectedDeliveryOption] = useState<'carpet_genie' | 'self_delivery' | null>(null);
  const [pickedItems, setPickedItems] = useState<Set<string>>(new Set());
  
  const progressAnim = useRef(new Animated.Value(0)).current;

  // Toggle item picked status
  const toggleItemPicked = (productId: string) => {
    setPickedItems(prev => {
      const newSet = new Set(prev);
      if (newSet.has(productId)) {
        newSet.delete(productId);
      } else {
        newSet.add(productId);
      }
      return newSet;
    });
  };

  // Check if all items are picked
  const allItemsPicked = orderItems.filter(i => !i.unavailable).every(item => pickedItems.has(item.product_id));

  const loadOrderDetails = async () => {
    if (!params.id) return;
    
    try {
      const response = await orderAPI.getDetails(params.id);
      setOrder(response.data.order);
      setOrderItems(response.data.order.items || []);
      setCheckpoints(response.data.status_checkpoints);
      setNextActions(response.data.next_actions);
      setVendorCanDeliver(response.data.vendor_can_deliver);
      
      const completedCount = response.data.status_checkpoints.filter((c: StatusCheckpoint) => c.completed).length;
      const totalCount = response.data.status_checkpoints.length;
      Animated.timing(progressAnim, {
        toValue: completedCount / totalCount,
        duration: 500,
        useNativeDriver: false,
      }).start();
    } catch (error) {
      console.error('Load order details error:', error);
      showAlert({
        type: 'error',
        title: 'Error',
        message: 'Failed to load order details',
      });
    } finally {
      setLoading(false);
    }
  };

  useFocusEffect(
    useCallback(() => {
      loadOrderDetails();
      const interval = setInterval(loadOrderDetails, 10000);
      return () => clearInterval(interval);
    }, [params.id])
  );

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadOrderDetails();
    setRefreshing(false);
  }, [params.id]);

  const handleAction = async (action: string) => {
    if (!params.id) return;
    
    setActionLoading(true);
    try {
      const response = await orderAPI.executeAction(params.id, action);
      showAlert({
        type: 'success',
        title: 'Success! 🎉',
        message: response.data.message,
      });
      await loadOrderDetails();
    } catch (error: any) {
      showAlert({
        type: 'error',
        title: 'Error',
        message: error.response?.data?.detail || 'Action failed',
      });
    } finally {
      setActionLoading(false);
    }
  };

  const handleAssignDelivery = async (deliveryType: string) => {
    if (!params.id) return;
    
    setActionLoading(true);
    try {
      const response = await orderAPI.assignDelivery(params.id, deliveryType);
      showAlert({
        type: 'success',
        title: deliveryType === 'carpet_genie' ? 'Carpet Genie Assigned! 🚴' : 'Delivery Assigned!',
        message: response.data.message,
      });
      await loadOrderDetails();
    } catch (error: any) {
      showAlert({
        type: 'error',
        title: 'Error',
        message: error.response?.data?.detail || 'Failed to assign delivery',
      });
    } finally {
      setActionLoading(false);
    }
  };

  // Handle item unavailability
  const openItemManagement = (item: OrderItem) => {
    setSelectedItem(item);
    setUnavailableReason(item.unavailable_reason || '');
    setAdjustedQty(item.adjusted_quantity?.toString() || item.quantity.toString());
    setShowItemModal(true);
  };

  const handleMarkItemUnavailable = async () => {
    if (!selectedItem || !params.id) return;
    
    const updatedItems = orderItems.map(item => {
      if (item.product_id === selectedItem.product_id) {
        return {
          ...item,
          unavailable: true,
          unavailable_reason: unavailableReason || 'Item out of stock',
        };
      }
      return item;
    });
    
    setOrderItems(updatedItems);
    setShowItemModal(false);
    
    // Calculate new total
    const newTotal = updatedItems
      .filter(i => !i.unavailable)
      .reduce((sum, i) => sum + (i.price * (i.adjusted_quantity || i.quantity)), 0);
    
    // Call API to update order items
    try {
      await orderAPI.updateItems(params.id, { 
        items: updatedItems,
        adjusted_total: newTotal 
      });
      showAlert({
        type: 'info',
        title: 'Item Marked Unavailable',
        message: 'Customer will be notified about this change.',
      });
      await loadOrderDetails();
    } catch (error) {
      showAlert({
        type: 'error',
        title: 'Error',
        message: 'Failed to update item. Please try again.',
      });
    }
  };

  const handleAdjustQuantity = async () => {
    if (!selectedItem || !params.id) return;
    
    const newQty = parseInt(adjustedQty);
    if (isNaN(newQty) || newQty < 0) {
      showAlert({ type: 'error', title: 'Invalid Quantity', message: 'Please enter a valid number' });
      return;
    }
    
    const updatedItems = orderItems.map(item => {
      if (item.product_id === selectedItem.product_id) {
        return {
          ...item,
          adjusted_quantity: newQty,
          unavailable: newQty === 0,
          unavailable_reason: newQty === 0 ? 'Item out of stock' : undefined,
        };
      }
      return item;
    });
    
    setOrderItems(updatedItems);
    setShowItemModal(false);
    
    const newTotal = updatedItems
      .filter(i => !i.unavailable)
      .reduce((sum, i) => sum + (i.price * (i.adjusted_quantity || i.quantity)), 0);
    
    try {
      await orderAPI.updateItems(params.id, { 
        items: updatedItems,
        adjusted_total: newTotal 
      });
      showAlert({
        type: 'success',
        title: 'Quantity Adjusted',
        message: `${selectedItem.name} quantity updated to ${newQty}`,
      });
      await loadOrderDetails();
    } catch (error) {
      showAlert({
        type: 'error',
        title: 'Error',
        message: 'Failed to update quantity.',
      });
    }
  };

  const getStatusColor = (status: string) => {
    const colors: { [key: string]: string } = {
      pending: '#F59E0B',
      confirmed: '#3B82F6',
      preparing: '#8B5CF6',
      ready: '#22C55E',
      awaiting_pickup: '#06B6D4',
      picked_up: '#6366F1',
      out_for_delivery: '#EC4899',
      delivered: '#22C55E',
      cancelled: '#EF4444',
      rejected: '#EF4444',
    };
    return colors[status] || '#6B7280';
  };

  const getStatusLabel = (status: string) => {
    const labels: { [key: string]: string } = {
      pending: 'New Order',
      confirmed: 'Accepted',
      preparing: 'Preparing',
      ready: 'Ready',
      awaiting_pickup: 'Awaiting Pickup',
      picked_up: 'Picked Up',
      out_for_delivery: 'Out for Delivery',
      delivered: 'Delivered',
      cancelled: 'Cancelled',
      rejected: 'Rejected',
    };
    return labels[status] || status;
  };

  // Calculate totals
  const availableItems = orderItems.filter(i => !i.unavailable);
  const unavailableItems = orderItems.filter(i => i.unavailable);
  const currentTotal = availableItems.reduce((sum, i) => sum + (i.price * (i.adjusted_quantity || i.quantity)), 0);
  const originalTotal = order?.total_amount || 0;
  const hasChanges = unavailableItems.length > 0 || currentTotal !== originalTotal;

  if (loading) {
    return (
      <View style={[styles.container, styles.loadingContainer, { paddingTop: insets.top }]}>
        <ActivityIndicator size="large" color="#6366F1" />
        <Text style={styles.loadingText}>Loading order...</Text>
      </View>
    );
  }

  if (!order) {
    return (
      <View style={[styles.container, styles.errorContainer, { paddingTop: insets.top }]}>
        <Ionicons name="alert-circle" size={64} color="#EF4444" />
        <Text style={styles.errorTitle}>Order Not Found</Text>
        <TouchableOpacity style={styles.backButton} onPress={() => router.back()}>
          <Text style={styles.backButtonText}>Go Back</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const statusColor = getStatusColor(order.status);

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.backBtn} onPress={() => router.back()}>
          <Ionicons name="arrow-back" size={24} color="#374151" />
        </TouchableOpacity>
        <View style={styles.headerContent}>
          <Text style={styles.orderNumber}>Order #{order.order_id?.slice(-6).toUpperCase()}</Text>
          <View style={[styles.statusBadge, { backgroundColor: statusColor + '20' }]}>
            <View style={[styles.statusDot, { backgroundColor: statusColor }]} />
            <Text style={[styles.statusText, { color: statusColor }]}>
              {getStatusLabel(order.status)}
            </Text>
          </View>
        </View>
        <TouchableOpacity style={styles.refreshBtn} onPress={onRefresh}>
          <Ionicons name="refresh" size={22} color="#6366F1" />
        </TouchableOpacity>
      </View>

      <ScrollView
        style={styles.scrollView}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={['#6366F1']} />
        }
      >
        {/* Customer Info Card */}
        <View style={styles.customerCard}>
          <View style={styles.customerRow}>
            <View style={styles.customerAvatar}>
              <Text style={styles.customerInitial}>
                {(order.customer_name || 'C')[0].toUpperCase()}
              </Text>
            </View>
            <View style={styles.customerInfo}>
              <Text style={styles.customerName}>{order.customer_name || 'Customer'}</Text>
              <Text style={styles.customerPhone}>{order.customer_phone || 'No phone'}</Text>
            </View>
            <TouchableOpacity style={styles.callBtn}>
              <Ionicons name="call" size={18} color="#22C55E" />
            </TouchableOpacity>
          </View>
          {order.delivery_type !== 'self_pickup' && order.delivery_address && (
            <View style={styles.addressRow}>
              <Ionicons name="location" size={16} color="#6B7280" />
              <Text style={styles.addressText}>{order.delivery_address?.address || 'No address'}</Text>
            </View>
          )}
          {order.delivery_type === 'self_pickup' && (
            <View style={styles.pickupBadge}>
              <Ionicons name="storefront" size={14} color="#6366F1" />
              <Text style={styles.pickupText}>Customer will pick up</Text>
            </View>
          )}
        </View>

        {/* ORDER ITEMS - PRIMARY SECTION */}
        <View style={styles.itemsCard}>
          <View style={styles.itemsHeader}>
            <View style={styles.itemsHeaderLeft}>
              <Text style={styles.sectionTitle}>
                {order.status === 'preparing' ? 'Packing List' : 'Order Items'}
              </Text>
              <View style={[
                styles.itemCountBadge,
                order.status === 'preparing' && pickedItems.size === availableItems.length && styles.itemCountBadgeComplete
              ]}>
                <Text style={[
                  styles.itemCountText,
                  order.status === 'preparing' && pickedItems.size === availableItems.length && styles.itemCountTextComplete
                ]}>
                  {order.status === 'preparing' 
                    ? `${pickedItems.size}/${availableItems.length} picked`
                    : `${orderItems.length} items`
                  }
                </Text>
              </View>
            </View>
            {order.status === 'confirmed' && (
              <View style={styles.editHint}>
                <Ionicons name="create-outline" size={14} color="#6366F1" />
                <Text style={styles.editHintText}>Tap item to edit</Text>
              </View>
            )}
            {order.status === 'preparing' && (
              <View style={styles.packingHint}>
                <Ionicons name="checkbox" size={14} color="#22C55E" />
                <Text style={styles.packingHintText}>Tap to confirm</Text>
              </View>
            )}
          </View>

          {/* Table Header for Preparing Status */}
          {order.status === 'preparing' && (
            <View style={styles.tableHeader}>
              <Text style={[styles.tableHeaderText, { width: 50, textAlign: 'center' }]}>Done</Text>
              <Text style={[styles.tableHeaderText, { flex: 1 }]}>Item</Text>
              <Text style={[styles.tableHeaderText, { width: 70, textAlign: 'right' }]}>Price</Text>
              <Text style={[styles.tableHeaderText, { width: 40, textAlign: 'center' }]}>Edit</Text>
            </View>
          )}

          {/* Available Items - Different layout for preparing */}
          {order.status === 'preparing' ? (
            // Packing List Layout
            availableItems.map((item, index) => {
              const isPicked = pickedItems.has(item.product_id);
              return (
                <View 
                  key={item.product_id}
                  style={[
                    styles.packingRow,
                    index < availableItems.length - 1 && styles.packingRowBorder,
                    isPicked && styles.packingRowPicked
                  ]}
                >
                  {/* Checkbox - Tap to mark picked */}
                  <TouchableOpacity 
                    style={styles.packingCheckCol}
                    onPress={() => toggleItemPicked(item.product_id)}
                  >
                    <View style={[
                      styles.packingCheckbox,
                      isPicked && styles.packingCheckboxChecked
                    ]}>
                      {isPicked && (
                        <Ionicons name="checkmark" size={18} color="#FFFFFF" />
                      )}
                    </View>
                  </TouchableOpacity>

                  {/* Item Column */}
                  <View style={styles.packingItemCol}>
                    <View style={styles.packingQtyBadge}>
                      <Text style={styles.packingQtyText}>
                        {item.adjusted_quantity !== undefined ? item.adjusted_quantity : item.quantity}x
                      </Text>
                    </View>
                    <View style={styles.packingItemDetails}>
                      <Text style={[
                        styles.packingItemName,
                        isPicked && styles.packingItemNamePicked
                      ]}>
                        {item.name}
                      </Text>
                      {item.adjusted_quantity !== undefined && item.adjusted_quantity !== item.quantity && (
                        <Text style={styles.packingItemAdjusted}>
                          Originally: {item.quantity}
                        </Text>
                      )}
                    </View>
                  </View>
                  
                  {/* Price Column */}
                  <View style={styles.packingPriceCol}>
                    <Text style={[
                      styles.packingPrice,
                      isPicked && styles.packingPricePicked
                    ]}>
                      ₹{((item.adjusted_quantity || item.quantity) * item.price).toFixed(0)}
                    </Text>
                  </View>
                  
                  {/* Edit Button - For missing/partial items */}
                  <TouchableOpacity 
                    style={styles.packingEditBtn}
                    onPress={() => openItemManagement(item)}
                  >
                    <Ionicons name="create-outline" size={18} color="#6366F1" />
                  </TouchableOpacity>
                </View>
              );
            })
          ) : (
            // Regular Layout for other statuses
            availableItems.map((item, index) => (
              <TouchableOpacity
                key={item.product_id}
                style={[
                  styles.itemRow,
                  index < availableItems.length - 1 && styles.itemRowBorder
                ]}
                onPress={() => {
                  if (order.status === 'confirmed') {
                    openItemManagement(item);
                  }
                }}
                activeOpacity={order.status === 'confirmed' ? 0.7 : 1}
              >
                <View style={styles.itemQtyBadge}>
                  <Text style={styles.itemQtyText}>
                    {item.adjusted_quantity !== undefined ? item.adjusted_quantity : item.quantity}x
                  </Text>
                </View>
                <View style={styles.itemDetails}>
                  <Text style={styles.itemName}>{item.name}</Text>
                  <Text style={styles.itemPrice}>₹{item.price} each</Text>
                  {item.adjusted_quantity !== undefined && item.adjusted_quantity !== item.quantity && (
                    <View style={styles.adjustedBadge}>
                      <Ionicons name="pencil" size={10} color="#F59E0B" />
                      <Text style={styles.adjustedText}>
                        Changed from {item.quantity}
                      </Text>
                    </View>
                  )}
                </View>
                <Text style={styles.itemTotal}>
                  ₹{((item.adjusted_quantity || item.quantity) * item.price).toFixed(0)}
                </Text>
                {order.status === 'confirmed' && (
                  <Ionicons name="chevron-forward" size={18} color="#D1D5DB" />
                )}
              </TouchableOpacity>
            ))
          )}

          {/* All Items Picked Confirmation */}
          {order.status === 'preparing' && allItemsPicked && (
            <View style={styles.allPickedBanner}>
              <Ionicons name="checkmark-circle" size={20} color="#22C55E" />
              <Text style={styles.allPickedText}>All items picked! Ready to pack.</Text>
            </View>
          )}

          {/* Unavailable Items */}
          {unavailableItems.length > 0 && (
            <View style={styles.unavailableSection}>
              <View style={styles.unavailableHeader}>
                <Ionicons name="alert-circle" size={16} color="#DC2626" />
                <Text style={styles.unavailableTitle}>Unavailable Items</Text>
              </View>
              {unavailableItems.map((item) => (
                <View key={item.product_id} style={styles.unavailableItem}>
                  <View style={styles.unavailableItemLeft}>
                    <Text style={styles.unavailableItemName}>{item.quantity}x {item.name}</Text>
                    <Text style={styles.unavailableReason}>
                      {item.unavailable_reason || 'Not available'}
                    </Text>
                  </View>
                  <Text style={styles.unavailablePrice}>-₹{(item.quantity * item.price).toFixed(0)}</Text>
                </View>
              ))}
            </View>
          )}

          {/* Order Totals */}
          <View style={styles.totalsSection}>
            <View style={styles.totalRow}>
              <Text style={styles.totalLabel}>Subtotal</Text>
              <Text style={styles.totalValue}>₹{currentTotal.toFixed(0)}</Text>
            </View>
            {order.delivery_fee > 0 && (
              <View style={styles.totalRow}>
                <Text style={styles.totalLabel}>Delivery Fee</Text>
                <Text style={styles.totalValue}>₹{order.delivery_fee}</Text>
              </View>
            )}
            {hasChanges && (
              <View style={styles.totalRow}>
                <Text style={[styles.totalLabel, { color: '#DC2626' }]}>Adjustment</Text>
                <Text style={[styles.totalValue, { color: '#DC2626' }]}>
                  -₹{(originalTotal - currentTotal - (order.delivery_fee || 0)).toFixed(0)}
                </Text>
              </View>
            )}
            <View style={[styles.totalRow, styles.grandTotalRow]}>
              <Text style={styles.grandTotalLabel}>Total</Text>
              <Text style={styles.grandTotalValue}>
                ₹{(currentTotal + (order.delivery_fee || 0)).toFixed(0)}
              </Text>
            </View>
          </View>

          {/* Special Instructions */}
          {order.special_instructions && (
            <View style={styles.instructionsBox}>
              <View style={styles.instructionsHeader}>
                <Ionicons name="document-text" size={16} color="#6366F1" />
                <Text style={styles.instructionsTitle}>Special Instructions</Text>
              </View>
              <Text style={styles.instructionsText}>{order.special_instructions}</Text>
            </View>
          )}
        </View>

        {/* Delivery Assignment Section */}
        {(order.status === 'ready' || order.status === 'preparing' || order.status === 'confirmed') && 
         order.delivery_type !== 'self_pickup' && (
          <View style={styles.deliveryCard}>
            <View style={styles.deliveryHeader}>
              <View style={styles.deliveryIconBg}>
                <Ionicons name="bicycle" size={24} color="#22C55E" />
              </View>
              <View style={styles.deliveryHeaderContent}>
                <Text style={styles.deliveryTitle}>Delivery</Text>
                <Text style={styles.deliverySubtitle}>
                  {order.assigned_agent_id 
                    ? `Assigned to ${order.agent_name || 'Carpet Genie'}`
                    : 'Select delivery method'}
                </Text>
              </View>
            </View>
            
            {!order.assigned_agent_id && order.delivery_method !== 'self' && order.status === 'ready' && (
              <>
                <View style={styles.deliveryOptions}>
                  {/* Carpet Genie Option */}
                  <TouchableOpacity 
                    style={[
                      styles.deliveryOptionBtn, 
                      styles.deliveryOptionBtnGenie,
                      !vendorCanDeliver && styles.deliveryOptionBtnRecommended,
                      selectedDeliveryOption === 'carpet_genie' && styles.deliveryOptionBtnSelected
                    ]}
                    onPress={() => setSelectedDeliveryOption('carpet_genie')}
                    disabled={actionLoading}
                  >
                    <View style={[
                      styles.radioCircle,
                      selectedDeliveryOption === 'carpet_genie' && styles.radioCircleSelected
                    ]}>
                      {selectedDeliveryOption === 'carpet_genie' && (
                        <View style={styles.radioInner} />
                      )}
                    </View>
                    <View style={[styles.deliveryOptionIcon, { backgroundColor: '#DCFCE7' }]}>
                      <Ionicons name="bicycle" size={20} color="#22C55E" />
                    </View>
                    <View style={styles.deliveryOptionContent}>
                      <Text style={styles.deliveryOptionTitle}>Carpet Genie</Text>
                      <Text style={styles.deliveryOptionSubtitle}>
                        {!vendorCanDeliver ? 'Recommended for you' : 'Partner delivery'}
                      </Text>
                    </View>
                    {!vendorCanDeliver && (
                      <View style={styles.recommendedBadge}>
                        <Ionicons name="star" size={12} color="#F59E0B" />
                      </View>
                    )}
                  </TouchableOpacity>

                  {/* Shop Delivery Option */}
                  <TouchableOpacity 
                    style={[
                      styles.deliveryOptionBtn,
                      !vendorCanDeliver && styles.deliveryOptionBtnSecondary,
                      selectedDeliveryOption === 'self_delivery' && styles.deliveryOptionBtnSelected
                    ]}
                    onPress={() => setSelectedDeliveryOption('self_delivery')}
                    disabled={actionLoading}
                  >
                    <View style={[
                      styles.radioCircle,
                      selectedDeliveryOption === 'self_delivery' && styles.radioCircleSelected
                    ]}>
                      {selectedDeliveryOption === 'self_delivery' && (
                        <View style={styles.radioInner} />
                      )}
                    </View>
                    <View style={[styles.deliveryOptionIcon, { backgroundColor: vendorCanDeliver ? '#DBEAFE' : '#F3F4F6' }]}>
                      <Ionicons name="car" size={20} color={vendorCanDeliver ? '#3B82F6' : '#6B7280'} />
                    </View>
                    <View style={styles.deliveryOptionContent}>
                      <Text style={[
                        styles.deliveryOptionTitle,
                        !vendorCanDeliver && styles.deliveryOptionTitleSecondary
                      ]}>
                        {vendorCanDeliver ? 'Own Delivery' : 'Shop Delivery'}
                      </Text>
                      <Text style={styles.deliveryOptionSubtitle}>
                        {vendorCanDeliver ? 'Use your service' : 'Deliver it yourself'}
                      </Text>
                    </View>
                  </TouchableOpacity>
                </View>

                {/* Assign Delivery Button */}
                <TouchableOpacity 
                  style={[
                    styles.assignDeliveryBtn,
                    !selectedDeliveryOption && styles.assignDeliveryBtnDisabled
                  ]}
                  onPress={() => {
                    if (selectedDeliveryOption) {
                      handleAssignDelivery(selectedDeliveryOption);
                    }
                  }}
                  disabled={!selectedDeliveryOption || actionLoading}
                >
                  {actionLoading ? (
                    <ActivityIndicator size="small" color="#FFFFFF" />
                  ) : (
                    <>
                      <Ionicons 
                        name="checkmark-circle" 
                        size={20} 
                        color={selectedDeliveryOption ? '#FFFFFF' : '#9CA3AF'} 
                      />
                      <Text style={[
                        styles.assignDeliveryBtnText,
                        !selectedDeliveryOption && styles.assignDeliveryBtnTextDisabled
                      ]}>
                        Assign Delivery
                      </Text>
                    </>
                  )}
                </TouchableOpacity>
              </>
            )}
          </View>
        )}

        {/* Genie/Agent Details Card - Shows when agent is assigned */}
        {order.assigned_agent_id && order.delivery_method === 'carpet_genie' && (
          <View style={styles.genieCard}>
            <View style={styles.genieHeader}>
              <View style={styles.genieAvatarContainer}>
                {order.agent_photo ? (
                  <Image 
                    source={{ uri: order.agent_photo }} 
                    style={styles.genieAvatar}
                  />
                ) : (
                  <View style={styles.genieAvatarPlaceholder}>
                    <Ionicons name="person" size={24} color="#22C55E" />
                  </View>
                )}
              </View>
              <View style={styles.genieInfo}>
                <Text style={styles.genieName}>{order.agent_name || 'Carpet Genie'}</Text>
                <View style={styles.genieRatingRow}>
                  <Ionicons name="star" size={12} color="#F59E0B" />
                  <Text style={styles.genieRating}>{order.agent_rating?.toFixed(1) || '4.8'}</Text>
                  <Text style={styles.genieVehicle}>
                    • {order.agent_vehicle_type === 'bike' ? '🏍️ Bike' : '🛵 Scooter'}
                  </Text>
                </View>
              </View>
              <TouchableOpacity 
                style={styles.genieCallBtn}
                onPress={() => {
                  showAlert({
                    type: 'info',
                    title: 'Call Agent',
                    message: `Call ${order.agent_name} at ${order.agent_phone}`,
                  });
                }}
              >
                <Ionicons name="call" size={18} color="#FFFFFF" />
              </TouchableOpacity>
            </View>

            {/* Agent Phone */}
            {order.agent_phone && (
              <View style={styles.geniePhoneRow}>
                <Ionicons name="call-outline" size={14} color="#6B7280" />
                <Text style={styles.geniePhone}>{order.agent_phone}</Text>
              </View>
            )}
          </View>
        )}

        {/* Live Delivery Status - Shows when in delivery */}
        {(order.delivery_method === 'carpet_genie' || order.delivery_type === 'agent_delivery') &&
         order.assigned_agent_id &&
         ['awaiting_pickup', 'picked_up', 'out_for_delivery'].includes(order.status) && (
          <View style={styles.liveStatusCard}>
            <View style={styles.liveStatusIcon}>
              <Ionicons name="bicycle" size={20} color="#22C55E" />
            </View>
            <View style={styles.liveStatusContent}>
              <Text style={styles.liveStatusTitle}>
                {order.status === 'awaiting_pickup' && 'Waiting for Pickup'}
                {order.status === 'picked_up' && 'Order Picked Up'}
                {order.status === 'out_for_delivery' && 'On The Way'}
              </Text>
              <Text style={styles.liveStatusSubtitle}>
                {order.agent_name || 'Genie'} is handling delivery
              </Text>
            </View>
            <View style={styles.liveBadge}>
              <View style={styles.liveBadgeDot} />
              <Text style={styles.liveBadgeText}>LIVE</Text>
            </View>
          </View>
        )}

        {/* Status Timeline - Collapsible */}
        <TouchableOpacity 
          style={styles.timelineToggle}
          onPress={() => setShowTimeline(!showTimeline)}
        >
          <View style={styles.timelineToggleLeft}>
            <Ionicons name="git-branch" size={18} color="#6366F1" />
            <Text style={styles.timelineToggleText}>Order Timeline</Text>
          </View>
          <View style={styles.timelineProgress}>
            <Text style={styles.timelineProgressText}>
              {Math.round((checkpoints.filter(c => c.completed).length / checkpoints.length) * 100)}%
            </Text>
            <Ionicons 
              name={showTimeline ? "chevron-up" : "chevron-down"} 
              size={18} 
              color="#6B7280" 
            />
          </View>
        </TouchableOpacity>

        {showTimeline && (
          <View style={styles.checkpointsCard}>
            {checkpoints.map((checkpoint, index) => (
              <View key={checkpoint.key} style={styles.checkpointRow}>
                {index > 0 && (
                  <View style={[
                    styles.connectorLine,
                    checkpoint.completed && styles.connectorLineCompleted
                  ]} />
                )}
                
                <View style={[
                  styles.checkpointCircle,
                  checkpoint.completed && styles.checkpointCircleCompleted,
                  checkpoint.current && styles.checkpointCircleCurrent,
                ]}>
                  {checkpoint.completed ? (
                    <Ionicons name="checkmark" size={14} color="#FFFFFF" />
                  ) : (
                    <Ionicons 
                      name={checkpoint.icon as any} 
                      size={14} 
                      color={checkpoint.current ? '#6366F1' : '#9CA3AF'} 
                    />
                  )}
                </View>
                
                <View style={styles.checkpointContent}>
                  <Text style={[
                    styles.checkpointLabel,
                    checkpoint.completed && styles.checkpointLabelCompleted,
                    checkpoint.current && styles.checkpointLabelCurrent,
                  ]}>
                    {checkpoint.label}
                  </Text>
                  {checkpoint.timestamp && (
                    <Text style={styles.checkpointTime}>
                      {format(new Date(checkpoint.timestamp), 'h:mm a')}
                    </Text>
                  )}
                </View>
              </View>
            ))}
          </View>
        )}

        <View style={{ height: 120 }} />
      </ScrollView>

      {/* Bottom Action Buttons */}
      {nextActions.length > 0 && (
        <View style={[styles.bottomActions, { paddingBottom: Math.max(insets.bottom, 16) }]}>
          {nextActions.map((action, index) => (
            <TouchableOpacity
              key={action.action}
              style={[
                styles.actionBtn,
                action.primary && styles.actionBtnPrimary,
                action.destructive && styles.actionBtnDestructive,
                index > 0 && { marginLeft: 12 },
              ]}
              onPress={() => handleAction(action.action)}
              disabled={actionLoading}
            >
              {actionLoading ? (
                <ActivityIndicator size="small" color={action.primary ? '#FFFFFF' : '#6366F1'} />
              ) : (
                <Text style={[
                  styles.actionBtnText,
                  action.primary && styles.actionBtnTextPrimary,
                  action.destructive && styles.actionBtnTextDestructive,
                ]}>
                  {action.label}
                </Text>
              )}
            </TouchableOpacity>
          ))}
        </View>
      )}

      {/* Carpet Genie Status Bar - REMOVED - now inline in the scroll view */}

      {/* Item Management Modal */}
      <Modal
        visible={showItemModal}
        transparent
        animationType="slide"
        onRequestClose={() => setShowItemModal(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={[styles.modalContent, { paddingBottom: insets.bottom + 20 }]}>
            <View style={styles.modalHandle} />
            
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Manage Item</Text>
              <TouchableOpacity onPress={() => setShowItemModal(false)}>
                <Ionicons name="close" size={24} color="#6B7280" />
              </TouchableOpacity>
            </View>

            {selectedItem && (
              <>
                <View style={styles.selectedItemCard}>
                  <Text style={styles.selectedItemName}>{selectedItem.name}</Text>
                  <Text style={styles.selectedItemDetails}>
                    {selectedItem.quantity} × ₹{selectedItem.price} = ₹{selectedItem.quantity * selectedItem.price}
                  </Text>
                </View>

                {/* Adjust Quantity Section */}
                <View style={styles.modalSection}>
                  <Text style={styles.modalSectionTitle}>Adjust Quantity</Text>
                  <Text style={styles.modalSectionDesc}>
                    If partial stock is available, adjust the quantity
                  </Text>
                  <View style={styles.qtyInputRow}>
                    <TouchableOpacity 
                      style={styles.qtyBtn}
                      onPress={() => setAdjustedQty(Math.max(0, parseInt(adjustedQty || '0') - 1).toString())}
                    >
                      <Ionicons name="remove" size={20} color="#6366F1" />
                    </TouchableOpacity>
                    <TextInput
                      style={styles.qtyInput}
                      value={adjustedQty}
                      onChangeText={setAdjustedQty}
                      keyboardType="numeric"
                      maxLength={3}
                    />
                    <TouchableOpacity 
                      style={styles.qtyBtn}
                      onPress={() => setAdjustedQty((parseInt(adjustedQty || '0') + 1).toString())}
                    >
                      <Ionicons name="add" size={20} color="#6366F1" />
                    </TouchableOpacity>
                  </View>
                  <TouchableOpacity 
                    style={styles.adjustQtyBtn}
                    onPress={handleAdjustQuantity}
                  >
                    <Text style={styles.adjustQtyBtnText}>Update Quantity</Text>
                  </TouchableOpacity>
                </View>

                {/* Mark Unavailable Section */}
                <View style={styles.modalSection}>
                  <Text style={[styles.modalSectionTitle, { color: '#DC2626' }]}>
                    Mark as Unavailable
                  </Text>
                  <Text style={styles.modalSectionDesc}>
                    Item is completely out of stock or cannot be fulfilled
                  </Text>
                  <TextInput
                    style={styles.reasonInput}
                    placeholder="Reason (optional): e.g., Out of stock, Damaged"
                    placeholderTextColor="#9CA3AF"
                    value={unavailableReason}
                    onChangeText={setUnavailableReason}
                  />
                  <TouchableOpacity 
                    style={styles.unavailableBtn}
                    onPress={handleMarkItemUnavailable}
                  >
                    <Ionicons name="close-circle" size={18} color="#FFFFFF" />
                    <Text style={styles.unavailableBtnText}>Mark Item Unavailable</Text>
                  </TouchableOpacity>
                </View>
              </>
            )}
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F8FAFC',
  },
  loadingContainer: {
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 12,
    fontSize: 14,
    color: '#6B7280',
  },
  errorContainer: {
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  errorTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#374151',
    marginTop: 16,
  },
  backButton: {
    marginTop: 16,
    paddingVertical: 10,
    paddingHorizontal: 24,
    backgroundColor: '#6366F1',
    borderRadius: 8,
  },
  backButtonText: {
    color: '#FFFFFF',
    fontWeight: '600',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  backBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#F3F4F6',
    justifyContent: 'center',
    alignItems: 'center',
  },
  headerContent: {
    flex: 1,
    marginLeft: 12,
  },
  orderNumber: {
    fontSize: 18,
    fontWeight: '700',
    color: '#111827',
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    alignSelf: 'flex-start',
    marginTop: 4,
  },
  statusDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    marginRight: 6,
  },
  statusText: {
    fontSize: 11,
    fontWeight: '700',
  },
  refreshBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#EEF2FF',
    justifyContent: 'center',
    alignItems: 'center',
  },
  scrollView: {
    flex: 1,
  },
  // Customer Card
  customerCard: {
    backgroundColor: '#FFFFFF',
    marginHorizontal: 16,
    marginTop: 16,
    padding: 16,
    borderRadius: 16,
  },
  customerRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  customerAvatar: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#EEF2FF',
    justifyContent: 'center',
    alignItems: 'center',
  },
  customerInitial: {
    fontSize: 18,
    fontWeight: '700',
    color: '#6366F1',
  },
  customerInfo: {
    flex: 1,
    marginLeft: 12,
  },
  customerName: {
    fontSize: 16,
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
    borderRadius: 20,
    backgroundColor: '#DCFCE7',
    justifyContent: 'center',
    alignItems: 'center',
  },
  addressRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#F3F4F6',
  },
  addressText: {
    flex: 1,
    marginLeft: 8,
    fontSize: 13,
    color: '#4B5563',
    lineHeight: 18,
  },
  pickupBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#EEF2FF',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
    marginTop: 12,
    gap: 6,
    alignSelf: 'flex-start',
  },
  pickupText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#6366F1',
  },
  // Items Card
  itemsCard: {
    backgroundColor: '#FFFFFF',
    marginHorizontal: 16,
    marginTop: 12,
    padding: 16,
    borderRadius: 16,
  },
  itemsHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  itemsHeaderLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#111827',
  },
  itemCountBadge: {
    backgroundColor: '#EEF2FF',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  itemCountText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#6366F1',
  },
  editHint: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  editHintText: {
    fontSize: 12,
    color: '#6366F1',
  },
  // Item Count Badge Complete State
  itemCountBadgeComplete: {
    backgroundColor: '#DCFCE7',
  },
  itemCountTextComplete: {
    color: '#22C55E',
  },
  // Packing Hint
  packingHint: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  packingHintText: {
    fontSize: 12,
    color: '#22C55E',
  },
  // Table Header
  tableHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingBottom: 10,
    marginBottom: 4,
    borderBottomWidth: 2,
    borderBottomColor: '#E5E7EB',
  },
  tableHeaderText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#9CA3AF',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  // Packing Row
  packingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 14,
  },
  packingRowBorder: {
    borderBottomWidth: 1,
    borderBottomColor: '#F3F4F6',
  },
  packingRowPicked: {
    backgroundColor: '#F0FDF4',
    marginHorizontal: -16,
    paddingHorizontal: 16,
  },
  packingItemCol: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
  },
  packingQtyBadge: {
    minWidth: 32,
    height: 28,
    paddingHorizontal: 6,
    borderRadius: 6,
    backgroundColor: '#F3F4F6',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 10,
  },
  packingQtyText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#374151',
  },
  packingItemDetails: {
    flex: 1,
  },
  packingItemName: {
    fontSize: 14,
    fontWeight: '600',
    color: '#111827',
  },
  packingItemNamePicked: {
    color: '#22C55E',
    textDecorationLine: 'line-through',
  },
  packingPriceCol: {
    width: 70,
    alignItems: 'flex-end',
  },
  packingPrice: {
    fontSize: 14,
    fontWeight: '600',
    color: '#374151',
  },
  packingPricePicked: {
    color: '#22C55E',
  },
  packingCheckCol: {
    width: 50,
    alignItems: 'center',
  },
  packingCheckbox: {
    width: 28,
    height: 28,
    borderRadius: 8,
    borderWidth: 2,
    borderColor: '#D1D5DB',
    backgroundColor: '#FFFFFF',
    justifyContent: 'center',
    alignItems: 'center',
  },
  packingCheckboxChecked: {
    backgroundColor: '#22C55E',
    borderColor: '#22C55E',
  },
  packingEditBtn: {
    width: 40,
    height: 36,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#EEF2FF',
    borderRadius: 8,
  },
  packingItemAdjusted: {
    fontSize: 11,
    color: '#F59E0B',
    marginTop: 2,
  },
  // All Picked Banner
  allPickedBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#DCFCE7',
    marginTop: 16,
    padding: 12,
    borderRadius: 10,
    gap: 8,
  },
  allPickedText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#166534',
  },
  itemRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
  },
  itemRowBorder: {
    borderBottomWidth: 1,
    borderBottomColor: '#F3F4F6',
  },
  itemQtyBadge: {
    width: 36,
    height: 36,
    borderRadius: 8,
    backgroundColor: '#F3F4F6',
    justifyContent: 'center',
    alignItems: 'center',
  },
  itemQtyText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#374151',
  },
  itemDetails: {
    flex: 1,
    marginLeft: 12,
  },
  itemName: {
    fontSize: 14,
    fontWeight: '600',
    color: '#111827',
  },
  itemPrice: {
    fontSize: 12,
    color: '#6B7280',
    marginTop: 2,
  },
  adjustedBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginTop: 4,
  },
  adjustedText: {
    fontSize: 11,
    color: '#F59E0B',
    fontWeight: '500',
  },
  itemTotal: {
    fontSize: 14,
    fontWeight: '700',
    color: '#111827',
    marginRight: 8,
  },
  // Unavailable Section
  unavailableSection: {
    backgroundColor: '#FEF2F2',
    borderRadius: 12,
    padding: 12,
    marginTop: 12,
  },
  unavailableHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
  },
  unavailableTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: '#DC2626',
  },
  unavailableItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
    borderTopWidth: 1,
    borderTopColor: '#FECACA',
  },
  unavailableItemLeft: {
    flex: 1,
  },
  unavailableItemName: {
    fontSize: 13,
    color: '#991B1B',
    textDecorationLine: 'line-through',
  },
  unavailableReason: {
    fontSize: 11,
    color: '#DC2626',
    marginTop: 2,
  },
  unavailablePrice: {
    fontSize: 13,
    fontWeight: '600',
    color: '#DC2626',
  },
  // Totals
  totalsSection: {
    marginTop: 16,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: '#E5E7EB',
  },
  totalRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  totalLabel: {
    fontSize: 14,
    color: '#6B7280',
  },
  totalValue: {
    fontSize: 14,
    fontWeight: '500',
    color: '#374151',
  },
  grandTotalRow: {
    marginTop: 8,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#E5E7EB',
  },
  grandTotalLabel: {
    fontSize: 16,
    fontWeight: '700',
    color: '#111827',
  },
  grandTotalValue: {
    fontSize: 20,
    fontWeight: '800',
    color: '#111827',
  },
  // Instructions
  instructionsBox: {
    backgroundColor: '#F0F9FF',
    borderRadius: 12,
    padding: 12,
    marginTop: 16,
  },
  instructionsHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
  },
  instructionsTitle: {
    fontSize: 13,
    fontWeight: '600',
    color: '#0369A1',
  },
  instructionsText: {
    fontSize: 13,
    color: '#0C4A6E',
    lineHeight: 18,
  },
  // Delivery Card
  deliveryCard: {
    backgroundColor: '#FFFFFF',
    marginHorizontal: 16,
    marginTop: 12,
    padding: 16,
    borderRadius: 16,
  },
  deliveryHeader: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  deliveryIconBg: {
    width: 48,
    height: 48,
    borderRadius: 14,
    backgroundColor: '#DCFCE7',
    justifyContent: 'center',
    alignItems: 'center',
  },
  deliveryHeaderContent: {
    marginLeft: 12,
  },
  deliveryTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#111827',
  },
  deliverySubtitle: {
    fontSize: 13,
    color: '#6B7280',
    marginTop: 2,
  },
  deliveryOptions: {
    marginTop: 16,
    gap: 10,
  },
  deliveryOptionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F9FAFB',
    padding: 14,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  deliveryOptionBtnGenie: {
    borderColor: '#22C55E',
    backgroundColor: '#F0FDF4',
  },
  deliveryOptionIcon: {
    width: 40,
    height: 40,
    borderRadius: 10,
    justifyContent: 'center',
    alignItems: 'center',
  },
  deliveryOptionContent: {
    flex: 1,
    marginLeft: 12,
  },
  deliveryOptionTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#111827',
  },
  deliveryOptionSubtitle: {
    fontSize: 12,
    color: '#6B7280',
  },
  deliveryOptionBtnRecommended: {
    borderWidth: 2,
    borderColor: '#22C55E',
    backgroundColor: '#F0FDF4',
  },
  deliveryOptionBtnSecondary: {
    backgroundColor: '#FAFAFA',
    borderColor: '#E5E7EB',
    borderStyle: 'dashed',
  },
  deliveryOptionTitleSecondary: {
    color: '#6B7280',
  },
  recommendedBadge: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: '#FEF3C7',
    justifyContent: 'center',
    alignItems: 'center',
  },
  deliveryOptionBtnSelected: {
    borderColor: '#6366F1',
    borderWidth: 2,
    backgroundColor: '#EEF2FF',
  },
  radioCircle: {
    width: 22,
    height: 22,
    borderRadius: 11,
    borderWidth: 2,
    borderColor: '#D1D5DB',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 10,
  },
  radioCircleSelected: {
    borderColor: '#6366F1',
  },
  radioInner: {
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: '#6366F1',
  },
  assignDeliveryBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#6366F1',
    marginTop: 16,
    paddingVertical: 14,
    borderRadius: 12,
    gap: 8,
  },
  assignDeliveryBtnDisabled: {
    backgroundColor: '#E5E7EB',
  },
  assignDeliveryBtnText: {
    fontSize: 15,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  assignDeliveryBtnTextDisabled: {
    color: '#9CA3AF',
  },
  // Genie/Agent Details Card
  genieCard: {
    backgroundColor: '#FFFFFF',
    marginHorizontal: 16,
    marginTop: 12,
    padding: 14,
    borderRadius: 14,
    borderWidth: 2,
    borderColor: '#22C55E',
  },
  genieHeader: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  genieAvatarContainer: {
    position: 'relative',
  },
  genieAvatar: {
    width: 48,
    height: 48,
    borderRadius: 24,
    borderWidth: 2,
    borderColor: '#22C55E',
  },
  genieAvatarPlaceholder: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: '#DCFCE7',
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 2,
    borderColor: '#22C55E',
  },
  genieInfo: {
    flex: 1,
    marginLeft: 12,
  },
  genieName: {
    fontSize: 16,
    fontWeight: '700',
    color: '#111827',
  },
  genieRatingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 2,
    gap: 4,
  },
  genieRating: {
    fontSize: 13,
    fontWeight: '600',
    color: '#374151',
  },
  genieVehicle: {
    fontSize: 13,
    color: '#6B7280',
  },
  genieCallBtn: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: '#22C55E',
    justifyContent: 'center',
    alignItems: 'center',
  },
  geniePhoneRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 10,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: '#E5E7EB',
    gap: 6,
  },
  geniePhone: {
    fontSize: 13,
    color: '#374151',
  },
  // Live Status Card (inline)
  liveStatusCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F0FDF4',
    marginHorizontal: 16,
    marginTop: 10,
    padding: 14,
    borderRadius: 14,
    borderWidth: 1.5,
    borderColor: '#86EFAC',
  },
  liveStatusIcon: {
    width: 40,
    height: 40,
    borderRadius: 12,
    backgroundColor: '#DCFCE7',
    justifyContent: 'center',
    alignItems: 'center',
  },
  liveStatusContent: {
    flex: 1,
    marginLeft: 12,
  },
  liveStatusTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: '#166534',
  },
  liveStatusSubtitle: {
    fontSize: 12,
    color: '#15803D',
    marginTop: 1,
  },
  liveBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#DCFCE7',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 10,
    gap: 4,
  },
  liveBadgeDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: '#22C55E',
  },
  liveBadgeText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#22C55E',
  },
  // Timeline Toggle
  timelineToggle: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    marginHorizontal: 16,
    marginTop: 12,
    padding: 16,
    borderRadius: 16,
  },
  timelineToggleLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  timelineToggleText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#374151',
  },
  timelineProgress: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  timelineProgressText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#6366F1',
  },
  // Checkpoints
  checkpointsCard: {
    backgroundColor: '#FFFFFF',
    marginHorizontal: 16,
    marginTop: 4,
    padding: 16,
    paddingTop: 0,
    borderRadius: 16,
    borderTopLeftRadius: 0,
    borderTopRightRadius: 0,
  },
  checkpointRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    position: 'relative',
    paddingTop: 16,
  },
  connectorLine: {
    position: 'absolute',
    left: 13,
    top: 0,
    width: 2,
    height: 16,
    backgroundColor: '#E5E7EB',
  },
  connectorLineCompleted: {
    backgroundColor: '#22C55E',
  },
  checkpointCircle: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: '#F3F4F6',
    borderWidth: 2,
    borderColor: '#E5E7EB',
    justifyContent: 'center',
    alignItems: 'center',
    zIndex: 1,
  },
  checkpointCircleCompleted: {
    backgroundColor: '#22C55E',
    borderColor: '#22C55E',
  },
  checkpointCircleCurrent: {
    backgroundColor: '#EEF2FF',
    borderColor: '#6366F1',
  },
  checkpointContent: {
    flex: 1,
    marginLeft: 12,
    paddingBottom: 8,
  },
  checkpointLabel: {
    fontSize: 14,
    fontWeight: '500',
    color: '#9CA3AF',
  },
  checkpointLabelCompleted: {
    color: '#374151',
    fontWeight: '600',
  },
  checkpointLabelCurrent: {
    color: '#6366F1',
    fontWeight: '700',
  },
  checkpointTime: {
    fontSize: 12,
    color: '#9CA3AF',
    marginTop: 2,
  },
  // Bottom Actions
  bottomActions: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    flexDirection: 'row',
    padding: 16,
    backgroundColor: '#FFFFFF',
    borderTopWidth: 1,
    borderTopColor: '#E5E7EB',
  },
  actionBtn: {
    flex: 1,
    paddingVertical: 16,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#F3F4F6',
  },
  actionBtnPrimary: {
    backgroundColor: '#6366F1',
  },
  actionBtnDestructive: {
    backgroundColor: '#FEE2E2',
  },
  actionBtnText: {
    fontSize: 15,
    fontWeight: '700',
    color: '#374151',
  },
  actionBtnTextPrimary: {
    color: '#FFFFFF',
  },
  actionBtnTextDestructive: {
    color: '#DC2626',
  },
  // Modal Styles
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: '#FFFFFF',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    paddingHorizontal: 20,
    paddingTop: 12,
    maxHeight: '80%',
  },
  modalHandle: {
    width: 40,
    height: 4,
    backgroundColor: '#D1D5DB',
    borderRadius: 2,
    alignSelf: 'center',
    marginBottom: 16,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 20,
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#111827',
  },
  selectedItemCard: {
    backgroundColor: '#F3F4F6',
    padding: 16,
    borderRadius: 12,
    marginBottom: 20,
  },
  selectedItemName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#111827',
  },
  selectedItemDetails: {
    fontSize: 14,
    color: '#6B7280',
    marginTop: 4,
  },
  modalSection: {
    marginBottom: 24,
  },
  modalSectionTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: '#111827',
    marginBottom: 4,
  },
  modalSectionDesc: {
    fontSize: 13,
    color: '#6B7280',
    marginBottom: 12,
  },
  qtyInputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginBottom: 12,
  },
  qtyBtn: {
    width: 44,
    height: 44,
    borderRadius: 12,
    backgroundColor: '#EEF2FF',
    justifyContent: 'center',
    alignItems: 'center',
  },
  qtyInput: {
    flex: 1,
    height: 44,
    backgroundColor: '#F3F4F6',
    borderRadius: 12,
    textAlign: 'center',
    fontSize: 18,
    fontWeight: '700',
    color: '#111827',
  },
  adjustQtyBtn: {
    backgroundColor: '#6366F1',
    paddingVertical: 14,
    borderRadius: 12,
    alignItems: 'center',
  },
  adjustQtyBtnText: {
    fontSize: 15,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  reasonInput: {
    backgroundColor: '#F3F4F6',
    borderRadius: 12,
    padding: 14,
    fontSize: 14,
    color: '#111827',
    marginBottom: 12,
  },
  unavailableBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#DC2626',
    paddingVertical: 14,
    borderRadius: 12,
    gap: 8,
  },
  unavailableBtnText: {
    fontSize: 15,
    fontWeight: '700',
    color: '#FFFFFF',
  },
});
