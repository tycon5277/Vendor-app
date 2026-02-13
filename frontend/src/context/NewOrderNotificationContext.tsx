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
  ScrollView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import * as Haptics from 'expo-haptics';
// Note: expo-notifications removed - not supported in Expo Go SDK 53+
// Note: expo-av removed - deprecated in SDK 53+, using Web Audio API instead
// Push notifications require a development build
import { orderAPI } from '../utils/api';
import { useAuthStore } from '../store/authStore';
import { Order } from '../types';

const { width, height } = Dimensions.get('window');

interface NewOrderNotificationContextType {
  hasNewOrder: boolean;
  currentNewOrder: Order | null;
  dismissNotification: () => void;
  refreshOrders: () => void;
  isVendorOnline: boolean;
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

// Loud vibration pattern for new orders
const LOUD_VIBRATION_PATTERN = Platform.OS === 'android' 
  ? [0, 800, 200, 800, 200, 800, 200, 1000] // Longer, stronger pattern for Android
  : [0, 500, 200, 500, 200, 500]; // iOS pattern

export const NewOrderNotificationProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const router = useRouter();
  const { isAuthenticated, isVendor, user } = useAuthStore();
  
  // Check if vendor is online (available status)
  const isVendorOnline = user?.partner_status === 'available';
  
  const [visible, setVisible] = useState(false);
  const [currentNewOrder, setCurrentNewOrder] = useState<Order | null>(null);
  const [knownOrderIds, setKnownOrderIds] = useState<Set<string>>(new Set());
  const [isInitialized, setIsInitialized] = useState(false);
  const [autoAcceptCountdown, setAutoAcceptCountdown] = useState<number | null>(null);
  
  // Animation refs
  const scaleAnim = useRef(new Animated.Value(0)).current;
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const glowAnim = useRef(new Animated.Value(0)).current;
  const bellShakeAnim = useRef(new Animated.Value(0)).current;
  const overlayAnim = useRef(new Animated.Value(0)).current;
  const cardSlideAnim = useRef(new Animated.Value(50)).current;
  
  // Sound interval ref for alert loop
  const soundIntervalRef = useRef<NodeJS.Timeout | null>(null);
  
  // App state ref
  const appState = useRef(AppState.currentState);

