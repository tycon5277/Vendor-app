import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
  Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { orderAPI, chatAPI } from '../../../src/utils/api';
import { Order } from '../../../src/types';
import { StatusBadge } from '../../../src/components/StatusBadge';
import { LoadingScreen } from '../../../src/components/LoadingScreen';
import { format } from 'date-fns';

export default function OrderDetailScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const [order, setOrder] = useState<Order | null>(null);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);

  const loadOrder = async () => {
    try {
      const response = await orderAPI.getOne(id || '');
      setOrder(response.data);
    } catch (error) {
      Alert.alert('Error', 'Failed to load order');
      router.back();
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadOrder();
  }, [id]);

  const handleAccept = async () => {
    setUpdating(true);
    try {
      await orderAPI.accept(id || '');
      Alert.alert('Success', 'Order accepted!');
      loadOrder();
    } catch (error: any) {
      Alert.alert('Error', error.response?.data?.detail || 'Failed to accept order');
    } finally {
      setUpdating(false);
    }
  };

  const handleReject = () => {
    Alert.alert(
      'Reject Order',
      'Are you sure you want to reject this order?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Reject',
          style: 'destructive',
          onPress: async () => {
            setUpdating(true);
            try {
              await orderAPI.reject(id || '');
              Alert.alert('Order Rejected');
              router.back();
            } catch (error) {
              Alert.alert('Error', 'Failed to reject order');
            } finally {
              setUpdating(false);
            }
          },
        },
      ]
    );
  };

  const handleUpdateStatus = async (newStatus: string) => {
    setUpdating(true);
    try {
      await orderAPI.updateStatus(id || '', newStatus);
      Alert.alert('Success', `Order marked as ${newStatus}`);
      loadOrder();
    } catch (error) {
      Alert.alert('Error', 'Failed to update order');
    } finally {
      setUpdating(false);
    }
  };

  const handleCall = () => {
    if (order?.customer_phone) {
      Linking.openURL(`tel:${order.customer_phone}`);
    }
  };

  const handleChat = async () => {
    try {
      const response = await chatAPI.createRoom(id || '');
      router.push(`/(main)/chats?room=${response.data.room_id}`);
    } catch (error) {
      Alert.alert('Error', 'Failed to start chat');
    }
  };

  const handleRequestAgent = async () => {
    try {
      const response = await orderAPI.requestAgent(id || '');
      if (response.data.agents_found > 0) {
        Alert.alert('Agents Available', `Found ${response.data.agents_found} delivery agents nearby. They will be notified.`);
      } else {
        Alert.alert('No Agents', 'No delivery agents available right now. Try again later.');
      }
    } catch (error) {
      Alert.alert('Error', 'Failed to request agent');
    }
  };

  if (loading) {
    return <LoadingScreen message="Loading order..." />;
  }

  if (!order) {
    return null;
  }

  const getNextStatusButton = () => {
    switch (order.status) {
      case 'confirmed':
        return { label: 'Start Preparing', status: 'preparing', icon: 'flame' };
      case 'preparing':
        return { label: 'Mark Ready', status: 'ready', icon: 'checkmark-circle' };
      case 'ready':
        if (order.delivery_type === 'self_pickup') {
          return { label: 'Complete Order', status: 'delivered', icon: 'checkmark-done' };
        }
        return { label: 'Hand to Delivery', status: 'out_for_delivery', icon: 'bicycle' };
      default:
        return null;
    }
  };

  const nextStatus = getNextStatusButton();

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity style={styles.backBtn} onPress={() => router.back()}>
          <Ionicons name="arrow-back" size={24} color="#374151" />
        </TouchableOpacity>
        <Text style={styles.title}>Order Details</Text>
        <View style={{ width: 44 }} />
      </View>

      <ScrollView style={styles.scrollView} showsVerticalScrollIndicator={false}>
        {/* Order Info */}
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <Text style={styles.orderId}>#{order.order_id.slice(-8).toUpperCase()}</Text>
            <StatusBadge status={order.status} />
          </View>
          <Text style={styles.orderTime}>
            {format(new Date(order.created_at), 'MMMM d, yyyy \u2022 h:mm a')}
          </Text>
        </View>

        {/* Customer Info */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Customer</Text>
          <View style={styles.customerRow}>
            <View style={styles.customerAvatar}>
              <Ionicons name="person" size={24} color="#6366F1" />
            </View>
            <View style={styles.customerInfo}>
              <Text style={styles.customerName}>{order.customer_name || 'Customer'}</Text>
              <Text style={styles.customerPhone}>{order.customer_phone || 'No phone'}</Text>
            </View>
            <View style={styles.customerActions}>
              <TouchableOpacity style={styles.iconBtn} onPress={handleCall}>
                <Ionicons name="call" size={20} color="#22C55E" />
              </TouchableOpacity>
              <TouchableOpacity style={styles.iconBtn} onPress={handleChat}>
                <Ionicons name="chatbubble" size={20} color="#6366F1" />
              </TouchableOpacity>
            </View>
          </View>
        </View>

        {/* Delivery Info */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Delivery</Text>
          <View style={styles.deliveryRow}>
            <Ionicons
              name={order.delivery_type === 'self_pickup' ? 'storefront' : 'location'}
              size={20}
              color="#6366F1"
            />
            <View style={styles.deliveryInfo}>
              <Text style={styles.deliveryType}>
                {order.delivery_type === 'self_pickup' ? 'Self Pickup' : 'Home Delivery'}
              </Text>
              <Text style={styles.deliveryAddress}>{order.delivery_address?.address}</Text>
            </View>
          </View>
          {order.delivery_type !== 'self_pickup' && order.status === 'ready' && !order.assigned_agent_id && (
            <TouchableOpacity style={styles.requestAgentBtn} onPress={handleRequestAgent}>
              <Ionicons name="bicycle" size={20} color="#6366F1" />
              <Text style={styles.requestAgentText}>Request Delivery Agent</Text>
            </TouchableOpacity>
          )}
        </View>

        {/* Order Items */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Items ({order.items.length})</Text>
          {order.items.map((item, idx) => (
            <View key={idx} style={styles.itemRow}>
              <View style={styles.itemQuantity}>
                <Text style={styles.itemQuantityText}>{item.quantity}x</Text>
              </View>
              <Text style={styles.itemName}>{item.name}</Text>
              <Text style={styles.itemPrice}>₹{item.price * item.quantity}</Text>
            </View>
          ))}
          <View style={styles.divider} />
          <View style={styles.totalRow}>
            <Text style={styles.totalLabel}>Subtotal</Text>
            <Text style={styles.totalValue}>₹{order.total_amount - order.delivery_fee}</Text>
          </View>
          <View style={styles.totalRow}>
            <Text style={styles.totalLabel}>Delivery Fee</Text>
            <Text style={styles.totalValue}>₹{order.delivery_fee}</Text>
          </View>
          <View style={[styles.totalRow, styles.grandTotalRow]}>
            <Text style={styles.grandTotalLabel}>Total</Text>
            <Text style={styles.grandTotalValue}>₹{order.total_amount}</Text>
          </View>
        </View>

        {/* Status History */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Status History</Text>
          {order.status_history?.map((entry, idx) => (
            <View key={idx} style={styles.historyRow}>
              <View style={styles.historyDot} />
              <View style={styles.historyContent}>
                <Text style={styles.historyStatus}>{entry.status.replace(/_/g, ' ')}</Text>
                <Text style={styles.historyTime}>
                  {format(new Date(entry.timestamp), 'MMM d, h:mm a')}
                </Text>
              </View>
            </View>
          ))}
        </View>

        <View style={{ height: 120 }} />
      </ScrollView>

      {/* Action Buttons */}
      {order.status === 'pending' && (
        <View style={styles.actionBar}>
          <TouchableOpacity
            style={[styles.actionBtn, styles.rejectBtn]}
            onPress={handleReject}
            disabled={updating}
          >
            <Text style={styles.rejectBtnText}>Reject</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.actionBtn, styles.acceptBtn]}
            onPress={handleAccept}
            disabled={updating}
          >
            <Text style={styles.acceptBtnText}>{updating ? 'Processing...' : 'Accept Order'}</Text>
          </TouchableOpacity>
        </View>
      )}

      {nextStatus && (
        <View style={styles.actionBar}>
          <TouchableOpacity
            style={[styles.actionBtn, styles.nextBtn]}
            onPress={() => handleUpdateStatus(nextStatus.status)}
            disabled={updating}
          >
            <Ionicons name={nextStatus.icon as any} size={24} color="#FFFFFF" />
            <Text style={styles.nextBtnText}>
              {updating ? 'Updating...' : nextStatus.label}
            </Text>
          </TouchableOpacity>
        </View>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F9FAFB',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  backBtn: {
    width: 44,
    height: 44,
    justifyContent: 'center',
    alignItems: 'center',
  },
  title: {
    fontSize: 18,
    fontWeight: '700',
    color: '#111827',
  },
  scrollView: {
    flex: 1,
    paddingHorizontal: 16,
  },
  card: {
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
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  orderId: {
    fontSize: 20,
    fontWeight: '700',
    color: '#6366F1',
  },
  orderTime: {
    fontSize: 13,
    color: '#6B7280',
    marginTop: 4,
  },
  cardTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#6B7280',
    marginBottom: 12,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  customerRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  customerAvatar: {
    width: 48,
    height: 48,
    backgroundColor: '#EEF2FF',
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
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
    fontSize: 14,
    color: '#6B7280',
    marginTop: 2,
  },
  customerActions: {
    flexDirection: 'row',
    gap: 8,
  },
  iconBtn: {
    width: 40,
    height: 40,
    backgroundColor: '#F3F4F6',
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
  },
  deliveryRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 12,
  },
  deliveryInfo: {
    flex: 1,
  },
  deliveryType: {
    fontSize: 15,
    fontWeight: '600',
    color: '#111827',
  },
  deliveryAddress: {
    fontSize: 14,
    color: '#6B7280',
    marginTop: 4,
    lineHeight: 20,
  },
  requestAgentBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#EEF2FF',
    borderRadius: 12,
    paddingVertical: 12,
    marginTop: 16,
    gap: 8,
  },
  requestAgentText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#6366F1',
  },
  itemRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#F3F4F6',
  },
  itemQuantity: {
    width: 32,
    height: 32,
    backgroundColor: '#F3F4F6',
    borderRadius: 8,
    justifyContent: 'center',
    alignItems: 'center',
  },
  itemQuantityText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#374151',
  },
  itemName: {
    flex: 1,
    fontSize: 15,
    color: '#111827',
    marginLeft: 12,
  },
  itemPrice: {
    fontSize: 15,
    fontWeight: '600',
    color: '#111827',
  },
  divider: {
    height: 1,
    backgroundColor: '#E5E7EB',
    marginVertical: 12,
  },
  totalRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 4,
  },
  totalLabel: {
    fontSize: 14,
    color: '#6B7280',
  },
  totalValue: {
    fontSize: 14,
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
    fontWeight: '700',
    color: '#111827',
  },
  historyRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    paddingVertical: 8,
  },
  historyDot: {
    width: 8,
    height: 8,
    backgroundColor: '#6366F1',
    borderRadius: 4,
    marginTop: 6,
  },
  historyContent: {
    marginLeft: 12,
  },
  historyStatus: {
    fontSize: 14,
    fontWeight: '600',
    color: '#111827',
    textTransform: 'capitalize',
  },
  historyTime: {
    fontSize: 12,
    color: '#9CA3AF',
    marginTop: 2,
  },
  actionBar: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    flexDirection: 'row',
    padding: 16,
    backgroundColor: '#FFFFFF',
    borderTopWidth: 1,
    borderTopColor: '#E5E7EB',
    gap: 12,
  },
  actionBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 16,
    borderRadius: 12,
    gap: 8,
  },
  rejectBtn: {
    backgroundColor: '#FEE2E2',
  },
  rejectBtnText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#DC2626',
  },
  acceptBtn: {
    backgroundColor: '#22C55E',
    flex: 2,
  },
  acceptBtnText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  nextBtn: {
    backgroundColor: '#6366F1',
  },
  nextBtnText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFFFFF',
  },
});
