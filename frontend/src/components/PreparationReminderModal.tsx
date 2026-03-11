import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Modal,
  TouchableOpacity,
  Animated,
  Vibration,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useTheme } from '../context/ThemeContext';
import { orderAPI } from '../utils/api';

interface DelayedOrder {
  order_id: string;
  customer_name: string;
  items_count: number;
  total: number;
  accepted_at: string;
  waiting_minutes: number;
  urgency: 'medium' | 'high' | 'critical';
  snooze_count: number;
  items_summary: string;
}

interface PreparationReminderModalProps {
  visible: boolean;
  order: DelayedOrder | null;
  onClose: () => void;
  onStartPreparing: () => void;
  onSnooze: () => void;
}

export default function PreparationReminderModal({ 
  visible, 
  order, 
  onClose, 
  onStartPreparing, 
  onSnooze 
}: PreparationReminderModalProps) {
  const { colors } = useTheme();
  const [isLoading, setIsLoading] = useState(false);
  const [action, setAction] = useState<'prepare' | 'snooze' | null>(null);
  
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const shakeAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (visible && order) {
      // Start animations
      startPulseAnimation();
      
      // Vibration pattern based on urgency
      if (order.urgency === 'critical') {
        Vibration.vibrate([0, 300, 100, 300, 100, 300], true);
      } else if (order.urgency === 'high') {
        Vibration.vibrate([0, 200, 100, 200], true);
      } else {
        Vibration.vibrate([0, 150, 100, 150], false);
      }
    }
    
    return () => {
      Vibration.cancel();
    };
  }, [visible, order]);

  const startPulseAnimation = () => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, { toValue: 1.08, duration: 400, useNativeDriver: true }),
        Animated.timing(pulseAnim, { toValue: 1, duration: 400, useNativeDriver: true }),
      ])
    ).start();
    
    // Shake animation for critical
    if (order?.urgency === 'critical') {
      Animated.loop(
        Animated.sequence([
          Animated.timing(shakeAnim, { toValue: 5, duration: 50, useNativeDriver: true }),
          Animated.timing(shakeAnim, { toValue: -5, duration: 50, useNativeDriver: true }),
          Animated.timing(shakeAnim, { toValue: 5, duration: 50, useNativeDriver: true }),
          Animated.timing(shakeAnim, { toValue: 0, duration: 50, useNativeDriver: true }),
          Animated.timing(shakeAnim, { toValue: 0, duration: 500, useNativeDriver: true }),
        ])
      ).start();
    }
  };

  const handleStartPreparing = async () => {
    if (!order) return;
    setIsLoading(true);
    setAction('prepare');
    try {
      await orderAPI.startPreparing(order.order_id);
      Vibration.cancel();
      onStartPreparing();
    } catch (error) {
      console.error('Start preparing error:', error);
    } finally {
      setIsLoading(false);
      setAction(null);
    }
  };

  const handleSnooze = async () => {
    if (!order) return;
    setIsLoading(true);
    setAction('snooze');
    try {
      await orderAPI.snoozePreparation(order.order_id);
      Vibration.cancel();
      onSnooze();
    } catch (error) {
      console.error('Snooze error:', error);
    } finally {
      setIsLoading(false);
      setAction(null);
    }
  };

  if (!visible || !order) return null;

  const getUrgencyConfig = () => {
    switch (order.urgency) {
      case 'critical':
        return {
          color: '#DC2626', // Red
          bgColor: '#FEE2E2',
          icon: 'alert-circle',
          title: 'CRITICAL - ORDER WAITING!',
          subtitle: 'Customer has been waiting too long'
        };
      case 'high':
        return {
          color: '#EA580C', // Orange
          bgColor: '#FFEDD5',
          icon: 'warning',
          title: 'ORDER NEEDS ATTENTION',
          subtitle: 'Please start preparing soon'
        };
      default:
        return {
          color: '#CA8A04', // Yellow
          bgColor: '#FEF9C3',
          icon: 'time',
          title: 'ORDER WAITING',
          subtitle: 'Time to start preparing'
        };
    }
  };

  const config = getUrgencyConfig();

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={onClose}
    >
      <View style={styles.overlay}>
        <Animated.View 
          style={[
            styles.modalContainer, 
            { 
              backgroundColor: colors.card,
              transform: [
                { scale: pulseAnim },
                { translateX: shakeAnim }
              ]
            }
          ]}
        >
          {/* Urgency Header */}
          <View style={[styles.header, { backgroundColor: config.bgColor }]}>
            <Animated.View style={[styles.iconContainer, { transform: [{ scale: pulseAnim }] }]}>
              <View style={[styles.iconBg, { backgroundColor: config.color }]}>
                <Ionicons name={config.icon as any} size={32} color="#FFFFFF" />
              </View>
            </Animated.View>
            <Text style={[styles.headerTitle, { color: config.color }]}>
              {config.title}
            </Text>
            <Text style={[styles.headerSubtitle, { color: config.color + 'CC' }]}>
              {config.subtitle}
            </Text>
          </View>

          {/* Order Info */}
          <View style={styles.orderInfo}>
            <View style={styles.orderRow}>
              <Text style={[styles.orderLabel, { color: colors.text.secondary }]}>Order ID</Text>
              <Text style={[styles.orderValue, { color: colors.text.primary }]}>
                #{order.order_id.slice(-8).toUpperCase()}
              </Text>
            </View>
            
            <View style={styles.orderRow}>
              <Text style={[styles.orderLabel, { color: colors.text.secondary }]}>Customer</Text>
              <Text style={[styles.orderValue, { color: colors.text.primary }]}>
                {order.customer_name}
              </Text>
            </View>
            
            <View style={styles.orderRow}>
              <Text style={[styles.orderLabel, { color: colors.text.secondary }]}>Items</Text>
              <Text style={[styles.orderValue, { color: colors.text.primary }]} numberOfLines={2}>
                {order.items_summary}
              </Text>
            </View>
            
            <View style={styles.orderRow}>
              <Text style={[styles.orderLabel, { color: colors.text.secondary }]}>Total</Text>
              <Text style={[styles.orderValue, { color: colors.text.primary, fontWeight: '700' }]}>
                ₹{order.total.toFixed(2)}
              </Text>
            </View>

            {/* Waiting Time Badge */}
            <View style={[styles.waitingBadge, { backgroundColor: config.bgColor }]}>
              <Ionicons name="time-outline" size={18} color={config.color} />
              <Text style={[styles.waitingText, { color: config.color }]}>
                Waiting for {Math.round(order.waiting_minutes)} minutes
              </Text>
            </View>

            {/* Snooze Warning */}
            {order.snooze_count >= 2 && (
              <View style={[styles.snoozeWarning, { backgroundColor: '#FEE2E2' }]}>
                <Ionicons name="alert" size={16} color="#DC2626" />
                <Text style={[styles.snoozeWarningText, { color: '#DC2626' }]}>
                  Snoozed {order.snooze_count} times - Management will be notified
                </Text>
              </View>
            )}
          </View>

          {/* Action Buttons */}
          <View style={styles.actions}>
            <TouchableOpacity
              style={[styles.primaryBtn, { backgroundColor: '#22C55E' }]}
              onPress={handleStartPreparing}
              disabled={isLoading}
            >
              {isLoading && action === 'prepare' ? (
                <ActivityIndicator color="#FFFFFF" size="small" />
              ) : (
                <>
                  <Ionicons name="restaurant" size={22} color="#FFFFFF" />
                  <Text style={styles.primaryBtnText}>Start Preparing Now</Text>
                </>
              )}
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.secondaryBtn, { borderColor: colors.separator }]}
              onPress={handleSnooze}
              disabled={isLoading}
            >
              {isLoading && action === 'snooze' ? (
                <ActivityIndicator color={colors.text.secondary} size="small" />
              ) : (
                <>
                  <Ionicons name="time" size={20} color={colors.text.secondary} />
                  <Text style={[styles.secondaryBtnText, { color: colors.text.secondary }]}>
                    In 2 Minutes
                  </Text>
                </>
              )}
            </TouchableOpacity>
          </View>
        </Animated.View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.7)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  modalContainer: {
    width: '100%',
    maxWidth: 400,
    borderRadius: 24,
    overflow: 'hidden',
  },
  header: {
    paddingVertical: 24,
    paddingHorizontal: 20,
    alignItems: 'center',
  },
  iconContainer: {
    marginBottom: 12,
  },
  iconBg: {
    width: 64,
    height: 64,
    borderRadius: 32,
    justifyContent: 'center',
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '800',
    textAlign: 'center',
    letterSpacing: 0.5,
  },
  headerSubtitle: {
    fontSize: 14,
    marginTop: 4,
    textAlign: 'center',
  },
  orderInfo: {
    padding: 20,
  },
  orderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  orderLabel: {
    fontSize: 13,
    fontWeight: '500',
    flex: 0.35,
  },
  orderValue: {
    fontSize: 14,
    fontWeight: '500',
    flex: 0.65,
    textAlign: 'right',
  },
  waitingBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 12,
    marginTop: 8,
    gap: 8,
  },
  waitingText: {
    fontSize: 14,
    fontWeight: '600',
  },
  snoozeWarning: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 8,
    marginTop: 12,
    gap: 6,
  },
  snoozeWarningText: {
    fontSize: 12,
    fontWeight: '500',
    flex: 1,
  },
  actions: {
    padding: 20,
    paddingTop: 8,
    gap: 12,
  },
  primaryBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 16,
    borderRadius: 14,
    gap: 10,
  },
  primaryBtnText: {
    color: '#FFFFFF',
    fontSize: 17,
    fontWeight: '700',
  },
  secondaryBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 14,
    borderRadius: 12,
    borderWidth: 1.5,
    gap: 8,
  },
  secondaryBtnText: {
    fontSize: 15,
    fontWeight: '600',
  },
});
