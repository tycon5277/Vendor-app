import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Animated,
  TouchableOpacity,
  Dimensions,
  Modal,
  Vibration,
  AppState,
  AppStateStatus,
  Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as Haptics from 'expo-haptics';
import { Audio } from 'expo-av';
import { orderAPI } from '../utils/api';
import { useAuthStore } from '../store/authStore';
import { Order } from '../types';

const { width, height } = Dimensions.get('window');

interface NewOrderNotificationContextType {
  hasNewOrder: boolean;
  currentNewOrder: Order | null;
  dismissNotification: () => void;
  refreshOrders: () => void;
}

const NewOrderNotificationContext = createContext<NewOrderNotificationContextType | undefined>(undefined);

export const useNewOrderNotification = () => {
  const context = useContext(NewOrderNotificationContext);
  if (!context) {
    throw new Error('useNewOrderNotification must be used within NewOrderNotificationProvider');
  }
  return context;
};

// Polling interval in milliseconds
const POLL_INTERVAL = 10000; // 10 seconds

export const NewOrderNotificationProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const router = useRouter();
  const { isAuthenticated, isVendor, user } = useAuthStore();
  
  // Check if vendor is online (available status)
  const isVendorOnline = user?.partner_status === 'available';
  
  const [visible, setVisible] = useState(false);
  const [currentNewOrder, setCurrentNewOrder] = useState<Order | null>(null);
  const [knownOrderIds, setKnownOrderIds] = useState<Set<string>>(new Set());
  const [isInitialized, setIsInitialized] = useState(false);
  
  // Animation refs
  const scaleAnim = useRef(new Animated.Value(0)).current;
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const slideAnim = useRef(new Animated.Value(100)).current;
  const overlayAnim = useRef(new Animated.Value(0)).current;
  const iconRotation = useRef(new Animated.Value(0)).current;
  
  // Sound ref
  const soundRef = useRef<Audio.Sound | null>(null);
  
  // App state ref
  const appState = useRef(AppState.currentState);
  
  // Vibration pattern: [wait, vibrate, wait, vibrate...]
  const VIBRATION_PATTERN = [0, 500, 200, 500, 200, 800];

  // Play notification sound
  const playNotificationSound = useCallback(async () => {
    try {
      // Configure audio mode for alerts
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: false,
        playsInSilentModeIOS: true,
        staysActiveInBackground: false,
        shouldDuckAndroid: true,
      });
      
      // Create and play a system-like notification sound using a tone
      // Since we don't have an external sound file, we'll use web audio on web
      // and rely on haptics/vibration on native
      if (Platform.OS === 'web') {
        // Use Web Audio API for web platform
        try {
          const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
          
          // Create a notification-like sound pattern
          const playTone = (freq: number, startTime: number, duration: number) => {
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();
            
            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);
            
            oscillator.frequency.value = freq;
            oscillator.type = 'sine';
            
            gainNode.gain.setValueAtTime(0.3, startTime);
            gainNode.gain.exponentialRampToValueAtTime(0.01, startTime + duration);
            
            oscillator.start(startTime);
            oscillator.stop(startTime + duration);
          };
          
          // Play a pleasant notification chime (3 ascending tones)
          const now = audioContext.currentTime;
          playTone(523.25, now, 0.15);        // C5
          playTone(659.25, now + 0.15, 0.15); // E5
          playTone(783.99, now + 0.3, 0.3);   // G5
          
          // Second pattern after a pause
          setTimeout(() => {
            const now2 = audioContext.currentTime;
            playTone(523.25, now2, 0.15);
            playTone(659.25, now2 + 0.15, 0.15);
            playTone(783.99, now2 + 0.3, 0.3);
          }, 800);
          
        } catch (webAudioError) {
          console.log('Web Audio not available:', webAudioError);
        }
      }
    } catch (error) {
      console.log('Sound playback setup failed:', error);
    }
  }, []);

  // Cleanup sound
  const cleanupSound = useCallback(async () => {
    if (soundRef.current) {
      try {
        await soundRef.current.unloadAsync();
      } catch (error) {
        // Ignore cleanup errors
      }
      soundRef.current = null;
    }
  }, []);

  // Trigger haptic feedback for notification
  const triggerHapticFeedback = useCallback(async () => {
    try {
      // Heavy impact for new order notification
      await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
      // Follow up with more haptics for emphasis
      setTimeout(async () => {
        await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy);
      }, 300);
      setTimeout(async () => {
        await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy);
      }, 600);
    } catch (error) {
      // Fallback to vibration on platforms that don't support haptics
      console.log('Haptics not available, using vibration');
    }
  }, []);

  // Trigger notification effects
  const triggerNotificationEffects = useCallback(() => {
    // Vibration
    Vibration.vibrate(VIBRATION_PATTERN);
    
    // Haptic feedback
    triggerHapticFeedback();
    
    // Start pulse animation
    const pulseLoop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, {
          toValue: 1.05,
          duration: 500,
          useNativeDriver: true,
        }),
        Animated.timing(pulseAnim, {
          toValue: 1,
          duration: 500,
          useNativeDriver: true,
        }),
      ])
    );
    pulseLoop.start();
    
    // Icon shake animation
    const iconShake = Animated.loop(
      Animated.sequence([
        Animated.timing(iconRotation, {
          toValue: 1,
          duration: 100,
          useNativeDriver: true,
        }),
        Animated.timing(iconRotation, {
          toValue: -1,
          duration: 100,
          useNativeDriver: true,
        }),
        Animated.timing(iconRotation, {
          toValue: 0,
          duration: 100,
          useNativeDriver: true,
        }),
      ])
    );
    iconShake.start();
    
    return () => {
      pulseLoop.stop();
      iconShake.stop();
    };
  }, [triggerHapticFeedback]);

  // Show notification modal
  const showNotification = useCallback((order: Order) => {
    setCurrentNewOrder(order);
    setVisible(true);
    
    // Animate in
    Animated.parallel([
      Animated.spring(scaleAnim, {
        toValue: 1,
        friction: 8,
        tension: 40,
        useNativeDriver: true,
      }),
      Animated.timing(overlayAnim, {
        toValue: 1,
        duration: 300,
        useNativeDriver: true,
      }),
      Animated.spring(slideAnim, {
        toValue: 0,
        friction: 8,
        tension: 40,
        useNativeDriver: true,
      }),
    ]).start();
    
    // Trigger effects
    triggerNotificationEffects();
  }, [triggerNotificationEffects]);

  // Hide notification modal
  const hideNotification = useCallback(() => {
    Vibration.cancel();
    
    Animated.parallel([
      Animated.timing(scaleAnim, {
        toValue: 0,
        duration: 200,
        useNativeDriver: true,
      }),
      Animated.timing(overlayAnim, {
        toValue: 0,
        duration: 200,
        useNativeDriver: true,
      }),
      Animated.timing(slideAnim, {
        toValue: 100,
        duration: 200,
        useNativeDriver: true,
      }),
    ]).start(() => {
      setVisible(false);
      setCurrentNewOrder(null);
      pulseAnim.setValue(1);
      iconRotation.setValue(0);
    });
  }, []);

  // Check for new orders
  const checkForNewOrders = useCallback(async () => {
    if (!isAuthenticated || !isVendor) return;
    
    try {
      const response = await orderAPI.getPending();
      const pendingOrders: Order[] = response.data;
      
      if (!isInitialized) {
        // First load - just record existing orders, don't notify
        setKnownOrderIds(new Set(pendingOrders.map(o => o.order_id)));
        setIsInitialized(true);
        return;
      }
      
      // Check for new orders
      const newOrders = pendingOrders.filter(
        order => !knownOrderIds.has(order.order_id)
      );
      
      if (newOrders.length > 0 && !visible) {
        // Show notification for the first new order
        showNotification(newOrders[0]);
        
        // Update known orders
        setKnownOrderIds(prev => {
          const updated = new Set(prev);
          newOrders.forEach(order => updated.add(order.order_id));
          return updated;
        });
      }
    } catch (error) {
      console.log('Error checking for new orders:', error);
    }
  }, [isAuthenticated, isVendor, isInitialized, knownOrderIds, visible, showNotification]);

  // Handle app state changes
  useEffect(() => {
    const subscription = AppState.addEventListener('change', (nextAppState: AppStateStatus) => {
      if (appState.current.match(/inactive|background/) && nextAppState === 'active') {
        // App came to foreground - check for orders
        checkForNewOrders();
      }
      appState.current = nextAppState;
    });

    return () => {
      subscription.remove();
    };
  }, [checkForNewOrders]);

  // Polling for new orders
  useEffect(() => {
    if (!isAuthenticated || !isVendor) return;
    
    // Initial check
    checkForNewOrders();
    
    // Set up polling
    const intervalId = setInterval(checkForNewOrders, POLL_INTERVAL);
    
    return () => {
      clearInterval(intervalId);
    };
  }, [isAuthenticated, isVendor, checkForNewOrders]);

  // Handle view order
  const handleViewOrder = useCallback(() => {
    if (currentNewOrder) {
      hideNotification();
      setTimeout(() => {
        router.push(`/(main)/orders/${currentNewOrder.order_id}`);
      }, 300);
    }
  }, [currentNewOrder, hideNotification, router]);

  // Handle accept order
  const handleAcceptOrder = useCallback(async () => {
    if (!currentNewOrder) return;
    
    try {
      await orderAPI.accept(currentNewOrder.order_id);
      hideNotification();
      setTimeout(() => {
        router.push(`/(main)/orders/${currentNewOrder.order_id}`);
      }, 300);
    } catch (error) {
      console.error('Error accepting order:', error);
      // Still navigate to order details
      hideNotification();
      router.push(`/(main)/orders/${currentNewOrder.order_id}`);
    }
  }, [currentNewOrder, hideNotification, router]);

  // Dismiss notification
  const dismissNotification = useCallback(() => {
    hideNotification();
  }, [hideNotification]);

  // Refresh orders (called externally after order actions)
  const refreshOrders = useCallback(async () => {
    if (!isAuthenticated || !isVendor) return;
    
    try {
      const response = await orderAPI.getPending();
      setKnownOrderIds(new Set(response.data.map((o: Order) => o.order_id)));
    } catch (error) {
      console.log('Error refreshing orders:', error);
    }
  }, [isAuthenticated, isVendor]);

  // Calculate auto-accept time
  const getAutoAcceptDisplay = () => {
    if (!currentNewOrder?.auto_accept_seconds) return null;
    const minutes = Math.floor(currentNewOrder.auto_accept_seconds / 60);
    const seconds = currentNewOrder.auto_accept_seconds % 60;
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  const spin = iconRotation.interpolate({
    inputRange: [-1, 1],
    outputRange: ['-15deg', '15deg'],
  });

  return (
    <NewOrderNotificationContext.Provider 
      value={{ 
        hasNewOrder: visible, 
        currentNewOrder, 
        dismissNotification,
        refreshOrders,
      }}
    >
      {children}
      
      <Modal
        visible={visible}
        transparent
        animationType="none"
        statusBarTranslucent
        onRequestClose={dismissNotification}
      >
        <Animated.View style={[styles.overlay, { opacity: overlayAnim }]}>
          <Animated.View 
            style={[
              styles.container,
              {
                transform: [
                  { scale: scaleAnim },
                  { translateY: slideAnim },
                ],
              }
            ]}
          >
            {/* Pulsing background */}
            <Animated.View 
              style={[
                styles.pulseBackground,
                { transform: [{ scale: pulseAnim }] }
              ]}
            />
            
            {/* Content */}
            <View style={styles.content}>
              {/* Bell icon with shake */}
              <Animated.View 
                style={[
                  styles.bellContainer,
                  { transform: [{ rotate: spin }] }
                ]}
              >
                <Ionicons name="notifications" size={48} color="#FFFFFF" />
              </Animated.View>
              
              {/* Title */}
              <Text style={styles.title}>New Order!</Text>
              <Text style={styles.subtitle}>You have a new customer order</Text>
              
              {/* Order details card */}
              <View style={styles.orderCard}>
                <View style={styles.orderRow}>
                  <Text style={styles.orderLabel}>Order ID</Text>
                  <Text style={styles.orderId}>
                    #{currentNewOrder?.order_id.slice(-8).toUpperCase()}
                  </Text>
                </View>
                
                <View style={styles.divider} />
                
                <View style={styles.orderRow}>
                  <Text style={styles.orderLabel}>Customer</Text>
                  <Text style={styles.orderValue}>
                    {currentNewOrder?.customer_name || 'Customer'}
                  </Text>
                </View>
                
                <View style={styles.divider} />
                
                <View style={styles.orderRow}>
                  <Text style={styles.orderLabel}>Items</Text>
                  <Text style={styles.orderValue}>
                    {currentNewOrder?.items?.length || 0} item(s)
                  </Text>
                </View>
                
                <View style={styles.divider} />
                
                <View style={styles.orderRow}>
                  <Text style={styles.orderLabel}>Total</Text>
                  <Text style={styles.orderAmount}>
                    ₹{currentNewOrder?.total_amount?.toLocaleString() || 0}
                  </Text>
                </View>
              </View>
              
              {/* Auto-accept timer */}
              {getAutoAcceptDisplay() && (
                <View style={styles.timerContainer}>
                  <Ionicons name="time-outline" size={16} color="#F59E0B" />
                  <Text style={styles.timerText}>
                    Auto-accepts in {getAutoAcceptDisplay()}
                  </Text>
                </View>
              )}
              
              {/* Action buttons */}
              <View style={styles.buttonContainer}>
                <TouchableOpacity
                  style={styles.viewButton}
                  onPress={handleViewOrder}
                  activeOpacity={0.8}
                  testID="view-order-btn"
                >
                  <Ionicons name="eye-outline" size={20} color="#6366F1" />
                  <Text style={styles.viewButtonText}>View Details</Text>
                </TouchableOpacity>
                
                <TouchableOpacity
                  style={styles.acceptButton}
                  onPress={handleAcceptOrder}
                  activeOpacity={0.8}
                  testID="accept-order-btn"
                >
                  <Ionicons name="checkmark-circle" size={20} color="#FFFFFF" />
                  <Text style={styles.acceptButtonText}>Accept Order</Text>
                </TouchableOpacity>
              </View>
              
              {/* Dismiss */}
              <TouchableOpacity
                style={styles.dismissButton}
                onPress={dismissNotification}
                testID="dismiss-notification-btn"
              >
                <Text style={styles.dismissText}>Dismiss</Text>
              </TouchableOpacity>
            </View>
          </Animated.View>
        </Animated.View>
      </Modal>
    </NewOrderNotificationContext.Provider>
  );
};

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.85)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  container: {
    width: width - 48,
    maxWidth: 380,
    backgroundColor: '#1F2937',
    borderRadius: 32,
    overflow: 'hidden',
    position: 'relative',
  },
  pulseBackground: {
    position: 'absolute',
    top: -100,
    left: -100,
    right: -100,
    bottom: -100,
    backgroundColor: 'rgba(99, 102, 241, 0.15)',
    borderRadius: 500,
  },
  content: {
    padding: 28,
    alignItems: 'center',
  },
  bellContainer: {
    width: 96,
    height: 96,
    backgroundColor: '#6366F1',
    borderRadius: 48,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 20,
    shadowColor: '#6366F1',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.5,
    shadowRadius: 16,
    elevation: 10,
  },
  title: {
    fontSize: 32,
    fontWeight: '800',
    color: '#FFFFFF',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 16,
    color: '#9CA3AF',
    marginBottom: 24,
  },
  orderCard: {
    width: '100%',
    backgroundColor: '#374151',
    borderRadius: 20,
    padding: 20,
    marginBottom: 16,
  },
  orderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
  },
  orderLabel: {
    fontSize: 14,
    color: '#9CA3AF',
    fontWeight: '500',
  },
  orderId: {
    fontSize: 16,
    color: '#6366F1',
    fontWeight: '700',
    fontFamily: 'monospace',
  },
  orderValue: {
    fontSize: 15,
    color: '#FFFFFF',
    fontWeight: '600',
  },
  orderAmount: {
    fontSize: 20,
    color: '#22C55E',
    fontWeight: '800',
  },
  divider: {
    height: 1,
    backgroundColor: '#4B5563',
    marginVertical: 4,
  },
  timerContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(245, 158, 11, 0.15)',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 12,
    marginBottom: 24,
    gap: 8,
  },
  timerText: {
    fontSize: 14,
    color: '#F59E0B',
    fontWeight: '600',
  },
  buttonContainer: {
    width: '100%',
    flexDirection: 'row',
    gap: 12,
    marginBottom: 16,
  },
  viewButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FFFFFF',
    paddingVertical: 16,
    borderRadius: 16,
    gap: 8,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
    elevation: 4,
  },
  viewButtonText: {
    fontSize: 16,
    fontWeight: '700',
    color: '#6366F1',
  },
  acceptButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#22C55E',
    paddingVertical: 16,
    borderRadius: 16,
    gap: 8,
    shadowColor: '#22C55E',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.4,
    shadowRadius: 8,
    elevation: 4,
  },
  acceptButtonText: {
    fontSize: 16,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  dismissButton: {
    paddingVertical: 12,
    paddingHorizontal: 24,
  },
  dismissText: {
    fontSize: 14,
    color: '#6B7280',
    fontWeight: '500',
  },
});

export default NewOrderNotificationProvider;
