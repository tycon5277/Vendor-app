import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Modal,
  TouchableOpacity,
  ScrollView,
  TextInput,
  Animated,
  Vibration,
  Image,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useTheme } from '../context/ThemeContext';
import { stockVerificationAPI } from '../utils/api';

interface VerificationProduct {
  product_id: string;
  name: string;
  category: string;
  current_stock: number;
  initial_stock: number;
  stock_percentage: number;
  image?: string;
  unit: string;
}

interface StockVerificationModalProps {
  visible: boolean;
  onClose: () => void;
  onComplete: () => void;
}

export default function StockVerificationModal({ visible, onClose, onComplete }: StockVerificationModalProps) {
  const { colors, isDark } = useTheme();
  const [products, setProducts] = useState<VerificationProduct[]>([]);
  const [verifiedStocks, setVerifiedStocks] = useState<Record<string, { stock: string; inStock: boolean }>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showPauseWarning, setShowPauseWarning] = useState(false);
  const [minutesSinceOpen, setMinutesSinceOpen] = useState(0);
  
  const pulseAnim = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    if (visible) {
      loadVerificationData();
      startPulseAnimation();
      playAlertSound();
    }
    return () => {
      stopSound();
    };
  }, [visible]);

  const startPulseAnimation = () => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, { toValue: 1.05, duration: 500, useNativeDriver: true }),
        Animated.timing(pulseAnim, { toValue: 1, duration: 500, useNativeDriver: true }),
      ])
    ).start();
  };

  const playAlertSound = async () => {
    // Use vibration pattern as alternative to sound
    try {
      // Vibrate pattern: vibrate, pause, vibrate
      Vibration.vibrate([0, 200, 100, 200], true);
    } catch (error) {
      console.log('Vibration not available');
    }
  };

  const stopSound = () => {
    try {
      Vibration.cancel();
    } catch (error) {
      console.log('Vibration cancel failed');
    }
  };

  const loadVerificationData = async () => {
    setIsLoading(true);
    try {
      const response = await stockVerificationAPI.getStatus();
      const data = response.data;
      setProducts(data.products_needing_verification || []);
      setShowPauseWarning(data.show_pause_warning || false);
      setMinutesSinceOpen(data.minutes_since_open || 0);
      
      // Initialize verified stocks with current values
      const initialStocks: Record<string, { stock: string; inStock: boolean }> = {};
      (data.products_needing_verification || []).forEach((p: VerificationProduct) => {
        initialStocks[p.product_id] = { 
          stock: String(p.current_stock), 
          inStock: p.current_stock > 0 
        };
      });
      setVerifiedStocks(initialStocks);
    } catch (error) {
      console.error('Load verification data error:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleStockChange = (productId: string, value: string) => {
    const numericValue = value.replace(/[^0-9]/g, '');
    setVerifiedStocks(prev => ({
      ...prev,
      [productId]: { 
        ...prev[productId], 
        stock: numericValue,
        inStock: parseInt(numericValue) > 0 
      }
    }));
  };

  const handleToggleInStock = (productId: string) => {
    setVerifiedStocks(prev => ({
      ...prev,
      [productId]: { 
        ...prev[productId], 
        inStock: !prev[productId]?.inStock,
        stock: !prev[productId]?.inStock ? prev[productId]?.stock || '0' : '0'
      }
    }));
  };

  const handleSubmit = async () => {
    setIsSubmitting(true);
    try {
      const items = products.map(p => ({
        product_id: p.product_id,
        verified_stock: parseInt(verifiedStocks[p.product_id]?.stock || '0'),
        in_stock: verifiedStocks[p.product_id]?.inStock ?? false
      }));
      
      await stockVerificationAPI.submit(items, 'morning');
      await stopSound();
      Vibration.vibrate(100);
      onComplete();
    } catch (error) {
      console.error('Submit verification error:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSkip = async () => {
    await stopSound();
    onClose();
  };

  if (!visible) return null;

  return (
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle="fullScreen"
      onRequestClose={handleSkip}
    >
      <View style={[styles.container, { backgroundColor: colors.background.grouped }]}>
        {/* Header */}
        <View style={[styles.header, { backgroundColor: colors.card }]}>
          <View style={styles.headerContent}>
            <Animated.View style={[styles.iconContainer, { transform: [{ scale: pulseAnim }] }]}>
              <View style={[styles.iconBg, { backgroundColor: colors.warning + '20' }]}>
                <Ionicons name="alert-circle" size={32} color={colors.warning} />
              </View>
            </Animated.View>
            <Text style={[styles.headerTitle, { color: colors.text.primary }]}>
              Morning Stock Verification
            </Text>
            <Text style={[styles.headerSubtitle, { color: colors.text.secondary }]}>
              Please verify your inventory before accepting orders
            </Text>
          </View>
        </View>

        {/* Warning Banner */}
        {showPauseWarning && (
          <View style={[styles.warningBanner, { backgroundColor: colors.danger + '15' }]}>
            <Ionicons name="warning" size={20} color={colors.danger} />
            <Text style={[styles.warningText, { color: colors.danger }]}>
              Orders may be paused! Verify stock to avoid this ({minutesSinceOpen} min since opening)
            </Text>
          </View>
        )}

        {/* Content */}
        {isLoading ? (
          <View style={styles.loadingContainer}>
            <ActivityIndicator size="large" color={colors.primary} />
            <Text style={[styles.loadingText, { color: colors.text.secondary }]}>
              Loading inventory...
            </Text>
          </View>
        ) : products.length === 0 ? (
          <View style={styles.emptyContainer}>
            <Ionicons name="checkmark-circle" size={64} color={colors.success} />
            <Text style={[styles.emptyTitle, { color: colors.text.primary }]}>
              All Good!
            </Text>
            <Text style={[styles.emptySubtitle, { color: colors.text.secondary }]}>
              No products need verification right now
            </Text>
            <TouchableOpacity
              style={[styles.continueBtn, { backgroundColor: colors.primary }]}
              onPress={handleSkip}
            >
              <Text style={styles.continueBtnText}>Continue to Dashboard</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <>
            <ScrollView style={styles.scrollView} showsVerticalScrollIndicator={false}>
              <Text style={[styles.sectionTitle, { color: colors.text.secondary }]}>
                PRODUCTS BELOW 50% STOCK ({products.length})
              </Text>
              
              {products.map((product) => (
                <View key={product.product_id} style={[styles.productCard, { backgroundColor: colors.card }]}>
                  <View style={styles.productHeader}>
                    {product.image ? (
                      <Image source={{ uri: product.image }} style={styles.productImage} />
                    ) : (
                      <View style={[styles.productImagePlaceholder, { backgroundColor: colors.background.secondary }]}>
                        <Ionicons name="cube-outline" size={24} color={colors.text.tertiary} />
                      </View>
                    )}
                    <View style={styles.productInfo}>
                      <Text style={[styles.productName, { color: colors.text.primary }]} numberOfLines={2}>
                        {product.name}
                      </Text>
                      <Text style={[styles.productCategory, { color: colors.text.tertiary }]}>
                        {product.category}
                      </Text>
                      <View style={styles.stockIndicator}>
                        <View style={[styles.stockBar, { backgroundColor: colors.background.secondary }]}>
                          <View 
                            style={[
                              styles.stockBarFill, 
                              { 
                                width: `${Math.min(product.stock_percentage, 100)}%`,
                                backgroundColor: product.stock_percentage < 35 ? colors.danger : colors.warning
                              }
                            ]} 
                          />
                        </View>
                        <Text style={[styles.stockPercent, { color: product.stock_percentage < 35 ? colors.danger : colors.warning }]}>
                          {product.stock_percentage.toFixed(0)}%
                        </Text>
                      </View>
                    </View>
                  </View>
                  
                  <View style={styles.productActions}>
                    <View style={styles.stockInputContainer}>
                      <Text style={[styles.inputLabel, { color: colors.text.secondary }]}>
                        Current Stock
                      </Text>
                      <View style={styles.stockInputRow}>
                        <TextInput
                          style={[
                            styles.stockInput, 
                            { 
                              backgroundColor: colors.background.secondary, 
                              color: colors.text.primary,
                              borderColor: colors.separator
                            }
                          ]}
                          value={verifiedStocks[product.product_id]?.stock || ''}
                          onChangeText={(v) => handleStockChange(product.product_id, v)}
                          keyboardType="number-pad"
                          placeholder="0"
                          placeholderTextColor={colors.text.tertiary}
                        />
                        <Text style={[styles.unitLabel, { color: colors.text.secondary }]}>
                          {product.unit}
                        </Text>
                      </View>
                    </View>
                    
                    <TouchableOpacity
                      style={[
                        styles.stockToggle,
                        verifiedStocks[product.product_id]?.inStock 
                          ? { backgroundColor: colors.success + '20' }
                          : { backgroundColor: colors.danger + '20' }
                      ]}
                      onPress={() => handleToggleInStock(product.product_id)}
                    >
                      <Ionicons
                        name={verifiedStocks[product.product_id]?.inStock ? 'checkmark-circle' : 'close-circle'}
                        size={20}
                        color={verifiedStocks[product.product_id]?.inStock ? colors.success : colors.danger}
                      />
                      <Text 
                        style={[
                          styles.stockToggleText, 
                          { color: verifiedStocks[product.product_id]?.inStock ? colors.success : colors.danger }
                        ]}
                      >
                        {verifiedStocks[product.product_id]?.inStock ? 'In Stock' : 'Out'}
                      </Text>
                    </TouchableOpacity>
                  </View>
                </View>
              ))}
              
              <View style={{ height: 120 }} />
            </ScrollView>

            {/* Submit Button */}
            <View style={[styles.bottomBar, { backgroundColor: colors.card, borderTopColor: colors.separator }]}>
              <TouchableOpacity
                style={[styles.skipBtn, { borderColor: colors.separator }]}
                onPress={handleSkip}
              >
                <Text style={[styles.skipBtnText, { color: colors.text.secondary }]}>Later</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.submitBtn, { backgroundColor: colors.primary }]}
                onPress={handleSubmit}
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <ActivityIndicator color="#FFFFFF" size="small" />
                ) : (
                  <>
                    <Ionicons name="checkmark-circle" size={20} color="#FFFFFF" />
                    <Text style={styles.submitBtnText}>Confirm All</Text>
                  </>
                )}
              </TouchableOpacity>
            </View>
          </>
        )}
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    paddingTop: 60,
    paddingBottom: 24,
    paddingHorizontal: 20,
  },
  headerContent: {
    alignItems: 'center',
  },
  iconContainer: {
    marginBottom: 16,
  },
  iconBg: {
    width: 64,
    height: 64,
    borderRadius: 32,
    justifyContent: 'center',
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: 22,
    fontWeight: '700',
    marginBottom: 8,
    textAlign: 'center',
  },
  headerSubtitle: {
    fontSize: 14,
    textAlign: 'center',
  },
  warningBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    paddingHorizontal: 16,
    marginHorizontal: 16,
    marginTop: 16,
    borderRadius: 12,
    gap: 8,
  },
  warningText: {
    flex: 1,
    fontSize: 13,
    fontWeight: '500',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 16,
    fontSize: 14,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 32,
  },
  emptyTitle: {
    fontSize: 24,
    fontWeight: '700',
    marginTop: 16,
  },
  emptySubtitle: {
    fontSize: 14,
    marginTop: 8,
    textAlign: 'center',
  },
  continueBtn: {
    marginTop: 24,
    paddingVertical: 14,
    paddingHorizontal: 32,
    borderRadius: 12,
  },
  continueBtnText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
  scrollView: {
    flex: 1,
    paddingHorizontal: 16,
    paddingTop: 16,
  },
  sectionTitle: {
    fontSize: 12,
    fontWeight: '600',
    letterSpacing: 0.5,
    marginBottom: 12,
    marginLeft: 4,
  },
  productCard: {
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
  },
  productHeader: {
    flexDirection: 'row',
    marginBottom: 16,
  },
  productImage: {
    width: 60,
    height: 60,
    borderRadius: 12,
  },
  productImagePlaceholder: {
    width: 60,
    height: 60,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
  },
  productInfo: {
    flex: 1,
    marginLeft: 12,
  },
  productName: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 4,
  },
  productCategory: {
    fontSize: 12,
    marginBottom: 8,
  },
  stockIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  stockBar: {
    flex: 1,
    height: 6,
    borderRadius: 3,
    overflow: 'hidden',
  },
  stockBarFill: {
    height: '100%',
    borderRadius: 3,
  },
  stockPercent: {
    fontSize: 12,
    fontWeight: '600',
    minWidth: 36,
    textAlign: 'right',
  },
  productActions: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 12,
  },
  stockInputContainer: {
    flex: 1,
  },
  inputLabel: {
    fontSize: 11,
    fontWeight: '500',
    marginBottom: 6,
  },
  stockInputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  stockInput: {
    flex: 1,
    height: 44,
    borderRadius: 10,
    paddingHorizontal: 14,
    fontSize: 16,
    fontWeight: '600',
    borderWidth: 1,
  },
  unitLabel: {
    fontSize: 13,
    fontWeight: '500',
  },
  stockToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: 10,
    gap: 6,
  },
  stockToggleText: {
    fontSize: 13,
    fontWeight: '600',
  },
  bottomBar: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    flexDirection: 'row',
    padding: 16,
    paddingBottom: 32,
    borderTopWidth: StyleSheet.hairlineWidth,
    gap: 12,
  },
  skipBtn: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 12,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  skipBtnText: {
    fontSize: 15,
    fontWeight: '600',
  },
  submitBtn: {
    flex: 2,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 14,
    borderRadius: 12,
    gap: 8,
  },
  submitBtnText: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '600',
  },
});
