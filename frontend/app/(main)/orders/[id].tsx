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
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { useFocusEffect } from '@react-navigation/native';
import { Ionicons } from '@expo/vector-icons';
import { orderAPI } from '../../../src/utils/api';
import { useAlert } from '../../../src/context/AlertContext';
import { format } from 'date-fns';

const { width } = Dimensions.get('window');

interface StatusCheckpoint {
  key: string;
  label: string;
  icon: string;
  description: string;
  completed: boolean;
  current: boolean;
  timestamp?: string;
}

interface DeliveryOption {
  type: string;
  label: string;
  description: string;
  available: boolean;
  selected: boolean;
  icon?: string;
  color?: string;
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
  const [checkpoints, setCheckpoints] = useState<StatusCheckpoint[]>([]);
  const [deliveryOptions, setDeliveryOptions] = useState<DeliveryOption[]>([]);
  const [nextActions, setNextActions] = useState<NextAction[]>([]);
  const [vendorCanDeliver, setVendorCanDeliver] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [showDeliveryModal, setShowDeliveryModal] = useState(false);
  
  const progressAnim = useRef(new Animated.Value(0)).current;

  const loadOrderDetails = async () => {
    if (!params.id) return;
    
    try {
      const response = await orderAPI.getDetails(params.id);
      setOrder(response.data.order);
      setCheckpoints(response.data.status_checkpoints);
      setDeliveryOptions(response.data.delivery_options);
      setNextActions(response.data.next_actions);
      setVendorCanDeliver(response.data.vendor_can_deliver);
      
      // Animate progress
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
      
      // Auto-refresh every 10 seconds for live tracking
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
    setShowDeliveryModal(false);
    
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
          <Text style={styles.orderNumber}>Order #{order.order_id?.slice(-8)}</Text>
          <View style={[styles.statusBadge, { backgroundColor: statusColor + '20' }]}>
            <View style={[styles.statusDot, { backgroundColor: statusColor }]} />
            <Text style={[styles.statusText, { color: statusColor }]}>
              {order.status?.replace(/_/g, ' ').toUpperCase()}
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
        {/* Progress Tracker */}
        <View style={styles.progressCard}>
          <View style={styles.progressHeader}>
            <Text style={styles.progressTitle}>Order Progress</Text>
            <Text style={styles.progressPercent}>
              {Math.round((checkpoints.filter(c => c.completed).length / checkpoints.length) * 100)}%
            </Text>
          </View>
          <View style={styles.progressBarBg}>
            <Animated.View 
              style={[
                styles.progressBarFill,
                {
                  width: progressAnim.interpolate({
                    inputRange: [0, 1],
                    outputRange: ['0%', '100%'],
                  }),
                }
              ]} 
            />
          </View>
        </View>

        {/* Status Checkpoints */}
        <View style={styles.checkpointsCard}>
          <Text style={styles.sectionTitle}>Status Timeline</Text>
          
          {checkpoints.map((checkpoint, index) => (
            <View key={checkpoint.key} style={styles.checkpointRow}>
              {/* Connector Line */}
              {index > 0 && (
                <View style={[
                  styles.connectorLine,
                  checkpoint.completed && styles.connectorLineCompleted
                ]} />
              )}
              
              {/* Checkpoint Circle */}
              <View style={[
                styles.checkpointCircle,
                checkpoint.completed && styles.checkpointCircleCompleted,
                checkpoint.current && styles.checkpointCircleCurrent,
              ]}>
                {checkpoint.completed ? (
                  <Ionicons name="checkmark" size={16} color="#FFFFFF" />
                ) : (
                  <Ionicons 
                    name={checkpoint.icon as any} 
                    size={16} 
                    color={checkpoint.current ? '#6366F1' : '#9CA3AF'} 
                  />
                )}
              </View>
              
              {/* Checkpoint Content */}
              <View style={styles.checkpointContent}>
                <Text style={[
                  styles.checkpointLabel,
                  checkpoint.completed && styles.checkpointLabelCompleted,
                  checkpoint.current && styles.checkpointLabelCurrent,
                ]}>
                  {checkpoint.label}
                </Text>
                <Text style={styles.checkpointDesc}>{checkpoint.description}</Text>
                {checkpoint.timestamp && (
                  <Text style={styles.checkpointTime}>
                    {format(new Date(checkpoint.timestamp), 'h:mm a')}
                  </Text>
                )}
              </View>
            </View>
          ))}
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
                <Text style={styles.deliveryTitle}>Delivery Assignment</Text>
                <Text style={styles.deliverySubtitle}>
                  {order.assigned_agent_id 
                    ? `Assigned to ${order.agent_name || 'Carpet Genie'}`
                    : 'Choose delivery method'}
                </Text>
              </View>
            </View>
            
            {!order.assigned_agent_id && order.delivery_method !== 'self' && (
              <View style={styles.deliveryOptions}>
                {vendorCanDeliver && (
                  <TouchableOpacity 
                    style={styles.deliveryOptionBtn}
                    onPress={() => handleAssignDelivery('self_delivery')}
                    disabled={actionLoading}
                  >
                    <View style={[styles.deliveryOptionIcon, { backgroundColor: '#DBEAFE' }]}>
                      <Ionicons name="car" size={20} color="#3B82F6" />
                    </View>
                    <View style={styles.deliveryOptionContent}>
                      <Text style={styles.deliveryOptionTitle}>Own Delivery</Text>
                      <Text style={styles.deliveryOptionSubtitle}>Use your delivery service</Text>
                    </View>
                    <Ionicons name="chevron-forward" size={20} color="#9CA3AF" />
                  </TouchableOpacity>
                )}
                
                <TouchableOpacity 
                  style={[styles.deliveryOptionBtn, styles.deliveryOptionBtnGenie]}
                  onPress={() => handleAssignDelivery('carpet_genie')}
                  disabled={actionLoading}
                >
                  <View style={[styles.deliveryOptionIcon, { backgroundColor: '#DCFCE7' }]}>
                    <Ionicons name="bicycle" size={20} color="#22C55E" />
                  </View>
                  <View style={styles.deliveryOptionContent}>
                    <Text style={styles.deliveryOptionTitle}>Carpet Genie</Text>
                    <Text style={styles.deliveryOptionSubtitle}>Assign to Genie delivery</Text>
                  </View>
                  <View style={styles.recommendedBadge}>
                    <Text style={styles.recommendedText}>Recommended</Text>
                  </View>
                </TouchableOpacity>
              </View>
            )}

            {(order.assigned_agent_id || order.delivery_method === 'self') && (
              <View style={styles.agentCard}>
                <View style={styles.agentAvatar}>
                  <Ionicons name={order.delivery_method === 'self' ? 'car' : 'person'} size={24} color="#FFFFFF" />
                </View>
                <View style={styles.agentInfo}>
                  <Text style={styles.agentName}>
                    {order.delivery_method === 'self' ? 'Your Delivery' : (order.agent_name || 'Carpet Genie Agent')}
                  </Text>
                  <Text style={styles.agentPhone}>
                    {order.delivery_method === 'self' ? 'Own delivery service' : (order.agent_phone || 'Finding agent...')}
                  </Text>
                </View>
                {order.agent_phone && (
                  <TouchableOpacity style={styles.callAgentBtn}>
                    <Ionicons name="call" size={18} color="#22C55E" />
                  </TouchableOpacity>
                )}
              </View>
            )}
          </View>
        )}

