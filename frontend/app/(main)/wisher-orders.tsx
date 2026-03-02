import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  Modal,
  TextInput,
  ScrollView,
  ActivityIndicator,
  Platform,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { useFocusEffect } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { wisherOrderAPI } from '../../src/utils/api';
import { useAlert } from '../../src/context/AlertContext';
import { format } from 'date-fns';
import QRCode from 'react-native-qrcode-svg';

type StatusType = 'all' | 'pending' | 'confirmed' | 'preparing' | 'ready_for_pickup' | 'out_for_delivery' | 'delivered' | 'cancelled';

interface PickupQRData {
  qr_data: string;
  pickup_code: string;
  expires_at: string;
  assigned_genie: {
    name: string;
    phone: string;
  };
  items: Array<{
    product_id: string;
    name: string;
    quantity: number;
    price: number;
  }>;
}

interface WisherOrder {
  order_id: string;
  user_id: string;
  user_info: {
    name: string;
    email?: string;
    phone?: string;
  };
  customer_name: string;
  customer_phone?: string;
  items: Array<{
    product_id: string;
    name: string;
    price: number;
    discounted_price?: number;
    quantity: number;
    image?: string;
  }>;
  original_items?: Array<any>;
  subtotal: number;
  delivery_fee: number;
  total: number;
  original_total?: number;
  refund_amount?: number;
  refund_status?: string;
  delivery_address: {
    address: string;
    lat?: number;
    lng?: number;
  };
  status: string;
  is_modified?: boolean;
  created_at: string;
  notes?: string;
  delivery_type?: string;
  genie_status?: string;
  genie_name?: string;
  genie_phone?: string;
  // Multi-order fields
  is_multi_order?: boolean;
  group_order_id?: string;
  vendor_sequence?: number;
  total_vendors?: number;
}

