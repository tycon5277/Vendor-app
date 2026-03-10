import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Modal,
  TouchableOpacity,
  TextInput,
  Animated,
  Image,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useTheme } from '../context/ThemeContext';
import { stockVerificationAPI } from '../utils/api';

interface LowStockProduct {
  product_id: string;
  name: string;
  category: string;
  current_stock: number;
  initial_stock: number;
  stock_percentage: number;
  image?: string;
  unit: string;
}

interface LowStockAlertProps {
  visible: boolean;
  product: LowStockProduct | null;
  onClose: () => void;
  onUpdate: () => void;
}

export default function LowStockAlert({ visible, product, onClose, onUpdate }: LowStockAlertProps) {
  const { colors, isDark } = useTheme();
  const [newStock, setNewStock] = useState('');
  const [isUpdating, setIsUpdating] = useState(false);
  const scaleAnim = React.useRef(new Animated.Value(0.9)).current;
  const opacityAnim = React.useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (visible && product) {
      setNewStock(String(product.current_stock));
      Animated.parallel([
        Animated.spring(scaleAnim, { toValue: 1, useNativeDriver: true }),
        Animated.timing(opacityAnim, { toValue: 1, duration: 200, useNativeDriver: true }),
      ]).start();
    } else {
      scaleAnim.setValue(0.9);
      opacityAnim.setValue(0);
    }
  }, [visible, product]);

  const handleUpdateStock = async () => {
    if (!product) return;
    setIsUpdating(true);
    try {
      await stockVerificationAPI.quickUpdate(
        product.product_id,
        parseInt(newStock) || 0,
        parseInt(newStock) > 0,
        false
      );
      onUpdate();
    } catch (error) {
      console.error('Update stock error:', error);
    } finally {
      setIsUpdating(false);
    }
  };

  const handleMarkOutOfStock = async () => {
    if (!product) return;
    setIsUpdating(true);
    try {
      await stockVerificationAPI.quickUpdate(
        product.product_id,
        undefined,
        undefined,
        true
      );
      onUpdate();
    } catch (error) {
      console.error('Mark out of stock error:', error);
    } finally {
      setIsUpdating(false);
    }
  };

  const handleDismiss = async () => {
    if (!product) return;
    try {
      await stockVerificationAPI.dismissAlert(product.product_id);
      onClose();
    } catch (error) {
      console.error('Dismiss alert error:', error);
      onClose();
    }
  };

  if (!visible || !product) return null;

  return (
    <Modal
      visible={visible}
      transparent
      animationType="none"
      onRequestClose={onClose}
    >
      <Animated.View style={[styles.overlay, { opacity: opacityAnim }]}>
        <TouchableOpacity style={styles.backdrop} onPress={onClose} data-testid="low-stock-backdrop" />
        <Animated.View 
          style={[
            styles.alertContainer, 
            { 
              backgroundColor: colors.card,
              transform: [{ scale: scaleAnim }]
            }
          ]}
          data-testid="low-stock-alert-container"
        >
          {/* Warning Header */}
          <View style={[styles.warningHeader, { backgroundColor: colors.warning + '15' }]}>
            <View style={[styles.warningIconBg, { backgroundColor: colors.warning }]}>
              <Ionicons name="warning" size={24} color="#FFFFFF" />
            </View>
            <Text style={[styles.warningTitle, { color: colors.warning }]} data-testid="low-stock-title">
              Low Stock Alert
            </Text>
          </View>

          {/* Product Info */}
          <View style={styles.productInfo}>
            {product.image ? (
              <Image source={{ uri: product.image }} style={styles.productImage} />
            ) : (
              <View style={[styles.productImagePlaceholder, { backgroundColor: colors.background.secondary }]}>
                <Ionicons name="cube-outline" size={32} color={colors.text.tertiary} />
              </View>
            )}
            <Text style={[styles.productName, { color: colors.text.primary }]} numberOfLines={2}>
              {product.name}
            </Text>
            <View style={styles.stockInfo}>
              <View style={[styles.stockBadge, { backgroundColor: colors.danger + '15' }]}>
                <Text style={[styles.stockBadgeText, { color: colors.danger }]}>
                  {product.stock_percentage.toFixed(0)}% remaining
                </Text>
              </View>
              <Text style={[styles.stockText, { color: colors.text.secondary }]}>
                {product.current_stock} {product.unit} left
              </Text>
            </View>
          </View>

          {/* Update Section */}
          <View style={styles.updateSection}>
            <Text style={[styles.updateLabel, { color: colors.text.secondary }]}>
              Update Stock Quantity
            </Text>
            <View style={styles.inputRow}>
              <TextInput
                style={[
                  styles.stockInput,
                  { 
                    backgroundColor: colors.background.secondary,
                    color: colors.text.primary,
                    borderColor: colors.separator
                  }
                ]}
                value={newStock}
                onChangeText={(v) => setNewStock(v.replace(/[^0-9]/g, ''))}
                keyboardType="number-pad"
                placeholder="Enter new stock"
                placeholderTextColor={colors.text.tertiary}
              />
              <Text style={[styles.unitText, { color: colors.text.secondary }]}>
                {product.unit}
              </Text>
            </View>
          </View>

          {/* Action Buttons */}
          <View style={styles.actions}>
            <TouchableOpacity
              style={[styles.actionBtn, styles.updateBtn, { backgroundColor: colors.primary }]}
              onPress={handleUpdateStock}
              disabled={isUpdating}
            >
              {isUpdating ? (
                <ActivityIndicator color="#FFFFFF" size="small" />
              ) : (
                <>
                  <Ionicons name="checkmark" size={18} color="#FFFFFF" />
                  <Text style={styles.actionBtnText}>Update Stock</Text>
                </>
              )}
            </TouchableOpacity>

            <View style={styles.secondaryActions}>
              <TouchableOpacity
                style={[styles.secondaryBtn, { backgroundColor: colors.danger + '15' }]}
                onPress={handleMarkOutOfStock}
                disabled={isUpdating}
              >
                <Ionicons name="close-circle" size={18} color={colors.danger} />
                <Text style={[styles.secondaryBtnText, { color: colors.danger }]}>
                  Mark Out of Stock
                </Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={[styles.secondaryBtn, { backgroundColor: colors.background.secondary }]}
                onPress={handleDismiss}
              >
                <Ionicons name="time" size={18} color={colors.text.secondary} />
                <Text style={[styles.secondaryBtnText, { color: colors.text.secondary }]}>
                  Dismiss
                </Text>
              </TouchableOpacity>
            </View>
          </View>
        </Animated.View>
      </Animated.View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
  },
  backdrop: {
    ...StyleSheet.absoluteFillObject,
  },
  alertContainer: {
    width: '90%',
    maxWidth: 400,
    borderRadius: 20,
    overflow: 'hidden',
  },
  warningHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 16,
    gap: 12,
  },
  warningIconBg: {
    width: 40,
    height: 40,
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
  },
  warningTitle: {
    fontSize: 18,
    fontWeight: '700',
  },
  productInfo: {
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 16,
  },
  productImage: {
    width: 80,
    height: 80,
    borderRadius: 16,
    marginBottom: 12,
  },
  productImagePlaceholder: {
    width: 80,
    height: 80,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 12,
  },
  productName: {
    fontSize: 17,
    fontWeight: '600',
    textAlign: 'center',
    marginBottom: 12,
  },
  stockInfo: {
    alignItems: 'center',
    gap: 6,
  },
  stockBadge: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
  },
  stockBadgeText: {
    fontSize: 13,
    fontWeight: '600',
  },
  stockText: {
    fontSize: 13,
  },
  updateSection: {
    paddingHorizontal: 20,
    paddingBottom: 16,
  },
  updateLabel: {
    fontSize: 12,
    fontWeight: '500',
    marginBottom: 8,
  },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  stockInput: {
    flex: 1,
    height: 48,
    borderRadius: 12,
    paddingHorizontal: 16,
    fontSize: 18,
    fontWeight: '600',
    borderWidth: 1,
  },
  unitText: {
    fontSize: 14,
    fontWeight: '500',
  },
  actions: {
    padding: 20,
    paddingTop: 0,
  },
  actionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 14,
    borderRadius: 12,
    gap: 8,
  },
  updateBtn: {
    marginBottom: 12,
  },
  actionBtnText: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '600',
  },
  secondaryActions: {
    flexDirection: 'row',
    gap: 8,
  },
  secondaryBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    borderRadius: 10,
    gap: 6,
  },
  secondaryBtnText: {
    fontSize: 13,
    fontWeight: '600',
  },
});
