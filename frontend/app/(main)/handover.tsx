import React, { useState, useRef, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  ActivityIndicator,
  Image,
  ScrollView,
  Animated,
  Vibration,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useTheme } from '../../src/context/ThemeContext';
import { useAlert } from '../../src/context/AlertContext';
import { useToastStore } from '../../src/store/toastStore';
import { handoverAPI } from '../../src/utils/api';

interface OrderSummary {
  items: Array<{
    name: string;
    quantity: number;
    price: number;
    variation_label?: string;
  }>;
  items_count: number;
  total_amount: number;
  customer_name: string;
  order_placed_at: string;
}

interface GenieInfo {
  name: string;
  phone: string | null;
  photo: string | null;
}

interface HandoverResult {
  valid: boolean;
  order_id: string;
  order_summary: OrderSummary;
  genie: GenieInfo;
  vendor_confirmed: boolean;
  genie_confirmed: boolean;
  handover_complete: boolean;
  message: string;
}

export default function HandoverScreen() {
  const router = useRouter();
  const { colors, isDark } = useTheme();
  const { showAlert } = useAlert();
  const { setPendingToast } = useToastStore();
  
  const [otp, setOtp] = useState(['', '', '', '', '', '']);
  const [isVerifying, setIsVerifying] = useState(false);
  const [handoverResult, setHandoverResult] = useState<HandoverResult | null>(null);
  const inputRefs = useRef<(TextInput | null)[]>([]);
  
  const scaleAnim = useRef(new Animated.Value(1)).current;
  const successAnim = useRef(new Animated.Value(0)).current;

  const handleOtpChange = (value: string, index: number) => {
    if (value.length > 1) {
      // Handle paste
      const digits = value.replace(/\D/g, '').slice(0, 6).split('');
      const newOtp = [...otp];
      digits.forEach((digit, i) => {
        if (index + i < 6) {
          newOtp[index + i] = digit;
        }
      });
      setOtp(newOtp);
      
      // Focus last filled input or next empty
      const lastFilledIndex = Math.min(index + digits.length - 1, 5);
      if (lastFilledIndex < 5 && newOtp[lastFilledIndex + 1] === '') {
        inputRefs.current[lastFilledIndex + 1]?.focus();
      }
      return;
    }
    
    const newOtp = [...otp];
    newOtp[index] = value.replace(/\D/g, '');
    setOtp(newOtp);
    
    // Auto-focus next input
    if (value && index < 5) {
      inputRefs.current[index + 1]?.focus();
    }
  };

  const handleKeyPress = (e: any, index: number) => {
    if (e.nativeEvent.key === 'Backspace' && !otp[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
  };

  const handleVerifyOtp = async () => {
    const otpString = otp.join('');
    if (otpString.length !== 6) {
      showAlert({
        type: 'warning',
        title: 'Invalid OTP',
        message: 'Please enter the complete 6-digit OTP from the delivery partner.',
      });
      return;
    }
    
    setIsVerifying(true);
    
    try {
      const response = await handoverAPI.verifyOtp(otpString);
      const data = response.data;
      
      setHandoverResult(data);
      
      // Animate success
      Animated.spring(successAnim, {
        toValue: 1,
        useNativeDriver: true,
        friction: 8,
      }).start();
      
      // Vibrate for feedback
      Vibration.vibrate(100);
      
      if (data.handover_complete) {
        setPendingToast({
          type: 'success',
          title: 'Handover Complete!',
          message: 'Order is now out for delivery.',
        });
      } else {
        showAlert({
          type: 'info',
          title: 'OTP Verified',
          message: 'Waiting for delivery partner to confirm items.',
        });
      }
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || 'Invalid OTP. Please try again.';
      showAlert({
        type: 'error',
        title: 'Verification Failed',
        message: errorMessage,
      });
      
      // Shake animation
      Animated.sequence([
        Animated.timing(scaleAnim, { toValue: 1.02, duration: 50, useNativeDriver: true }),
        Animated.timing(scaleAnim, { toValue: 0.98, duration: 50, useNativeDriver: true }),
        Animated.timing(scaleAnim, { toValue: 1.02, duration: 50, useNativeDriver: true }),
        Animated.timing(scaleAnim, { toValue: 1, duration: 50, useNativeDriver: true }),
      ]).start();
      
      Vibration.vibrate([0, 100, 50, 100]);
    } finally {
      setIsVerifying(false);
    }
  };

  const handleReset = () => {
    setOtp(['', '', '', '', '', '']);
    setHandoverResult(null);
    successAnim.setValue(0);
    inputRefs.current[0]?.focus();
  };

  const isOtpComplete = otp.every(digit => digit !== '');

  // Auto-verify when OTP is complete
  useEffect(() => {
    if (isOtpComplete && !isVerifying && !handoverResult) {
      handleVerifyOtp();
    }
  }, [otp]);

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background.grouped }]} edges={['top']}>
      {/* Header */}
      <View style={[styles.header, { backgroundColor: colors.card }]}>
        <TouchableOpacity style={styles.backBtn} onPress={() => router.back()}>
          <Ionicons name="arrow-back" size={24} color={colors.text.primary} />
        </TouchableOpacity>
        <Text style={[styles.headerTitle, { color: colors.text.primary }]}>Handover Order</Text>
        <View style={styles.headerRight} />
      </View>

      <ScrollView 
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
      >
        {!handoverResult ? (
          // OTP Entry View
          <Animated.View style={[styles.otpContainer, { transform: [{ scale: scaleAnim }] }]}>
            <View style={[styles.iconContainer, { backgroundColor: isDark ? colors.primary + '20' : '#EFF6FF' }]}>
              <Ionicons name="swap-horizontal" size={48} color={colors.primary} />
            </View>
            
            <Text style={[styles.title, { color: colors.text.primary }]}>
              Enter Handover Code
            </Text>
            <Text style={[styles.subtitle, { color: colors.text.secondary }]}>
              Ask the delivery partner for the 6-digit code
            </Text>

            {/* OTP Input */}
            <View style={styles.otpInputContainer}>
              {otp.map((digit, index) => (
                <TextInput
                  key={index}
                  ref={(ref) => (inputRefs.current[index] = ref)}
                  style={[
                    styles.otpInput,
                    { 
                      backgroundColor: colors.card,
                      borderColor: digit ? colors.primary : colors.separator,
                      color: colors.text.primary,
                    }
                  ]}
                  value={digit}
                  onChangeText={(value) => handleOtpChange(value, index)}
                  onKeyPress={(e) => handleKeyPress(e, index)}
                  keyboardType="number-pad"
                  maxLength={6}
                  selectTextOnFocus
                  testID={`otp-input-${index}`}
                />
              ))}
            </View>

            {/* Verify Button */}
            <TouchableOpacity
              style={[
                styles.verifyBtn,
                { backgroundColor: isOtpComplete ? colors.primary : colors.separator },
                isVerifying && styles.verifyingBtn,
              ]}
              onPress={handleVerifyOtp}
              disabled={!isOtpComplete || isVerifying}
              testID="verify-otp-btn"
            >
              {isVerifying ? (
                <ActivityIndicator color="#FFFFFF" size="small" />
              ) : (
                <>
                  <Ionicons name="checkmark-circle" size={22} color="#FFFFFF" />
                  <Text style={styles.verifyBtnText}>Verify Code</Text>
                </>
              )}
            </TouchableOpacity>

            <Text style={[styles.helpText, { color: colors.text.tertiary }]}>
              The delivery partner has a unique code for this pickup
            </Text>
          </Animated.View>
        ) : (
          // Order Summary View
          <Animated.View 
            style={[
              styles.resultContainer,
              { 
                opacity: successAnim,
                transform: [{ 
                  scale: successAnim.interpolate({
                    inputRange: [0, 1],
                    outputRange: [0.9, 1],
                  })
                }]
              }
            ]}
          >
            {/* Status Banner */}
            <View style={[
              styles.statusBanner,
              { 
                backgroundColor: handoverResult.handover_complete 
                  ? (isDark ? 'rgba(48, 209, 88, 0.2)' : '#D1FAE5')
                  : (isDark ? 'rgba(255, 159, 10, 0.2)' : '#FEF3C7')
              }
            ]}>
              <Ionicons 
                name={handoverResult.handover_complete ? "checkmark-circle" : "time"} 
                size={24} 
                color={handoverResult.handover_complete ? colors.success : colors.warning} 
              />
              <View style={styles.statusTextContainer}>
                <Text style={[
                  styles.statusTitle,
                  { color: handoverResult.handover_complete ? colors.success : colors.warning }
                ]}>
                  {handoverResult.handover_complete ? 'Handover Complete!' : 'OTP Verified'}
                </Text>
                <Text style={[styles.statusSubtitle, { color: colors.text.secondary }]}>
                  {handoverResult.handover_complete 
                    ? 'Order is now out for delivery'
                    : 'Waiting for partner to confirm items'}
                </Text>
              </View>
            </View>

            {/* Order Details Card */}
            <View style={[styles.orderCard, { backgroundColor: colors.card }]}>
              <View style={styles.orderHeader}>
                <Text style={[styles.orderLabel, { color: colors.text.secondary }]}>ORDER</Text>
                <Text style={[styles.orderId, { color: colors.primary }]}>
                  #{handoverResult.order_id.slice(-8).toUpperCase()}
                </Text>
              </View>

              {/* Items List */}
              <View style={styles.itemsList}>
                {handoverResult.order_summary.items.map((item, index) => (
                  <View 
                    key={index} 
                    style={[
                      styles.itemRow,
                      index < handoverResult.order_summary.items.length - 1 && {
                        borderBottomWidth: StyleSheet.hairlineWidth,
                        borderBottomColor: colors.separator,
                      }
                    ]}
                  >
                    <View style={styles.itemInfo}>
                      <Text style={[styles.itemName, { color: colors.text.primary }]}>
                        {item.name}
                      </Text>
                      {item.variation_label && (
                        <Text style={[styles.itemVariation, { color: colors.text.tertiary }]}>
                          {item.variation_label}
                        </Text>
                      )}
                    </View>
                    <View style={styles.itemQtyPrice}>
                      <Text style={[styles.itemQty, { color: colors.text.secondary }]}>
                        x{item.quantity}
                      </Text>
                      <Text style={[styles.itemPrice, { color: colors.text.primary }]}>
                        ₹{(item.price * item.quantity).toFixed(0)}
                      </Text>
                    </View>
                  </View>
                ))}
              </View>

              {/* Total */}
              <View style={[styles.totalRow, { borderTopColor: colors.separator }]}>
                <Text style={[styles.totalLabel, { color: colors.text.secondary }]}>Total</Text>
                <Text style={[styles.totalValue, { color: colors.text.primary }]}>
                  ₹{handoverResult.order_summary.total_amount.toFixed(0)}
                </Text>
              </View>
            </View>

            {/* Genie Info */}
            <View style={[styles.genieCard, { backgroundColor: colors.card }]}>
              <View style={[styles.genieAvatar, { backgroundColor: colors.primary + '20' }]}>
                {handoverResult.genie.photo ? (
                  <Image source={{ uri: handoverResult.genie.photo }} style={styles.geniePhoto} />
                ) : (
                  <Ionicons name="bicycle" size={28} color={colors.primary} />
                )}
              </View>
              <View style={styles.genieInfo}>
                <Text style={[styles.genieName, { color: colors.text.primary }]}>
                  {handoverResult.genie.name}
                </Text>
                <Text style={[styles.genieRole, { color: colors.text.secondary }]}>
                  Delivery Partner
                </Text>
              </View>
              <View style={styles.confirmationBadges}>
                <View style={[
                  styles.badge,
                  { backgroundColor: handoverResult.vendor_confirmed ? colors.success + '20' : colors.separator }
                ]}>
                  <Ionicons 
                    name={handoverResult.vendor_confirmed ? "checkmark" : "time-outline"} 
                    size={14} 
                    color={handoverResult.vendor_confirmed ? colors.success : colors.text.tertiary} 
                  />
                  <Text style={[
                    styles.badgeText,
                    { color: handoverResult.vendor_confirmed ? colors.success : colors.text.tertiary }
                  ]}>
                    You
                  </Text>
                </View>
                <View style={[
                  styles.badge,
                  { backgroundColor: handoverResult.genie_confirmed ? colors.success + '20' : colors.separator }
                ]}>
                  <Ionicons 
                    name={handoverResult.genie_confirmed ? "checkmark" : "time-outline"} 
                    size={14} 
                    color={handoverResult.genie_confirmed ? colors.success : colors.text.tertiary} 
                  />
                  <Text style={[
                    styles.badgeText,
                    { color: handoverResult.genie_confirmed ? colors.success : colors.text.tertiary }
                  ]}>
                    Partner
                  </Text>
                </View>
              </View>
            </View>

            {/* Actions */}
            <View style={styles.actions}>
              {handoverResult.handover_complete ? (
                <TouchableOpacity
                  style={[styles.doneBtn, { backgroundColor: colors.primary }]}
                  onPress={() => router.back()}
                  testID="done-btn"
                >
                  <Ionicons name="checkmark-done" size={22} color="#FFFFFF" />
                  <Text style={styles.doneBtnText}>Done</Text>
                </TouchableOpacity>
              ) : (
                <TouchableOpacity
                  style={[styles.resetBtn, { backgroundColor: colors.card, borderColor: colors.separator }]}
                  onPress={handleReset}
                  testID="reset-btn"
                >
                  <Ionicons name="refresh" size={20} color={colors.text.secondary} />
                  <Text style={[styles.resetBtnText, { color: colors.text.secondary }]}>
                    Enter Different Code
                  </Text>
                </TouchableOpacity>
              )}
            </View>
          </Animated.View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  backBtn: {
    width: 40,
    height: 40,
    justifyContent: 'center',
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
  },
  headerRight: {
    width: 40,
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    padding: 20,
    paddingBottom: 40,
  },
  otpContainer: {
    alignItems: 'center',
    paddingTop: 40,
  },
  iconContainer: {
    width: 100,
    height: 100,
    borderRadius: 50,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 24,
  },
  title: {
    fontSize: 24,
    fontWeight: '700',
    marginBottom: 8,
    textAlign: 'center',
  },
  subtitle: {
    fontSize: 15,
    textAlign: 'center',
    marginBottom: 32,
    lineHeight: 22,
  },
  otpInputContainer: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 10,
    marginBottom: 32,
  },
  otpInput: {
    width: 50,
    height: 60,
    borderRadius: 12,
    borderWidth: 2,
    fontSize: 24,
    fontWeight: '700',
    textAlign: 'center',
  },
  verifyBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 16,
    paddingHorizontal: 32,
    borderRadius: 14,
    gap: 10,
    width: '100%',
    maxWidth: 300,
  },
  verifyingBtn: {
    opacity: 0.8,
  },
  verifyBtnText: {
    color: '#FFFFFF',
    fontSize: 17,
    fontWeight: '600',
  },
  helpText: {
    fontSize: 13,
    textAlign: 'center',
    marginTop: 20,
    lineHeight: 18,
  },
  resultContainer: {
    gap: 16,
  },
  statusBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    borderRadius: 14,
    gap: 14,
  },
  statusTextContainer: {
    flex: 1,
  },
  statusTitle: {
    fontSize: 17,
    fontWeight: '600',
    marginBottom: 2,
  },
  statusSubtitle: {
    fontSize: 14,
  },
  orderCard: {
    borderRadius: 14,
    padding: 16,
  },
  orderHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
    paddingBottom: 12,
  },
  orderLabel: {
    fontSize: 12,
    fontWeight: '600',
    letterSpacing: 0.5,
  },
  orderId: {
    fontSize: 16,
    fontWeight: '700',
  },
  itemsList: {
    gap: 0,
  },
  itemRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 12,
  },
  itemInfo: {
    flex: 1,
    marginRight: 16,
  },
  itemName: {
    fontSize: 15,
    fontWeight: '500',
  },
  itemVariation: {
    fontSize: 13,
    marginTop: 2,
  },
  itemQtyPrice: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  itemQty: {
    fontSize: 14,
  },
  itemPrice: {
    fontSize: 15,
    fontWeight: '600',
    minWidth: 60,
    textAlign: 'right',
  },
  totalRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingTop: 16,
    marginTop: 8,
    borderTopWidth: 1,
  },
  totalLabel: {
    fontSize: 15,
    fontWeight: '500',
  },
  totalValue: {
    fontSize: 20,
    fontWeight: '700',
  },
  genieCard: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    borderRadius: 14,
    gap: 14,
  },
  genieAvatar: {
    width: 56,
    height: 56,
    borderRadius: 28,
    justifyContent: 'center',
    alignItems: 'center',
    overflow: 'hidden',
  },
  geniePhoto: {
    width: '100%',
    height: '100%',
  },
  genieInfo: {
    flex: 1,
  },
  genieName: {
    fontSize: 17,
    fontWeight: '600',
  },
  genieRole: {
    fontSize: 14,
    marginTop: 2,
  },
  confirmationBadges: {
    flexDirection: 'column',
    gap: 6,
  },
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    gap: 4,
  },
  badgeText: {
    fontSize: 12,
    fontWeight: '600',
  },
  actions: {
    marginTop: 8,
  },
  doneBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 16,
    borderRadius: 14,
    gap: 10,
  },
  doneBtnText: {
    color: '#FFFFFF',
    fontSize: 17,
    fontWeight: '600',
  },
  resetBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 14,
    borderRadius: 14,
    borderWidth: 1,
    gap: 8,
  },
  resetBtnText: {
    fontSize: 15,
    fontWeight: '500',
  },
});