        {/* Order Details */}
        <View style={styles.detailsCard}>
          <Text style={styles.sectionTitle}>Order Details</Text>
          
          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Customer</Text>
            <Text style={styles.detailValue}>{order.customer_name || 'Customer'}</Text>
          </View>
          
          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Phone</Text>
            <TouchableOpacity>
              <Text style={[styles.detailValue, styles.detailValueLink]}>
                {order.customer_phone || 'N/A'}
              </Text>
            </TouchableOpacity>
          </View>
          
          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Delivery Type</Text>
            <Text style={styles.detailValue}>
              {order.delivery_type === 'self_pickup' ? 'Customer Pickup' :
               order.delivery_method === 'self' ? 'Your Delivery' :
               order.delivery_method === 'carpet_genie' ? 'Carpet Genie' :
               order.delivery_type === 'vendor_delivery' ? 'Your Delivery' :
               order.delivery_type === 'agent_delivery' ? 'Carpet Genie' : 'Pending'}
            </Text>
          </View>
          
          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Total Amount</Text>
            <Text style={[styles.detailValue, styles.detailValueAmount]}>
              ₹{order.total_amount?.toFixed(2)}
            </Text>
          </View>
          
          {order.special_instructions && (
            <View style={styles.instructionsBox}>
              <Text style={styles.instructionsLabel}>Special Instructions</Text>
              <Text style={styles.instructionsText}>{order.special_instructions}</Text>
            </View>
          )}
        </View>