export default function WisherOrdersScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { showAlert } = useAlert();
  
  const [orders, setOrders] = useState<WisherOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeFilter, setActiveFilter] = useState<StatusType>('all');
  const [vendorHasOwnDelivery, setVendorHasOwnDelivery] = useState(false);
  const [summary, setSummary] = useState({
    pending: 0,
    confirmed: 0,
    preparing: 0,
    ready_for_pickup: 0,
    out_for_delivery: 0,
    delivered: 0,
    cancelled: 0,
  });
  
  // Delivery assignment modal
  const [showDeliveryModal, setShowDeliveryModal] = useState(false);
  
  // Order detail modal
  const [selectedOrder, setSelectedOrder] = useState<WisherOrder | null>(null);
  const [showOrderModal, setShowOrderModal] = useState(false);
  
  // Modify order modal
  const [showModifyModal, setShowModifyModal] = useState(false);
  const [modifyReason, setModifyReason] = useState('');
  const [itemsToModify, setItemsToModify] = useState<{[key: string]: {quantity: number, reason: string}}>({});
  
  // Status update modal
  const [showStatusModal, setShowStatusModal] = useState(false);
  const [statusNote, setStatusNote] = useState('');
  
  // Pickup QR modal
  const [showQRModal, setShowQRModal] = useState(false);
  const [pickupQRData, setPickupQRData] = useState<PickupQRData | null>(null);
  const [loadingQR, setLoadingQR] = useState(false);

  const fetchOrders = async () => {
    try {
      const response = await wisherOrderAPI.getAll();
      setOrders(response.data.orders || []);
      setSummary(response.data.summary || {});
      setVendorHasOwnDelivery(response.data.vendor_has_own_delivery || false);
    } catch (error: any) {
      console.error('Error fetching wisher orders:', error);
      showAlert({
        type: 'error',
        title: 'Error',
        message: 'Failed to fetch orders from Local Hub',
      });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useFocusEffect(
    useCallback(() => {
      fetchOrders();
    }, [])
  );

  const onRefresh = () => {
    setRefreshing(true);
    fetchOrders();
  };

  const getFilteredOrders = () => {
    if (activeFilter === 'all') return orders;
    return orders.filter(o => o.status === activeFilter);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'pending': return '#F59E0B';
      case 'confirmed': return '#3B82F6';
      case 'preparing': return '#8B5CF6';
      case 'ready_for_pickup': return '#F97316';
      case 'out_for_delivery': return '#06B6D4';
      case 'delivered': return '#10B981';
      case 'cancelled': return '#EF4444';
      default: return '#6B7280';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pending': return 'time-outline';
      case 'confirmed': return 'checkmark-circle-outline';
      case 'preparing': return 'restaurant-outline';
      case 'ready_for_pickup': return 'cube-outline';
      case 'out_for_delivery': return 'bicycle-outline';
      case 'delivered': return 'checkmark-done-outline';
      case 'cancelled': return 'close-circle-outline';
      default: return 'help-outline';
    }
  };

  const handleStatusUpdate = async (orderId: string, newStatus: string) => {
    try {
      await wisherOrderAPI.updateStatus(orderId, newStatus, statusNote);
      showAlert({
        type: 'success',
        title: 'Status Updated',
        message: `Order status changed to ${newStatus}`,
      });
      setShowStatusModal(false);
      setStatusNote('');
      fetchOrders();
    } catch (error: any) {
      showAlert({
        type: 'error',
        title: 'Error',
        message: error.response?.data?.detail || 'Failed to update status',
      });
    }
  };

  const handleReadyForPickup = async (orderId: string) => {
    try {
      await wisherOrderAPI.readyForPickup(orderId);
      showAlert({
        type: 'success',
        title: 'Ready for Pickup',
        message: 'Order is ready for delivery assignment',
      });
      setShowOrderModal(false);
      fetchOrders();
    } catch (error: any) {
      showAlert({
        type: 'error',
        title: 'Error',
        message: error.response?.data?.detail || 'Failed to update status',
      });
    }
  };

  const handleAssignDelivery = async (orderId: string, deliveryType: 'own' | 'genie') => {
    try {
      const response = await wisherOrderAPI.assignDelivery(orderId, deliveryType);
      showAlert({
        type: 'success',
        title: deliveryType === 'own' ? 'Self Delivery' : 'Carpet Genie Requested',
        message: response.data.message,
      });
      setShowDeliveryModal(false);
      setShowOrderModal(false);
      fetchOrders();
    } catch (error: any) {
      showAlert({
        type: 'error',
        title: 'Error',
        message: error.response?.data?.detail || 'Failed to assign delivery',
      });
    }
  };

  const handleModifyOrder = async () => {
    if (!selectedOrder) return;
    
    const modifiedItems = Object.entries(itemsToModify)
      .filter(([_, value]) => value.quantity >= 0)
      .map(([productId, value]) => ({
        product_id: productId,
        new_quantity: value.quantity,
        reason: value.reason || 'Item modified',
      }));
    
    if (modifiedItems.length === 0) {
      showAlert({
        type: 'error',
        title: 'No Changes',
        message: 'Please specify items to modify',
      });
      return;
    }
    
    try {
      const response = await wisherOrderAPI.modifyOrder(selectedOrder.order_id, {
        modified_items: modifiedItems,
        modification_reason: modifyReason || 'Order modified by vendor',
      });
      
      showAlert({
        type: 'success',
        title: 'Order Modified',
        message: `Refund amount: ₹${response.data.refund_amount}`,
      });
      
      setShowModifyModal(false);
      setModifyReason('');
      setItemsToModify({});
      setShowOrderModal(false);
      fetchOrders();
    } catch (error: any) {
      showAlert({
        type: 'error',
        title: 'Error',
        message: error.response?.data?.detail || 'Failed to modify order',
      });
    }
  };

  const handleProcessRefund = async (orderId: string) => {
    try {
      await wisherOrderAPI.processRefund(orderId);
      showAlert({
        type: 'success',
        title: 'Refund Processed',
        message: 'Refund has been marked as processed',
      });
      fetchOrders();
    } catch (error: any) {
      showAlert({
        type: 'error',
        title: 'Error',
        message: error.response?.data?.detail || 'Failed to process refund',
      });
    }
  };

  const handleShowPickupQR = async (orderId: string) => {
    setLoadingQR(true);
    try {
      const response = await wisherOrderAPI.getPickupQR(orderId);
      setPickupQRData(response.data);
      setShowQRModal(true);
    } catch (error: any) {
      showAlert({
        type: 'error',
        title: 'Error',
        message: error.response?.data?.detail || 'Failed to get pickup QR code',
      });
    } finally {
      setLoadingQR(false);
    }
  };

  const renderOrderCard = ({ item }: { item: WisherOrder }) => {
    const statusColor = getStatusColor(item.status);
    const itemCount = item.items.reduce((sum, i) => sum + i.quantity, 0);
    const isSearchingGenie = item.genie_status === 'searching';
    
    return (
      <TouchableOpacity
        style={styles.orderCard}
        onPress={() => {
          setSelectedOrder(item);
          setShowOrderModal(true);
        }}
        activeOpacity={0.7}
      >
        <View style={styles.orderHeader}>
          <View style={styles.orderIdContainer}>
            <Text style={styles.orderId}>#{item.order_id.slice(-8)}</Text>
            {item.is_modified && (
              <View style={styles.modifiedBadge}>
                <Text style={styles.modifiedText}>Modified</Text>
              </View>
            )}
            {item.is_multi_order && (
              <View style={styles.multiOrderBadge}>
                <Ionicons name="layers-outline" size={12} color="#6366F1" />
                <Text style={styles.multiOrderText}>{item.vendor_sequence}/{item.total_vendors}</Text>
              </View>
            )}
          </View>
          <View style={[styles.statusBadge, { backgroundColor: `${statusColor}15` }]}>
            <Ionicons name={getStatusIcon(item.status) as any} size={14} color={statusColor} />
            <Text style={[styles.statusText, { color: statusColor }]}>
              {item.status.replace(/_/g, ' ')}
            </Text>
          </View>
        </View>
        
        {/* Genie Searching Indicator */}
        {isSearchingGenie && (
          <View style={styles.searchingGenieBar}>
            <ActivityIndicator size="small" color="#6366F1" />
            <Text style={styles.searchingGenieText}>Finding delivery partner...</Text>
          </View>
        )}
        
        <View style={styles.customerInfo}>
          <Ionicons name="person-outline" size={16} color="#6B7280" />
          <Text style={styles.customerName}>{item.customer_name || item.user_info?.name}</Text>
          {item.customer_phone && (
            <>
              <Text style={styles.separator}>•</Text>
              <Text style={styles.customerPhone}>{item.customer_phone}</Text>
            </>
          )}
        </View>
        
        <View style={styles.orderDetails}>
          <View style={styles.detailItem}>
            <Ionicons name="cube-outline" size={16} color="#6B7280" />
            <Text style={styles.detailText}>{itemCount} items</Text>
          </View>
          <View style={styles.detailItem}>
            <Text style={styles.totalAmount}>₹{item.total}</Text>
            {item.refund_amount && item.refund_amount > 0 && (
              <Text style={styles.refundAmount}>(-₹{item.refund_amount})</Text>
            )}
          </View>
        </View>
        
        <View style={styles.orderFooter}>
          <Text style={styles.orderTime}>
            {format(new Date(item.created_at), 'dd MMM, hh:mm a')}
          </Text>
          <Ionicons name="chevron-forward" size={20} color="#9CA3AF" />
        </View>
      </TouchableOpacity>
    );
  };

  const renderFilterChip = (filter: StatusType, label: string, count?: number) => {
    const isActive = activeFilter === filter;
    return (
      <TouchableOpacity
        key={filter}
        style={[styles.filterChip, isActive && styles.filterChipActive]}
        onPress={() => setActiveFilter(filter)}
      >
        <Text style={[styles.filterChipText, isActive && styles.filterChipTextActive]}>
          {label}
        </Text>
        {count !== undefined && count > 0 && (
          <View style={[styles.filterCount, isActive && styles.filterCountActive]}>
            <Text style={[styles.filterCountText, isActive && styles.filterCountTextActive]}>
              {count}
            </Text>
          </View>
        )}
      </TouchableOpacity>
    );
  };

  if (loading) {
    return (
      <View style={[styles.container, styles.centered]}>
        <ActivityIndicator size="large" color="#6366F1" />
        <Text style={styles.loadingText}>Loading orders...</Text>
      </View>
    );
  }

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={24} color="#111827" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Local Hub Orders</Text>
        <View style={styles.headerBadge}>
          <Ionicons name="globe-outline" size={18} color="#6366F1" />
        </View>
      </View>

      {/* Summary Cards */}
      <View style={styles.summaryContainer}>
        <View style={[styles.summaryCard, { backgroundColor: '#FEF3C7' }]}>
          <Text style={styles.summaryCount}>{summary.pending}</Text>
          <Text style={styles.summaryLabel}>Pending</Text>
        </View>
        <View style={[styles.summaryCard, { backgroundColor: '#DBEAFE' }]}>
          <Text style={styles.summaryCount}>{summary.confirmed + summary.preparing}</Text>
          <Text style={styles.summaryLabel}>Active</Text>
        </View>
        <View style={[styles.summaryCard, { backgroundColor: '#D1FAE5' }]}>
          <Text style={styles.summaryCount}>{summary.delivered}</Text>
          <Text style={styles.summaryLabel}>Done</Text>
        </View>
      </View>

      {/* Filter Chips */}
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.filterContainer}
        contentContainerStyle={styles.filterContent}
      >
        {renderFilterChip('all', 'All', orders.length)}
        {renderFilterChip('pending', 'Pending', summary.pending)}
        {renderFilterChip('confirmed', 'Confirmed', summary.confirmed)}
        {renderFilterChip('preparing', 'Preparing', summary.preparing)}
        {renderFilterChip('ready_for_pickup', 'Ready', summary.ready_for_pickup)}
        {renderFilterChip('out_for_delivery', 'On Delivery', summary.out_for_delivery)}
        {renderFilterChip('delivered', 'Delivered', summary.delivered)}
      </ScrollView>

      {/* Orders List */}
      <FlatList
        data={getFilteredOrders()}
        renderItem={renderOrderCard}
        keyExtractor={(item) => item.order_id}
        contentContainerStyle={[styles.listContent, { paddingBottom: insets.bottom + 20 }]}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={['#6366F1']} />
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Ionicons name="receipt-outline" size={64} color="#D1D5DB" />
            <Text style={styles.emptyTitle}>No orders yet</Text>
            <Text style={styles.emptyText}>Orders from Local Hub will appear here</Text>
          </View>
        }
      />

      {/* Order Detail Modal */}
      <Modal visible={showOrderModal} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={[styles.modalContent, { paddingBottom: insets.bottom + 20 }]}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Order Details</Text>
              <TouchableOpacity onPress={() => setShowOrderModal(false)}>
                <Ionicons name="close" size={24} color="#6B7280" />
              </TouchableOpacity>
            </View>
            
            {selectedOrder && (
              <ScrollView showsVerticalScrollIndicator={false}>
                {/* Order Info */}
                <View style={styles.section}>
                  <View style={styles.orderTitleRow}>
                    <Text style={styles.sectionTitle}>Order #{selectedOrder.order_id.slice(-8)}</Text>
                    {selectedOrder.is_multi_order && (
                      <View style={styles.multiOrderInfoBadge}>
                        <Ionicons name="layers" size={14} color="#6366F1" />
                        <Text style={styles.multiOrderInfoText}>Multi-Order ({selectedOrder.vendor_sequence}/{selectedOrder.total_vendors})</Text>
                      </View>
                    )}
                  </View>
                  <View style={[styles.statusBadge, { backgroundColor: `${getStatusColor(selectedOrder.status)}15`, alignSelf: 'flex-start' }]}>
                    <Text style={[styles.statusText, { color: getStatusColor(selectedOrder.status) }]}>
                      {selectedOrder.status.replace(/_/g, ' ')}
                    </Text>
                  </View>
                  {selectedOrder.is_multi_order && (
                    <Text style={styles.multiOrderNote}>This is part of a multi-vendor order. Customer ordered from {selectedOrder.total_vendors} shops.</Text>
                  )}
                </View>
                
                {/* Customer Info */}
                <View style={styles.section}>
                  <Text style={styles.sectionTitle}>Customer</Text>
                  <Text style={styles.infoText}>{selectedOrder.customer_name || selectedOrder.user_info?.name}</Text>
                  {selectedOrder.customer_phone && (
                    <Text style={styles.infoTextSecondary}>{selectedOrder.customer_phone}</Text>
                  )}
                  {selectedOrder.user_info?.email && (
                    <Text style={styles.infoTextSecondary}>{selectedOrder.user_info.email}</Text>
                  )}
                </View>
                
                {/* Delivery Address */}
                <View style={styles.section}>
                  <Text style={styles.sectionTitle}>Delivery Address</Text>
                  <Text style={styles.infoText}>{selectedOrder.delivery_address?.address || 'Not provided'}</Text>
                </View>
                
                {/* Items */}
                <View style={styles.section}>
                  <Text style={styles.sectionTitle}>Items</Text>
                  {selectedOrder.items.map((item, index) => (
                    <View key={index} style={styles.itemRow}>
                      <View style={styles.itemInfo}>
                        <Text style={styles.itemName}>{item.name}</Text>
                        <Text style={styles.itemQty}>x{item.quantity}</Text>
                      </View>
                      <Text style={styles.itemPrice}>₹{(item.discounted_price || item.price) * item.quantity}</Text>
                    </View>
                  ))}
                </View>
                
                {/* Totals */}
                <View style={styles.section}>
                  <View style={styles.totalRow}>
                    <Text style={styles.totalLabel}>Subtotal</Text>
                    <Text style={styles.totalValue}>₹{selectedOrder.subtotal}</Text>
                  </View>
                  <View style={styles.totalRow}>
                    <Text style={styles.totalLabel}>Delivery Fee</Text>
                    <Text style={styles.totalValue}>₹{selectedOrder.delivery_fee}</Text>
                  </View>
                  {selectedOrder.refund_amount && selectedOrder.refund_amount > 0 && (
                    <View style={styles.totalRow}>
                      <Text style={[styles.totalLabel, { color: '#EF4444' }]}>Refund</Text>
                      <Text style={[styles.totalValue, { color: '#EF4444' }]}>-₹{selectedOrder.refund_amount}</Text>
                    </View>
                  )}
                  <View style={[styles.totalRow, styles.grandTotal]}>
                    <Text style={styles.grandTotalLabel}>Total</Text>
                    <Text style={styles.grandTotalValue}>₹{selectedOrder.total}</Text>
                  </View>
                </View>
                
                {/* Action Buttons */}
                <View style={styles.actionButtons}>
                  {selectedOrder.status === 'pending' && (
                    <>
                      <TouchableOpacity
                        style={[styles.actionBtn, styles.confirmBtn]}
                        onPress={() => handleStatusUpdate(selectedOrder.order_id, 'confirmed')}
                        data-testid="confirm-order-btn"
                      >
                        <Ionicons name="checkmark-circle" size={20} color="#FFF" />
                        <Text style={styles.actionBtnText}>Confirm</Text>
                      </TouchableOpacity>
                      <TouchableOpacity
                        style={[styles.actionBtn, styles.modifyBtn]}
                        onPress={() => {
                          const initial: {[key: string]: {quantity: number, reason: string}} = {};
                          selectedOrder.items.forEach(item => {
                            initial[item.product_id] = { quantity: item.quantity, reason: '' };
                          });
                          setItemsToModify(initial);
                          setShowModifyModal(true);
                        }}
                        data-testid="modify-order-btn"
                      >
                        <Ionicons name="create-outline" size={20} color="#FFF" />
                        <Text style={styles.actionBtnText}>Modify</Text>
                      </TouchableOpacity>
                    </>
                  )}
                  
                  {selectedOrder.status === 'confirmed' && (
                    <>
                      <TouchableOpacity
                        style={[styles.actionBtn, styles.confirmBtn]}
                        onPress={() => handleStatusUpdate(selectedOrder.order_id, 'preparing')}
                        data-testid="start-preparing-btn"
                      >
                        <Ionicons name="restaurant" size={20} color="#FFF" />
                        <Text style={styles.actionBtnText}>Start Preparing</Text>
                      </TouchableOpacity>
                      {!vendorHasOwnDelivery && (
                        <View style={styles.autoSearchNote}>
                          <Ionicons name="information-circle-outline" size={16} color="#6366F1" />
                          <Text style={styles.autoSearchText}>We'll start finding a delivery partner once you begin preparing</Text>
                        </View>
                      )}
                    </>
                  )}
                  
                  {selectedOrder.status === 'preparing' && (
                    <>
                      {/* Show genie search status if auto-searching */}
                      {selectedOrder.genie_status === 'searching' && (
                        <View style={styles.genieInfoBox}>
                          <ActivityIndicator size="small" color="#6366F1" />
                          <Text style={styles.genieInfoTitle}>Finding Delivery Partner...</Text>
                          <Text style={styles.genieStatusText}>We're looking for the best partner for this order</Text>
                        </View>
                      )}
                      <TouchableOpacity
                        style={[styles.actionBtn, styles.confirmBtn]}
                        onPress={() => handleReadyForPickup(selectedOrder.order_id)}
                        data-testid="ready-for-pickup-btn"
                      >
                        <Ionicons name="cube" size={20} color="#FFF" />
                        <Text style={styles.actionBtnText}>Ready for Pickup</Text>
                      </TouchableOpacity>
                    </>
                  )}
                  
                  {selectedOrder.status === 'ready_for_pickup' && !selectedOrder.genie_status && (
                    <>
                      <Text style={styles.deliveryLabel}>Choose Delivery Method:</Text>
                      {vendorHasOwnDelivery && (
                        <TouchableOpacity
                          style={[styles.actionBtn, styles.confirmBtn]}
                          onPress={() => handleAssignDelivery(selectedOrder.order_id, 'own')}
                          data-testid="self-delivery-btn"
                        >
                          <Ionicons name="car" size={20} color="#FFF" />
                          <Text style={styles.actionBtnText}>I'll Deliver Myself</Text>
                        </TouchableOpacity>
                      )}
                      <TouchableOpacity
                        style={[styles.actionBtn, styles.genieBtn]}
                        onPress={() => handleAssignDelivery(selectedOrder.order_id, 'genie')}
                        data-testid="request-genie-btn"
                      >
                        <Ionicons name="bicycle" size={20} color="#FFF" />
                        <Text style={styles.actionBtnText}>Request Delivery Partner</Text>
                      </TouchableOpacity>
                    </>
                  )}
                  
                  {/* Show searching status when genie is being searched */}
                  {selectedOrder.genie_status === 'searching' && selectedOrder.status !== 'preparing' && (
                    <View style={styles.genieInfoBox}>
                      <ActivityIndicator size="small" color="#6366F1" />
                      <Text style={styles.genieInfoTitle}>Finding Delivery Partner...</Text>
                      <Text style={styles.genieStatusText}>We'll assign the best partner for your order</Text>
                    </View>
                  )}
                  
                  {/* Show assigned genie info */}
                  {selectedOrder.genie_status === 'assigned' && (
                    <View style={styles.genieInfoBox}>
                      <View style={styles.genieAssignedHeader}>
                        <Ionicons name="checkmark-circle" size={24} color="#10B981" />
                        <Text style={styles.genieAssignedTitle}>Delivery Partner Assigned!</Text>
                      </View>
                      <Text style={styles.genieInfoText}>{selectedOrder.genie_name || 'Delivery Partner'}</Text>
                      {selectedOrder.genie_phone && (
                        <Text style={styles.genieInfoText}>{selectedOrder.genie_phone}</Text>
                      )}
                    </View>
                  )}
                  
                  {/* Show QR Code button when order is ready and genie is assigned */}
                  {(selectedOrder.status === 'ready_for_pickup' || selectedOrder.status === 'preparing') && 
                   selectedOrder.genie_status === 'assigned' && (
                    <TouchableOpacity
                      style={[styles.actionBtn, styles.qrBtn]}
                      onPress={() => handleShowPickupQR(selectedOrder.order_id)}
                      disabled={loadingQR}
                      data-testid="show-pickup-qr-btn"
                    >
                      {loadingQR ? (
                        <ActivityIndicator size="small" color="#FFF" />
                      ) : (
                        <>
                          <Ionicons name="qr-code" size={20} color="#FFF" />
                          <Text style={styles.actionBtnText}>Show Pickup QR Code</Text>
                        </>
                      )}
                    </TouchableOpacity>
                  )}
                  
                  {selectedOrder.status === 'out_for_delivery' && selectedOrder.delivery_type === 'vendor_delivery' && (
                    <TouchableOpacity
                      style={[styles.actionBtn, styles.confirmBtn]}
                      onPress={() => handleStatusUpdate(selectedOrder.order_id, 'delivered')}
                      data-testid="mark-delivered-btn"
                    >
                      <Ionicons name="checkmark-done" size={20} color="#FFF" />
                      <Text style={styles.actionBtnText}>Mark Delivered</Text>
                    </TouchableOpacity>
                  )}
                  
                  {selectedOrder.status === 'out_for_delivery' && selectedOrder.delivery_type === 'genie_delivery' && (
                    <View style={styles.genieInfoBox}>
                      <Text style={styles.genieInfoTitle}>Delivery Partner</Text>
                      <Text style={styles.genieInfoText}>{selectedOrder.genie_name || 'Assigned'}</Text>
                      {selectedOrder.genie_phone && (
                        <Text style={styles.genieInfoText}>{selectedOrder.genie_phone}</Text>
                      )}
                      <Text style={styles.genieStatusText}>
                        Status: {selectedOrder.genie_status?.replace(/_/g, ' ') || 'On the way'}
                      </Text>
                    </View>
                  )}
                  
                  {selectedOrder.refund_amount && selectedOrder.refund_amount > 0 && selectedOrder.refund_status === 'pending' && (
                    <TouchableOpacity
                      style={[styles.actionBtn, styles.refundBtn]}
                      onPress={() => handleProcessRefund(selectedOrder.order_id)}
                      data-testid="process-refund-btn"
                    >
                      <Ionicons name="wallet" size={20} color="#FFF" />
                      <Text style={styles.actionBtnText}>Process Refund (₹{selectedOrder.refund_amount})</Text>
                    </TouchableOpacity>
                  )}
                </View>
              </ScrollView>
            )}
          </View>
        </View>
      </Modal>

      {/* Modify Order Modal */}
      <Modal visible={showModifyModal} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={[styles.modalContent, { paddingBottom: insets.bottom + 20 }]}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Modify Order</Text>
              <TouchableOpacity onPress={() => setShowModifyModal(false)}>
                <Ionicons name="close" size={24} color="#6B7280" />
              </TouchableOpacity>
            </View>
            
            <ScrollView showsVerticalScrollIndicator={false}>
              <Text style={styles.modifyHint}>
                Set quantity to 0 to remove an item. Refund will be calculated automatically.
              </Text>
              
              {selectedOrder?.items.map((item, index) => (
                <View key={index} style={styles.modifyItemRow}>
                  <View style={styles.modifyItemInfo}>
                    <Text style={styles.modifyItemName}>{item.name}</Text>
                    <Text style={styles.modifyItemPrice}>₹{item.discounted_price || item.price} each</Text>
                  </View>
                  <View style={styles.modifyControls}>
                    <TouchableOpacity
                      style={styles.qtyBtn}
                      onPress={() => {
                        const current = itemsToModify[item.product_id]?.quantity ?? item.quantity;
                        if (current > 0) {
                          setItemsToModify({
                            ...itemsToModify,
                            [item.product_id]: {
                              ...itemsToModify[item.product_id],
                              quantity: current - 1,
                            },
                          });
                        }
                      }}
                    >
                      <Ionicons name="remove" size={18} color="#6366F1" />
                    </TouchableOpacity>
                    <Text style={styles.qtyText}>
                      {itemsToModify[item.product_id]?.quantity ?? item.quantity}
                    </Text>
                    <TouchableOpacity
                      style={styles.qtyBtn}
                      onPress={() => {
                        const current = itemsToModify[item.product_id]?.quantity ?? item.quantity;
                        setItemsToModify({
                          ...itemsToModify,
                          [item.product_id]: {
                            ...itemsToModify[item.product_id],
                            quantity: current + 1,
                          },
                        });
                      }}
                    >
                      <Ionicons name="add" size={18} color="#6366F1" />
                    </TouchableOpacity>
                  </View>
                  <TextInput
                    style={styles.reasonInput}
                    placeholder="Reason (e.g., Out of stock)"
                    value={itemsToModify[item.product_id]?.reason || ''}
                    onChangeText={(text) => {
                      setItemsToModify({
                        ...itemsToModify,
                        [item.product_id]: {
                          ...itemsToModify[item.product_id],
                          reason: text,
                        },
                      });
                    }}
                  />
                </View>
              ))}
              
              <TextInput
                style={styles.overallReasonInput}
                placeholder="Overall modification reason"
                value={modifyReason}
                onChangeText={setModifyReason}
                multiline
              />
              
              <TouchableOpacity style={styles.saveModifyBtn} onPress={handleModifyOrder}>
                <Text style={styles.saveModifyBtnText}>Save Changes</Text>
              </TouchableOpacity>
            </ScrollView>
          </View>
        </View>
      </Modal>

      {/* Pickup QR Code Modal */}
      <Modal visible={showQRModal} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={[styles.modalContent, { paddingBottom: insets.bottom + 20 }]}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Pickup QR Code</Text>
              <TouchableOpacity onPress={() => {
                setShowQRModal(false);
                setPickupQRData(null);
              }}>
                <Ionicons name="close" size={24} color="#6B7280" />
              </TouchableOpacity>
            </View>
            
            {pickupQRData && (
              <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.qrModalContent}>
                {/* QR Code Section */}
                <View style={styles.qrCodeContainer} data-testid="pickup-qr-container">
                  <View style={styles.qrWrapper}>
                    {Platform.OS === 'web' ? (
                      <View style={styles.qrWebPlaceholder}>
                        <Ionicons name="qr-code-outline" size={120} color="#6366F1" />
                        <Text style={styles.qrWebNote}>QR Code: {pickupQRData.qr_data.substring(0, 30)}...</Text>
                      </View>
                    ) : (
                      <QRCode
                        value={pickupQRData.qr_data}
                        size={200}
                        backgroundColor="#FFF"
                        color="#111827"
                      />
                    )}
                  </View>
                  <Text style={styles.qrInstructions}>
                    Show this QR code to the delivery partner for verification
                  </Text>
                </View>
                
                {/* Fallback Code Section */}
                <View style={styles.fallbackCodeSection}>
                  <Text style={styles.fallbackLabel}>Or use this code:</Text>
                  <View style={styles.pickupCodeBox} data-testid="pickup-code-display">
                    <Text style={styles.pickupCode}>{pickupQRData.pickup_code}</Text>
                  </View>
                  <Text style={styles.pickupCodeHint}>
                    Share this 6-digit code if QR scanning fails
                  </Text>
                </View>
                
                {/* Genie Info */}
                <View style={styles.qrGenieInfo}>
                  <Ionicons name="bicycle" size={20} color="#6366F1" />
                  <View style={styles.qrGenieDetails}>
                    <Text style={styles.qrGenieLabel}>Assigned To:</Text>
                    <Text style={styles.qrGenieName}>{pickupQRData.assigned_genie?.name || 'Delivery Partner'}</Text>
                    {pickupQRData.assigned_genie?.phone && (
                      <Text style={styles.qrGeniePhone}>{pickupQRData.assigned_genie.phone}</Text>
                    )}
                  </View>
                </View>
                
                {/* Items Checklist */}
                <View style={styles.qrItemsSection}>
                  <Text style={styles.qrItemsTitle}>Order Items Checklist</Text>
                  <Text style={styles.qrItemsHint}>Verify all items before handover</Text>
                  {pickupQRData.items?.map((item, index) => (
                    <View key={index} style={styles.qrItemRow}>
                      <View style={styles.qrItemCheckbox}>
                        <Ionicons name="checkbox-outline" size={22} color="#6366F1" />
                      </View>
                      <View style={styles.qrItemInfo}>
                        <Text style={styles.qrItemName}>{item.name}</Text>
                        <Text style={styles.qrItemQty}>Qty: {item.quantity}</Text>
                      </View>
                    </View>
                  ))}
                </View>
                
                {/* Expiry Warning */}
                {pickupQRData.expires_at && (
                  <View style={styles.qrExpiryWarning}>
                    <Ionicons name="time-outline" size={16} color="#F59E0B" />
                    <Text style={styles.qrExpiryText}>
                      Valid until: {format(new Date(pickupQRData.expires_at), 'hh:mm a')}
                    </Text>
                  </View>
                )}
              </ScrollView>
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
    backgroundColor: '#F9FAFB',
  },
  centered: {
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 12,
    color: '#6B7280',
    fontSize: 14,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: '#FFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  backButton: {
    padding: 8,
    marginRight: 8,
  },
  headerTitle: {
    flex: 1,
    fontSize: 20,
    fontWeight: '700',
    color: '#111827',
  },
  headerBadge: {
    backgroundColor: '#EEF2FF',
    padding: 8,
    borderRadius: 12,
  },
  summaryContainer: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    paddingVertical: 12,
    gap: 10,
  },
  summaryCard: {
    flex: 1,
    padding: 12,
    borderRadius: 12,
    alignItems: 'center',
  },
  summaryCount: {
    fontSize: 24,
    fontWeight: '700',
    color: '#111827',
  },
  summaryLabel: {
    fontSize: 12,
    color: '#6B7280',
    marginTop: 2,
  },
  filterContainer: {
    maxHeight: 50,
    backgroundColor: '#FFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  filterContent: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    gap: 8,
    flexDirection: 'row',
  },
  filterChip: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingVertical: 6,
    backgroundColor: '#F3F4F6',
    borderRadius: 20,
    gap: 6,
  },
  filterChipActive: {
    backgroundColor: '#6366F1',
  },
  filterChipText: {
    fontSize: 13,
    fontWeight: '500',
    color: '#6B7280',
  },
  filterChipTextActive: {
    color: '#FFF',
  },
  filterCount: {
    backgroundColor: '#E5E7EB',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 10,
  },
  filterCountActive: {
    backgroundColor: 'rgba(255,255,255,0.2)',
  },
  filterCountText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#6B7280',
  },
  filterCountTextActive: {
    color: '#FFF',
  },
  listContent: {
    padding: 16,
    gap: 12,
  },
  orderCard: {
    backgroundColor: '#FFF',
    borderRadius: 16,
    padding: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
    marginBottom: 12,
  },
  orderHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  orderIdContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  orderId: {
    fontSize: 16,
    fontWeight: '700',
    color: '#111827',
  },
  modifiedBadge: {
    backgroundColor: '#FEF3C7',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 8,
  },
  modifiedText: {
    fontSize: 10,
    fontWeight: '600',
    color: '#D97706',
  },
  multiOrderBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#EEF2FF',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 8,
    gap: 4,
  },
  multiOrderText: {
    fontSize: 10,
    fontWeight: '600',
    color: '#6366F1',
  },
  searchingGenieBar: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#EEF2FF',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
    marginBottom: 12,
    gap: 8,
  },
  searchingGenieText: {
    fontSize: 13,
    fontWeight: '500',
    color: '#6366F1',
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    gap: 4,
  },
  statusText: {
    fontSize: 12,
    fontWeight: '600',
    textTransform: 'capitalize',
  },
  customerInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 8,
  },
  customerName: {
    fontSize: 14,
    fontWeight: '500',
    color: '#374151',
  },
  separator: {
    color: '#9CA3AF',
  },
  customerPhone: {
    fontSize: 13,
    color: '#6B7280',
  },
  orderDetails: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: '#F3F4F6',
  },
  detailItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  detailText: {
    fontSize: 13,
    color: '#6B7280',
  },
  totalAmount: {
    fontSize: 18,
    fontWeight: '700',
    color: '#111827',
  },
  refundAmount: {
    fontSize: 13,
    color: '#EF4444',
    marginLeft: 4,
  },
  orderFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  orderTime: {
    fontSize: 12,
    color: '#9CA3AF',
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingTop: 80,
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#374151',
    marginTop: 16,
  },
  emptyText: {
    fontSize: 14,
    color: '#9CA3AF',
    marginTop: 4,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: '#FFF',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 20,
    maxHeight: '90%',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#111827',
  },
  section: {
    marginBottom: 20,
  },
  orderTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  multiOrderInfoBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#EEF2FF',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    gap: 4,
  },
  multiOrderInfoText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#6366F1',
  },
  multiOrderNote: {
    fontSize: 13,
    color: '#6B7280',
    marginTop: 8,
    fontStyle: 'italic',
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#6B7280',
    marginBottom: 8,
    textTransform: 'uppercase',
  },
  infoText: {
    fontSize: 16,
    fontWeight: '500',
    color: '#111827',
  },
  infoTextSecondary: {
    fontSize: 14,
    color: '#6B7280',
    marginTop: 2,
  },
  itemRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#F3F4F6',
  },
  itemInfo: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  itemName: {
    fontSize: 14,
    fontWeight: '500',
    color: '#374151',
  },
  itemQty: {
    fontSize: 13,
    color: '#6B7280',
  },
  itemPrice: {
    fontSize: 14,
    fontWeight: '600',
    color: '#111827',
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
  grandTotal: {
    marginTop: 8,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#E5E7EB',
  },
  grandTotalLabel: {
    fontSize: 16,
    fontWeight: '600',
    color: '#111827',
  },
  grandTotalValue: {
    fontSize: 18,
    fontWeight: '700',
    color: '#111827',
  },
  actionButtons: {
    marginTop: 16,
    gap: 10,
  },
  actionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 14,
    borderRadius: 12,
    gap: 8,
  },
  confirmBtn: {
    backgroundColor: '#10B981',
  },
  modifyBtn: {
    backgroundColor: '#F59E0B',
  },
  refundBtn: {
    backgroundColor: '#EF4444',
  },
  genieBtn: {
    backgroundColor: '#6366F1',
  },
  actionBtnText: {
    color: '#FFF',
    fontSize: 15,
    fontWeight: '600',
  },
  deliveryLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: '#374151',
    marginBottom: 10,
    textAlign: 'center',
  },
  autoSearchNote: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#EEF2FF',
    padding: 12,
    borderRadius: 8,
    marginTop: 8,
    gap: 8,
  },
  autoSearchText: {
    flex: 1,
    fontSize: 13,
    color: '#6366F1',
  },
  genieInfoBox: {
    backgroundColor: '#EEF2FF',
    padding: 16,
    borderRadius: 12,
    marginTop: 10,
    alignItems: 'center',
  },
  genieAssignedHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
  },
  genieAssignedTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#10B981',
  },
  genieInfoTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#6366F1',
    marginBottom: 8,
  },
  genieInfoText: {
    fontSize: 16,
    fontWeight: '500',
    color: '#111827',
  },
  genieStatusText: {
    fontSize: 13,
    color: '#6B7280',
    marginTop: 6,
    textTransform: 'capitalize',
  },
  modifyHint: {
    fontSize: 13,
    color: '#6B7280',
    marginBottom: 16,
    backgroundColor: '#FEF3C7',
    padding: 12,
    borderRadius: 8,
  },
  modifyItemRow: {
    marginBottom: 16,
    padding: 12,
    backgroundColor: '#F9FAFB',
    borderRadius: 12,
  },
  modifyItemInfo: {
    marginBottom: 8,
  },
  modifyItemName: {
    fontSize: 15,
    fontWeight: '600',
    color: '#111827',
  },
  modifyItemPrice: {
    fontSize: 13,
    color: '#6B7280',
  },
  modifyControls: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginBottom: 8,
  },
  qtyBtn: {
    width: 36,
    height: 36,
    backgroundColor: '#EEF2FF',
    borderRadius: 18,
    justifyContent: 'center',
    alignItems: 'center',
  },
  qtyText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#111827',
    minWidth: 30,
    textAlign: 'center',
  },
  reasonInput: {
    backgroundColor: '#FFF',
    borderWidth: 1,
    borderColor: '#E5E7EB',
    borderRadius: 8,
    padding: 10,
    fontSize: 14,
  },
  overallReasonInput: {
    backgroundColor: '#FFF',
    borderWidth: 1,
    borderColor: '#E5E7EB',
    borderRadius: 8,
    padding: 12,
    fontSize: 14,
    minHeight: 80,
    textAlignVertical: 'top',
    marginTop: 8,
  },
  saveModifyBtn: {
    backgroundColor: '#6366F1',
    padding: 16,
    borderRadius: 12,
    alignItems: 'center',
    marginTop: 16,
  },
  saveModifyBtnText: {
    color: '#FFF',
    fontSize: 16,
    fontWeight: '600',
  },
});
