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
import { Audio } from 'expo-av';
// Note: expo-notifications removed - not supported in Expo Go SDK 53+
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
  
  // Sound ref
  const soundRef = useRef<Audio.Sound | null>(null);
  const soundIntervalRef = useRef<NodeJS.Timeout | null>(null);
  
  // App state ref
  const appState = useRef(AppState.currentState);

  // Play loud notification sound
  const playLoudSound = useCallback(async () => {
    try {
      // Configure audio for maximum volume
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: false,
        playsInSilentModeIOS: true,
        staysActiveInBackground: true,
        shouldDuckAndroid: false,
      });

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
              {/* Claymorphism Card */}
              <View style={styles.clayCard}>
                {/* Animated glow ring */}
                <Animated.View 
                  style={[
                    styles.glowRing,
                    { opacity: glowOpacity }
                  ]}
                />
                
                {/* Bell icon container with animation */}
                <Animated.View 
                  style={[
                    styles.bellContainer,
                    { transform: [{ rotate: bellRotate }, { scale: pulseAnim }] }
                  ]}
                >
                  <View style={styles.bellInner}>
                    <Ionicons name="notifications" size={32} color="#FF6B35" />
                  </View>
                </Animated.View>
                
                {/* Title Section */}
                <View style={styles.titleSection}>
                  <Text style={styles.newBadge}>NEW</Text>
                  <Text style={styles.title}>Order Received!</Text>
                  <Text style={styles.subtitle}>A customer is waiting for your response</Text>
                </View>
                
              {/* Order Details Card - Claymorphism Inner Card */}
              <View style={styles.orderDetailsCard}>
                {/* Order ID */}
                <View style={styles.orderIdRow}>
                  <View style={styles.orderIdBadge}>
                    <Text style={styles.orderIdText}>
                      #{currentNewOrder?.order_id.slice(-8).toUpperCase()}
                    </Text>
                  </View>
                </View>
                
                {/* Customer Info */}
                <View style={styles.infoRow}>
                  <View style={styles.infoIcon}>
                    <Ionicons name="person" size={16} color="#6366F1" />
                  </View>
                  <View style={styles.infoContent}>
                    <Text style={styles.infoLabel}>Customer</Text>
                    <Text style={styles.infoValue}>{currentNewOrder?.customer_name || 'Customer'}</Text>
                  </View>
                </View>
                
                {/* Items */}
                <View style={styles.infoRow}>
                  <View style={styles.infoIcon}>
                    <Ionicons name="basket" size={16} color="#6366F1" />
                  </View>
                  <View style={styles.infoContent}>
                    <Text style={styles.infoLabel}>Items</Text>
                    <Text style={styles.infoValue}>{currentNewOrder?.items?.length || 0} item(s)</Text>
                  </View>
                </View>
                
                {/* Total Amount - Highlighted */}
                <View style={styles.totalRow}>
                  <View style={styles.totalLeft}>
                    <Ionicons name="wallet" size={18} color="#22C55E" />
                    <Text style={styles.totalLabel}>Total Amount</Text>
                  </View>
                  <Text style={styles.totalValue}>
                    ₹{currentNewOrder?.total_amount?.toLocaleString() || 0}
                  </Text>
                </View>
              </View>
              
              {/* Auto-accept Timer */}
              {formatCountdown() && (
                <View style={styles.timerContainer}>
                  <View style={styles.timerIcon}>
                    <Ionicons name="timer" size={16} color="#F59E0B" />
                  </View>
                  <Text style={styles.timerText}>
                    Auto-accepts in <Text style={styles.timerCountdown}>{formatCountdown()}</Text>
                  </Text>
                </View>
              )}
              
              {/* Action Buttons */}
              <View style={styles.buttonContainer}>
                <TouchableOpacity
                  style={styles.viewButton}
                  onPress={handleViewOrder}
                  activeOpacity={0.8}
                  testID="view-order-btn"
                >
                  <Ionicons name="eye-outline" size={18} color="#6366F1" />
                  <Text style={styles.viewButtonText}>View Details</Text>
                </TouchableOpacity>
                
                <TouchableOpacity
                  style={styles.acceptButton}
                  onPress={handleAcceptOrder}
                  activeOpacity={0.8}
                  testID="accept-order-btn"
                >
                  <Ionicons name="checkmark-circle" size={18} color="#FFFFFF" />
                  <Text style={styles.acceptButtonText}>Accept</Text>
                </TouchableOpacity>
              </View>
              
              {/* Dismiss Link */}
              <TouchableOpacity
                style={styles.dismissButton}
                onPress={dismissNotification}
                testID="dismiss-notification-btn"
              >
                <Text style={styles.dismissText}>Dismiss for now</Text>
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
    backgroundColor: 'rgba(0, 0, 0, 0.7)',
  },
  scrollContent: {
    flexGrow: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 40,
    paddingHorizontal: 16,
  },
  container: {
    width: '100%',
    maxWidth: 340,
  },
  clayCard: {
    backgroundColor: '#F8FAFC',
    borderRadius: 24,
    padding: 20,
    alignItems: 'center',
    // Claymorphism shadow
    shadowColor: '#64748B',
    shadowOffset: { width: 0, height: 20 },
    shadowOpacity: 0.15,
    shadowRadius: 40,
    elevation: 20,
    // Inner highlight effect
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.8)',
  },
  glowRing: {
    position: 'absolute',
    top: -6,
    left: -6,
    right: -6,
    bottom: -6,
    borderRadius: 30,
    borderWidth: 2,
    borderColor: '#FF6B35',
    backgroundColor: 'transparent',
  },
  bellContainer: {
    marginTop: 4,
    marginBottom: 10,
  },
  bellInner: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: '#FFF7ED',
    justifyContent: 'center',
    alignItems: 'center',
    // Claymorphism inner shadow
    shadowColor: '#FB923C',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.3,
    shadowRadius: 12,
    elevation: 6,
    borderWidth: 2,
    borderColor: '#FFEDD5',
  },
  titleSection: {
    alignItems: 'center',
    marginBottom: 14,
  },
  newBadge: {
    backgroundColor: '#FF6B35',
    color: '#FFFFFF',
    fontSize: 10,
    fontWeight: '800',
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderRadius: 10,
    marginBottom: 8,
    letterSpacing: 1,
    overflow: 'hidden',
  },
  title: {
    fontSize: 22,
    fontWeight: '800',
    color: '#1E293B',
    marginBottom: 4,
    letterSpacing: -0.5,
  },
  subtitle: {
    fontSize: 13,
    color: '#64748B',
    textAlign: 'center',
  },
  orderDetailsCard: {
    width: '100%',
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 14,
    marginBottom: 12,
    // Claymorphism nested card
    shadowColor: '#94A3B8',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 3,
    borderWidth: 1,
    borderColor: '#F1F5F9',
  },
  orderIdRow: {
    alignItems: 'center',
    marginBottom: 10,
  },
  orderIdBadge: {
    backgroundColor: '#EEF2FF',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#C7D2FE',
  },
  orderIdText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#4F46E5',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    letterSpacing: 1,
  },
  infoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#F1F5F9',
  },
  infoIcon: {
    width: 32,
    height: 32,
    borderRadius: 8,
    backgroundColor: '#EEF2FF',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 10,
  },
  infoContent: {
    flex: 1,
  },
  infoLabel: {
    fontSize: 11,
    color: '#94A3B8',
    fontWeight: '500',
    marginBottom: 1,
  },
  infoValue: {
    fontSize: 14,
    color: '#1E293B',
    fontWeight: '600',
  },
  totalRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingTop: 10,
    marginTop: 4,
  },
  totalLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  totalLabel: {
    fontSize: 13,
    color: '#64748B',
    fontWeight: '600',
  },
  totalValue: {
    fontSize: 22,
    fontWeight: '800',
    color: '#22C55E',
  },
  timerContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFBEB',
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 12,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: '#FEF3C7',
    gap: 8,
  },
  timerIcon: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: '#FEF3C7',
    justifyContent: 'center',
    alignItems: 'center',
  },
  timerText: {
    fontSize: 13,
    color: '#92400E',
    fontWeight: '500',
  },
  timerCountdown: {
    fontWeight: '800',
    color: '#D97706',
    fontSize: 14,
  },
  buttonContainer: {
    width: '100%',
    flexDirection: 'row',
    gap: 10,
  },
  viewButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FFFFFF',
    paddingVertical: 12,
    borderRadius: 12,
    gap: 6,
    borderWidth: 2,
    borderColor: '#E0E7FF',
    // Claymorphism button
    shadowColor: '#6366F1',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.15,
    shadowRadius: 6,
    elevation: 3,
  },
  viewButtonText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#6366F1',
  },
  acceptButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#22C55E',
    paddingVertical: 12,
    borderRadius: 12,
    gap: 6,
    // Claymorphism button
    shadowColor: '#22C55E',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.35,
    shadowRadius: 8,
    elevation: 4,
  },
  acceptButtonText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  dismissButton: {
    marginTop: 12,
    paddingVertical: 8,
    paddingHorizontal: 16,
  },
  dismissText: {
    fontSize: 13,
    color: '#94A3B8',
    fontWeight: '500',
  },
});

export default NewOrderNotificationProvider;