        {/* Items */}
        <View style={styles.itemsCard}>
          <Text style={styles.sectionTitle}>Items ({order.items?.length || 0})</Text>
          
          {order.items?.map((item: any, index: number) => (
            <View key={index} style={styles.itemRow}>
              <View style={styles.itemQty}>
                <Text style={styles.itemQtyText}>{item.quantity}x</Text>
              </View>
              <View style={styles.itemInfo}>
                <Text style={styles.itemName}>{item.name}</Text>
                {item.notes && <Text style={styles.itemNotes}>{item.notes}</Text>}
              </View>
              <Text style={styles.itemPrice}>₹{(item.price * item.quantity).toFixed(2)}</Text>
            </View>
          ))}
        </View>

        {/* Extra spacing for bottom actions */}
        <View style={{ height: 120 }} />
      </ScrollView>

      {/* Bottom Action Buttons OR Carpet Genie Status */}
      {nextActions.length > 0 ? (
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
              onPress={() => {
                if (action.action === 'assign_delivery') {
                  setShowDeliveryModal(true);
                } else {
                  handleAction(action.action);
                }
              }}
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
      ) : (
        /* Show Carpet Genie status when no actions available */
        (order.delivery_method === 'carpet_genie' || 
         (order.delivery_type === 'agent_delivery' && order.assigned_agent_id)) &&
        ['awaiting_pickup', 'picked_up', 'out_for_delivery'].includes(order.status) && (
          <View style={[styles.bottomStatusBar, { paddingBottom: Math.max(insets.bottom, 16) }]}>
            <View style={styles.carpetGenieStatusContainer}>
              <View style={styles.carpetGenieIconContainer}>
                <Ionicons name="bicycle" size={24} color="#22C55E" />
              </View>
              <View style={styles.carpetGenieStatusContent}>
                <Text style={styles.carpetGenieStatusTitle}>
                  {order.status === 'awaiting_pickup' && 'Waiting for Pickup'}
                  {order.status === 'picked_up' && 'Order Picked Up'}
                  {order.status === 'out_for_delivery' && 'On The Way'}
                </Text>
                <Text style={styles.carpetGenieStatusSubtitle}>
                  {order.agent_name ? `${order.agent_name} will update the status` : 'Carpet Genie agent will update'}
                </Text>
              </View>
              <View style={styles.liveIndicator}>
                <View style={styles.liveDot} />
                <Text style={styles.liveText}>LIVE</Text>
              </View>
            </View>
          </View>
        )
      )}