  // Play loud notification sound
  const playLoudSound = useCallback(async () => {
    try {
      if (Platform.OS === 'web') {
        // Web Audio API - Louder, more urgent sound
        try {
          const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
          
          const playUrgentTone = (freq: number, startTime: number, duration: number, volume: number) => {
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();
            
            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);
            
            oscillator.frequency.value = freq;
            oscillator.type = 'square'; // More attention-grabbing than sine
            
            gainNode.gain.setValueAtTime(volume, startTime);
            gainNode.gain.exponentialRampToValueAtTime(0.01, startTime + duration);
            
            oscillator.start(startTime);
            oscillator.stop(startTime + duration);
          };
          
          // Urgent notification pattern - loud and attention-grabbing
          const now = audioContext.currentTime;
          // First burst - ascending
          playUrgentTone(880, now, 0.15, 0.5);        // A5
          playUrgentTone(1047, now + 0.12, 0.15, 0.5); // C6
          playUrgentTone(1319, now + 0.24, 0.2, 0.5);  // E6
          
          // Second burst after pause
          playUrgentTone(880, now + 0.6, 0.15, 0.5);
          playUrgentTone(1047, now + 0.72, 0.15, 0.5);
          playUrgentTone(1319, now + 0.84, 0.2, 0.5);
          
          // Third burst - even higher
          playUrgentTone(1047, now + 1.2, 0.15, 0.5);
          playUrgentTone(1319, now + 1.32, 0.15, 0.5);
          playUrgentTone(1568, now + 1.44, 0.3, 0.5);  // G6
          
        } catch (webAudioError) {
          console.log('Web Audio error:', webAudioError);
        }
      }
    } catch (error) {
      console.log('Sound playback error:', error);
    }
  }, []);

  // Start continuous sound and vibration
  const startAlertLoop = useCallback(() => {
    // Initial sound and vibration
    playLoudSound();
    Vibration.vibrate(LOUD_VIBRATION_PATTERN, true); // Repeat pattern
    
    // Haptic feedback for extra attention
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
    
    // Repeat sound every 2 seconds
    soundIntervalRef.current = setInterval(() => {
      playLoudSound();
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy);
    }, 2000);
  }, [playLoudSound]);

  // Stop alert loop
  const stopAlertLoop = useCallback(() => {
    Vibration.cancel();
    if (soundIntervalRef.current) {
      clearInterval(soundIntervalRef.current);
      soundIntervalRef.current = null;
    }
  }, []);

  // Cleanup sound
  const cleanupSound = useCallback(async () => {
    stopAlertLoop();
    if (soundRef.current) {
      try {
        await soundRef.current.unloadAsync();
      } catch (error) {
        // Ignore cleanup errors
      }
      soundRef.current = null;
    }
  }, [stopAlertLoop]);

  // Show notification modal
  const showNotification = useCallback((order: Order) => {
    setCurrentNewOrder(order);
    setVisible(true);
    
    // Calculate auto-accept countdown
    if (order.auto_accept_seconds) {
      setAutoAcceptCountdown(order.auto_accept_seconds);
    }
    
    // Note: Push notifications removed - not supported in Expo Go SDK 53+
    
    // Animate in with spring effect
    Animated.parallel([
      Animated.spring(scaleAnim, {
        toValue: 1,
        friction: 7,
        tension: 50,
        useNativeDriver: true,
      }),
      Animated.timing(overlayAnim, {
        toValue: 1,
        duration: 300,
        useNativeDriver: true,
      }),
      Animated.spring(cardSlideAnim, {
        toValue: 0,
        friction: 8,
        tension: 40,
        useNativeDriver: true,
      }),
    ]).start();
    
    // Start glow animation
    Animated.loop(
      Animated.sequence([
        Animated.timing(glowAnim, {
          toValue: 1,
          duration: 1000,
          useNativeDriver: false,
        }),
        Animated.timing(glowAnim, {
          toValue: 0.3,
          duration: 1000,
          useNativeDriver: false,
        }),
      ])
    ).start();
    
    // Start bell shake animation
    Animated.loop(
      Animated.sequence([
        Animated.timing(bellShakeAnim, {
          toValue: 1,
          duration: 80,
          useNativeDriver: true,
        }),
        Animated.timing(bellShakeAnim, {
          toValue: -1,
          duration: 80,
          useNativeDriver: true,
        }),
        Animated.timing(bellShakeAnim, {
          toValue: 0.5,
          duration: 80,
          useNativeDriver: true,
        }),
        Animated.timing(bellShakeAnim, {
          toValue: -0.5,
          duration: 80,
          useNativeDriver: true,
        }),
        Animated.timing(bellShakeAnim, {
          toValue: 0,
          duration: 80,
          useNativeDriver: true,
        }),
        Animated.delay(500),
      ])
    ).start();
    
    // Start pulse animation
    Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, {
          toValue: 1.08,
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
    
    // Start alert sound and vibration loop
    startAlertLoop();
  }, [startAlertLoop]);

  // Countdown timer for auto-accept
  useEffect(() => {
    if (visible && autoAcceptCountdown !== null && autoAcceptCountdown > 0) {
      const timer = setTimeout(() => {
        setAutoAcceptCountdown(prev => prev !== null ? prev - 1 : null);
      }, 1000);
      return () => clearTimeout(timer);
    }
  }, [visible, autoAcceptCountdown]);

  // Hide notification modal
  const hideNotification = useCallback(() => {
    stopAlertLoop();
    cleanupSound();
    
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
      Animated.timing(cardSlideAnim, {
        toValue: 50,
        duration: 200,
        useNativeDriver: true,
      }),
    ]).start(() => {
      setVisible(false);
      setCurrentNewOrder(null);
      setAutoAcceptCountdown(null);
      pulseAnim.setValue(1);
      glowAnim.setValue(0);
      bellShakeAnim.setValue(0);
    });
  }, [stopAlertLoop, cleanupSound]);

  // Check for new orders
  const checkForNewOrders = useCallback(async () => {
    // Debug logging
    console.log('Checking for new orders:', { 
      isAuthenticated, 
      isVendor, 
      isVendorOnline,
      partnerStatus: user?.partner_status 
    });
    
    if (!isAuthenticated || !isVendor) {
      console.log('Not authenticated or not vendor, skipping...');
      return;
    }
    
    // Allow notifications if vendor is online OR if status is not explicitly offline
    const shouldPoll = isVendorOnline || user?.partner_status !== 'offline';
    if (!shouldPoll) {
      console.log('Vendor is offline, skipping...');
      return;
    }
    
    try {
      const response = await orderAPI.getPending();
      const pendingOrders: Order[] = response.data;
      console.log('Pending orders:', pendingOrders.length, 'Known:', knownOrderIds.size);
      
      if (!isInitialized) {
        console.log('First load - initializing known orders');
        setKnownOrderIds(new Set(pendingOrders.map(o => o.order_id)));
        setIsInitialized(true);
        return;
      }
      
      const newOrders = pendingOrders.filter(
        order => !knownOrderIds.has(order.order_id)
      );
      
      console.log('New orders detected:', newOrders.length);
      
      if (newOrders.length > 0 && !visible) {
        console.log('Showing notification for order:', newOrders[0].order_id);
        showNotification(newOrders[0]);
        
        setKnownOrderIds(prev => {
          const updated = new Set(prev);
          newOrders.forEach(order => updated.add(order.order_id));
          return updated;
        });
      }
    } catch (error) {
      console.log('Error checking for new orders:', error);
    }
  }, [isAuthenticated, isVendor, isVendorOnline, isInitialized, knownOrderIds, visible, showNotification]);

  // Handle app state changes
  useEffect(() => {
    const subscription = AppState.addEventListener('change', (nextAppState: AppStateStatus) => {
      if (appState.current.match(/inactive|background/) && nextAppState === 'active') {
        if (isVendorOnline) {
          checkForNewOrders();
        }
      }
      appState.current = nextAppState;
    });

    return () => {
      subscription.remove();
    };
  }, [checkForNewOrders, isVendorOnline]);

  // Polling for new orders
  useEffect(() => {
    console.log('Polling effect - isAuthenticated:', isAuthenticated, 'isVendor:', isVendor, 'isVendorOnline:', isVendorOnline, 'partnerStatus:', user?.partner_status);
    
    if (!isAuthenticated || !isVendor) {
      console.log('Not authenticated or not vendor - skipping poll setup');
      return;
    }
    
    // Poll if vendor is online OR if status is not explicitly set to offline
    const shouldPoll = isVendorOnline || (user?.partner_status !== 'offline');
    if (!shouldPoll) {
      console.log('Vendor is offline - skipping poll setup');
      return;
    }
    
    console.log('Setting up order polling...');
    checkForNewOrders();
    const intervalId = setInterval(checkForNewOrders, POLL_INTERVAL);
    
    return () => {
      clearInterval(intervalId);
      cleanupSound();
    };
  }, [isAuthenticated, isVendor, isVendorOnline, user?.partner_status, checkForNewOrders, cleanupSound]);

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
      hideNotification();
      router.push(`/(main)/orders/${currentNewOrder.order_id}`);
    }
  }, [currentNewOrder, hideNotification, router]);

  // Dismiss notification
  const dismissNotification = useCallback(() => {
    hideNotification();
  }, [hideNotification]);

  // Refresh orders
  const refreshOrders = useCallback(async () => {
    if (!isAuthenticated || !isVendor || !isVendorOnline) return;
    
    try {
      const response = await orderAPI.getPending();
      setKnownOrderIds(new Set(response.data.map((o: Order) => o.order_id)));
    } catch (error) {
      console.log('Error refreshing orders:', error);
    }
  }, [isAuthenticated, isVendor, isVendorOnline]);

  // Format countdown display
  const formatCountdown = () => {
    if (autoAcceptCountdown === null) return null;
    const minutes = Math.floor(autoAcceptCountdown / 60);
    const seconds = autoAcceptCountdown % 60;
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  const bellRotate = bellShakeAnim.interpolate({
    inputRange: [-1, 1],
    outputRange: ['-20deg', '20deg'],
  });

  const glowOpacity = glowAnim.interpolate({
    inputRange: [0, 1],
    outputRange: [0.3, 1],
  });

  return (
    <NewOrderNotificationContext.Provider 
      value={{ 
        hasNewOrder: visible, 
        currentNewOrder, 
        dismissNotification,
        refreshOrders,
        isVendorOnline,
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
          <ScrollView 
            contentContainerStyle={styles.scrollContent}
            showsVerticalScrollIndicator={false}
            bounces={false}
          >
            <Animated.View 
              style={[
                styles.container,
                {
                  transform: [
                    { scale: scaleAnim },
                    { translateY: cardSlideAnim },
                  ],
                }
              ]}
            >
              {/* Compact Card */}
              <View style={styles.clayCard}>
                {/* Header with bell and title inline */}
                <View style={styles.headerRow}>
                  <Animated.View 
                    style={[
                      styles.bellContainer,
                      { transform: [{ rotate: bellRotate }] }
                    ]}
                  >
                    <Ionicons name="notifications" size={24} color="#FF6B35" />
                  </Animated.View>
                  <View style={styles.headerText}>
                    <Text style={styles.newBadge}>NEW ORDER</Text>
                    <Text style={styles.orderId}>#{currentNewOrder?.order_id.slice(-6).toUpperCase()}</Text>
                  </View>
                </View>
                
                {/* Order Info - Compact */}
                <View style={styles.orderInfo}>
                  <View style={styles.infoItem}>
                    <Text style={styles.infoLabel}>Customer</Text>
                    <Text style={styles.infoValue}>{currentNewOrder?.customer_name || 'Customer'}</Text>
                  </View>
                  <View style={styles.infoItem}>
                    <Text style={styles.infoLabel}>Items</Text>
                    <Text style={styles.infoValue}>{currentNewOrder?.items?.length || 0}</Text>
                  </View>
                  <View style={styles.infoItem}>
                    <Text style={styles.infoLabel}>Total</Text>
                    <Text style={styles.totalValue}>₹{currentNewOrder?.total_amount || 0}</Text>
                  </View>
                </View>
                
                {/* Timer */}
                {formatCountdown() && (
                  <View style={styles.timerRow}>
                    <Ionicons name="timer-outline" size={14} color="#D97706" />
                    <Text style={styles.timerText}>Auto-accepts in {formatCountdown()}</Text>
                  </View>
                )}
                
                {/* Buttons */}
                <View style={styles.buttonRow}>
                  <TouchableOpacity
                    style={styles.viewButton}
                    onPress={handleViewOrder}
                    activeOpacity={0.8}
                  >
                    <Text style={styles.viewButtonText}>View</Text>
                  </TouchableOpacity>
                  
                  <TouchableOpacity
                    style={styles.acceptButton}
                    onPress={handleAcceptOrder}
                    activeOpacity={0.8}
                  >
                    <Text style={styles.acceptButtonText}>Accept</Text>
                  </TouchableOpacity>
                </View>
                
                <TouchableOpacity onPress={dismissNotification} style={styles.dismissBtn}>
                  <Text style={styles.dismissText}>Dismiss</Text>
                </TouchableOpacity>
              </View>
            </Animated.View>
          </ScrollView>
        </Animated.View>
      </Modal>
    </NewOrderNotificationContext.Provider>
  );
};

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.6)',
  },
  scrollContent: {
    flexGrow: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  container: {
    width: '100%',
    maxWidth: 300,
  },
  clayCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.15,
    shadowRadius: 16,
    elevation: 10,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
    gap: 12,
  },
  bellContainer: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#FFF7ED',
    justifyContent: 'center',
    alignItems: 'center',
  },
  headerText: {
    flex: 1,
  },
  newBadge: {
    fontSize: 10,
    fontWeight: '700',
    color: '#FF6B35',
    letterSpacing: 0.5,
  },
  orderId: {
    fontSize: 16,
    fontWeight: '800',
    color: '#1E293B',
  },
  orderInfo: {
    flexDirection: 'row',
    backgroundColor: '#F8FAFC',
    borderRadius: 10,
    padding: 12,
    marginBottom: 10,
  },
  infoItem: {
    flex: 1,
    alignItems: 'center',
  },
  infoLabel: {
    fontSize: 10,
    color: '#94A3B8',
    marginBottom: 2,
  },
  infoValue: {
    fontSize: 13,
    fontWeight: '600',
    color: '#1E293B',
  },
  totalValue: {
    fontSize: 15,
    fontWeight: '800',
    color: '#22C55E',
  },
  timerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    marginBottom: 12,
  },
  timerText: {
    fontSize: 12,
    color: '#D97706',
    fontWeight: '600',
  },
  buttonRow: {
    flexDirection: 'row',
    gap: 10,
  },
  viewButton: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 10,
    borderWidth: 1.5,
    borderColor: '#E2E8F0',
    alignItems: 'center',
  },
  viewButtonText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#64748B',
  },
  acceptButton: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 10,
    backgroundColor: '#22C55E',
    alignItems: 'center',
  },
  acceptButtonText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  dismissBtn: {
    alignItems: 'center',
    paddingTop: 12,
  },
  dismissText: {
    fontSize: 12,
    color: '#94A3B8',
  },
});

export default NewOrderNotificationProvider;