      {/* Delivery Options Modal */}
      <Modal
        visible={showDeliveryModal}
        transparent
        animationType="slide"
        onRequestClose={() => setShowDeliveryModal(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Assign Delivery</Text>
              <TouchableOpacity onPress={() => setShowDeliveryModal(false)}>
                <Ionicons name="close" size={24} color="#6B7280" />
              </TouchableOpacity>
            </View>
            
            <Text style={styles.modalSubtitle}>Choose how to deliver this order</Text>
            
            <View style={styles.modalOptions}>
              {vendorCanDeliver && (
                <TouchableOpacity 
                  style={styles.modalOption}
                  onPress={() => handleAssignDelivery('self_delivery')}
                >
                  <View style={[styles.modalOptionIcon, { backgroundColor: '#DBEAFE' }]}>
                    <Ionicons name="car" size={28} color="#3B82F6" />
                  </View>
                  <Text style={styles.modalOptionTitle}>Own Delivery</Text>
                  <Text style={styles.modalOptionSubtitle}>Use your delivery service</Text>
                </TouchableOpacity>
              )}
              
              <TouchableOpacity 
                style={[styles.modalOption, styles.modalOptionHighlighted]}
                onPress={() => handleAssignDelivery('carpet_genie')}
              >
                <View style={[styles.modalOptionIcon, { backgroundColor: '#DCFCE7' }]}>
                  <Ionicons name="bicycle" size={28} color="#22C55E" />
                </View>
                <Text style={styles.modalOptionTitle}>Carpet Genie</Text>
                <Text style={styles.modalOptionSubtitle}>Fast & reliable delivery</Text>
                <View style={styles.modalRecommendedBadge}>
                  <Ionicons name="star" size={12} color="#F59E0B" />
                  <Text style={styles.modalRecommendedText}>Recommended</Text>
                </View>
              </TouchableOpacity>
            </View>
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
    fontSize: 16,
    color: '#6B7280',
  },
  errorContainer: {
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 32,
  },
  errorTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#374151',
    marginTop: 16,
  },
  backButton: {
    marginTop: 20,
    paddingHorizontal: 24,
    paddingVertical: 12,
    backgroundColor: '#6366F1',
    borderRadius: 12,
  },
  backButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFFFFF',
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
    justifyContent: 'center',
    alignItems: 'center',
  },
  headerContent: {
    flex: 1,
    marginLeft: 4,
  },
  orderNumber: {
    fontSize: 18,
    fontWeight: '700',
    color: '#111827',
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    marginTop: 4,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 6,
  },
  statusText: {
    fontSize: 12,
    fontWeight: '700',
  },
  refreshBtn: {
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
  progressCard: {
    backgroundColor: '#FFFFFF',
    margin: 16,
    marginBottom: 8,
    padding: 16,
    borderRadius: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 8,
    elevation: 2,
  },
  progressHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  progressTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#111827',
  },
  progressPercent: {
    fontSize: 16,
    fontWeight: '700',
    color: '#6366F1',
  },
  progressBarBg: {
    height: 8,
    backgroundColor: '#E5E7EB',
    borderRadius: 4,
    overflow: 'hidden',
  },
  progressBarFill: {
    height: '100%',
    backgroundColor: '#6366F1',
    borderRadius: 4,
  },
  checkpointsCard: {
    backgroundColor: '#FFFFFF',
    marginHorizontal: 16,
    marginVertical: 8,
    padding: 16,
    borderRadius: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 8,
    elevation: 2,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#111827',
    marginBottom: 16,
  },
  checkpointRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: 20,
    position: 'relative',
  },
  connectorLine: {
    position: 'absolute',
    left: 15,
    top: -20,
    width: 2,
    height: 20,
    backgroundColor: '#E5E7EB',
  },
  connectorLineCompleted: {
    backgroundColor: '#22C55E',
  },
  checkpointCircle: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: '#F3F4F6',
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 2,
    borderColor: '#E5E7EB',
  },
  checkpointCircleCompleted: {
    backgroundColor: '#22C55E',
    borderColor: '#22C55E',
  },
  checkpointCircleCurrent: {
    backgroundColor: '#FFFFFF',
    borderColor: '#6366F1',
    borderWidth: 3,
  },
  checkpointContent: {
    flex: 1,
    marginLeft: 12,
  },
  checkpointLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: '#9CA3AF',
  },
  checkpointLabelCompleted: {
    color: '#374151',
  },
  checkpointLabelCurrent: {
    color: '#6366F1',
    fontWeight: '700',
  },
  checkpointDesc: {
    fontSize: 12,
    color: '#9CA3AF',
    marginTop: 2,
  },
  checkpointTime: {
    fontSize: 11,
    color: '#22C55E',
    fontWeight: '600',
    marginTop: 4,
  },
  deliveryCard: {
    backgroundColor: '#FFFFFF',
    marginHorizontal: 16,
    marginVertical: 8,
    padding: 16,
    borderRadius: 16,
    borderWidth: 2,
    borderColor: '#22C55E',
    shadowColor: '#22C55E',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 3,
  },
  deliveryHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 16,
  },
  deliveryIconBg: {
    width: 48,
    height: 48,
    backgroundColor: '#DCFCE7',
    borderRadius: 14,
    justifyContent: 'center',
    alignItems: 'center',
  },
  deliveryHeaderContent: {
    flex: 1,
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
    gap: 10,
  },
  deliveryOptionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 14,
    backgroundColor: '#F9FAFB',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  deliveryOptionBtnGenie: {
    backgroundColor: '#F0FDF4',
    borderColor: '#BBF7D0',
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
    marginTop: 2,
  },
  recommendedBadge: {
    backgroundColor: '#FEF3C7',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
  },
  recommendedText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#D97706',
  },
  agentCard: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 14,
    backgroundColor: '#F0FDF4',
    borderRadius: 12,
  },
  agentAvatar: {
    width: 44,
    height: 44,
    backgroundColor: '#22C55E',
    borderRadius: 22,
    justifyContent: 'center',
    alignItems: 'center',
  },
  agentInfo: {
    flex: 1,
    marginLeft: 12,
  },
  agentName: {
    fontSize: 15,
    fontWeight: '600',
    color: '#111827',
  },
  agentPhone: {
    fontSize: 13,
    color: '#6B7280',
    marginTop: 2,
  },
  callAgentBtn: {
    width: 40,
    height: 40,
    backgroundColor: '#DCFCE7',
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
  },
  detailsCard: {
    backgroundColor: '#FFFFFF',
    marginHorizontal: 16,
    marginVertical: 8,
    padding: 16,
    borderRadius: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 8,
    elevation: 2,
  },
  detailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#F3F4F6',
  },
  detailLabel: {
    fontSize: 14,
    color: '#6B7280',
  },
  detailValue: {
    fontSize: 14,
    fontWeight: '600',
    color: '#111827',
  },
  detailValueLink: {
    color: '#6366F1',
  },
  detailValueAmount: {
    fontSize: 16,
    fontWeight: '700',
    color: '#22C55E',
  },
  instructionsBox: {
    marginTop: 12,
    padding: 12,
    backgroundColor: '#FEF3C7',
    borderRadius: 10,
  },
  instructionsLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: '#92400E',
    marginBottom: 4,
  },
  instructionsText: {
    fontSize: 14,
    color: '#78350F',
  },
  itemsCard: {
    backgroundColor: '#FFFFFF',
    marginHorizontal: 16,
    marginVertical: 8,
    padding: 16,
    borderRadius: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 8,
    elevation: 2,
  },
  itemRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#F3F4F6',
  },
  itemQty: {
    width: 36,
    height: 36,
    backgroundColor: '#EEF2FF',
    borderRadius: 10,
    justifyContent: 'center',
    alignItems: 'center',
  },
  itemQtyText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#6366F1',
  },
  itemInfo: {
    flex: 1,
    marginLeft: 12,
  },
  itemName: {
    fontSize: 14,
    fontWeight: '600',
    color: '#111827',
  },
  itemNotes: {
    fontSize: 12,
    color: '#6B7280',
    marginTop: 2,
  },
  itemPrice: {
    fontSize: 14,
    fontWeight: '600',
    color: '#111827',
  },
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
    shadowColor: '#000',
    shadowOffset: { width: 0, height: -4 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 8,
  },
  actionBtn: {
    flex: 1,
    paddingVertical: 16,
    borderRadius: 14,
    backgroundColor: '#F3F4F6',
    alignItems: 'center',
    justifyContent: 'center',
  },
  actionBtnPrimary: {
    backgroundColor: '#6366F1',
  },
  actionBtnDestructive: {
    backgroundColor: '#FEE2E2',
  },
  actionBtnText: {
    fontSize: 16,
    fontWeight: '700',
    color: '#374151',
  },
  actionBtnTextPrimary: {
    color: '#FFFFFF',
  },
  actionBtnTextDestructive: {
    color: '#DC2626',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: '#FFFFFF',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 20,
    paddingBottom: 40,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#111827',
  },
  modalSubtitle: {
    fontSize: 14,
    color: '#6B7280',
    marginBottom: 20,
  },
  modalOptions: {
    flexDirection: 'row',
    gap: 12,
  },
  modalOption: {
    flex: 1,
    alignItems: 'center',
    padding: 20,
    backgroundColor: '#F9FAFB',
    borderRadius: 16,
    borderWidth: 2,
    borderColor: '#E5E7EB',
  },
  modalOptionHighlighted: {
    backgroundColor: '#F0FDF4',
    borderColor: '#22C55E',
  },
  modalOptionIcon: {
    width: 60,
    height: 60,
    borderRadius: 18,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 12,
  },
  modalOptionTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#111827',
    marginBottom: 4,
  },
  modalOptionSubtitle: {
    fontSize: 12,
    color: '#6B7280',
    textAlign: 'center',
  },
  modalRecommendedBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
    gap: 4,
  },
  modalRecommendedText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#F59E0B',
  },
  // Carpet Genie Status Bar Styles
  bottomStatusBar: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    padding: 16,
    backgroundColor: '#FFFFFF',
    borderTopWidth: 1,
    borderTopColor: '#E5E7EB',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: -4 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 8,
  },
  carpetGenieStatusContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F0FDF4',
    borderRadius: 16,
    padding: 16,
    borderWidth: 2,
    borderColor: '#22C55E',
  },
  carpetGenieIconContainer: {
    width: 48,
    height: 48,
    backgroundColor: '#DCFCE7',
    borderRadius: 14,
    justifyContent: 'center',
    alignItems: 'center',
  },
  carpetGenieStatusContent: {
    flex: 1,
    marginLeft: 12,
  },
  carpetGenieStatusTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#166534',
  },
  carpetGenieStatusSubtitle: {
    fontSize: 13,
    color: '#15803D',
    marginTop: 2,
  },
  liveIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#DCFCE7',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 12,
    gap: 6,
  },
  liveDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#22C55E',
  },
  liveText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#22C55E',
  },
});
