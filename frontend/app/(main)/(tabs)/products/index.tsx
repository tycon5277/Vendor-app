import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  Animated,
  Easing,
  Dimensions,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useAuthStore } from '../../../src/store/authStore';
import { vendorAPI, productAPI } from '../../../src/utils/api';
import { Product } from '../../../src/types';
import { useAlert } from '../../../src/context/AlertContext';

const { width } = Dimensions.get('window');

export default function MyShopScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { user, setUser } = useAuthStore();
  const { showAlert } = useAlert();
  const [refreshing, setRefreshing] = useState(false);
  const [shopOpen, setShopOpen] = useState(user?.partner_status === 'available');
  const [productStats, setProductStats] = useState({ total: 0, inStock: 0, outOfStock: 0, lowStock: 0 });
  
  // Animation for shop status
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const glowAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (shopOpen) {
      // Pulse animation for open status
      Animated.loop(
        Animated.sequence([
          Animated.timing(pulseAnim, {
            toValue: 1.05,
            duration: 1000,
            easing: Easing.inOut(Easing.ease),
            useNativeDriver: true,
          }),
          Animated.timing(pulseAnim, {
            toValue: 1,
            duration: 1000,
            easing: Easing.inOut(Easing.ease),
            useNativeDriver: true,
          }),
        ])
      ).start();
      
      Animated.timing(glowAnim, {
        toValue: 1,
        duration: 300,
        useNativeDriver: false,
      }).start();
    } else {
      pulseAnim.setValue(1);
      Animated.timing(glowAnim, {
        toValue: 0,
        duration: 300,
        useNativeDriver: false,
      }).start();
    }
  }, [shopOpen]);

  const loadData = async () => {
    try {
      const response = await productAPI.getAll();
      const products: Product[] = response.data;
      
      // Calculate stats
      const total = products.length;
      const inStock = products.filter((p: Product) => p.in_stock).length;
      const lowStock = products.filter((p: Product) => p.in_stock && p.stock_quantity <= 10).length;
      setProductStats({ total, inStock, outOfStock: total - inStock, lowStock });
    } catch (error) {
      console.error('Load products error:', error);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  }, []);

  const toggleShopStatus = async () => {
    const newStatus = shopOpen ? 'offline' : 'available';
    try {
      await vendorAPI.updateStatus(newStatus);
      setShopOpen(!shopOpen);
      if (user) {
        setUser({ ...user, partner_status: newStatus });
      }
    } catch (error) {
      showAlert({
        type: 'error',
        title: 'Oops!',
        message: 'Failed to update shop status. Please try again.',
      });
    }
  };

  const glowColor = glowAnim.interpolate({
    inputRange: [0, 1],
    outputRange: ['rgba(34, 197, 94, 0)', 'rgba(34, 197, 94, 0.3)'],
  });

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Ionicons name="storefront" size={28} color="#6366F1" />
          <Text style={styles.headerTitle}>My Shop</Text>
        </View>
        <TouchableOpacity 
          style={styles.settingsBtn}
          onPress={() => router.push('/(main)/profile')}
        >
          <Ionicons name="settings-outline" size={24} color="#374151" />
        </TouchableOpacity>
      </View>

      <ScrollView 
        style={styles.scrollView}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={['#6366F1']} />
        }
      >
        {/* Shop Status Card - Beautiful Toggle */}
        <Animated.View style={[styles.statusCard, { shadowColor: shopOpen ? '#22C55E' : '#9CA3AF' }]}>
          <Animated.View 
            style={[
              styles.statusGlow,
              { backgroundColor: glowColor }
            ]} 
          />
          
          <View style={styles.statusContent}>
            <View style={styles.statusLeft}>
              <Animated.View 
                style={[
                  styles.statusIconContainer,
                  shopOpen ? styles.statusIconOpen : styles.statusIconClosed,
                  { transform: [{ scale: pulseAnim }] }
                ]}
              >
                <Ionicons 
                  name={shopOpen ? "flash" : "flash-off"} 
                  size={32} 
                  color="#FFFFFF" 
                />
              </Animated.View>
              <View style={styles.statusTextContainer}>
                <Text style={styles.statusLabel}>Shop Status</Text>
                <Text style={[styles.statusValue, shopOpen && styles.statusValueOpen]}>
                  {shopOpen ? 'OPEN FOR BUSINESS' : 'CLOSED'}
                </Text>
                <Text style={styles.statusHint}>
                  {shopOpen ? 'Customers can see your products' : 'Your shop is hidden from customers'}
                </Text>
              </View>
            </View>
            
            <TouchableOpacity 
              style={[styles.statusToggle, shopOpen && styles.statusToggleActive]}
              onPress={toggleShopStatus}
              activeOpacity={0.8}
            >
              <View style={[styles.toggleTrack, shopOpen && styles.toggleTrackActive]}>
                <Animated.View 
                  style={[
                    styles.toggleThumb,
                    shopOpen && styles.toggleThumbActive,
                  ]}
                >
                  <Ionicons 
                    name={shopOpen ? "power" : "power-outline"} 
                    size={18} 
                    color={shopOpen ? "#22C55E" : "#9CA3AF"} 
                  />
                </Animated.View>
              </View>
            </TouchableOpacity>
          </View>
          
          {/* Status Indicator Dots */}
          <View style={styles.statusIndicators}>
            <View style={[styles.statusDot, shopOpen && styles.statusDotActive]} />
            <View style={[styles.statusDot, shopOpen && styles.statusDotActive, { opacity: shopOpen ? 0.7 : 0.3 }]} />
            <View style={[styles.statusDot, shopOpen && styles.statusDotActive, { opacity: shopOpen ? 0.4 : 0.1 }]} />
          </View>
        </Animated.View>

        {/* Quick Stats */}
        <View style={styles.statsRow}>
          <View style={[styles.statCard, styles.statCardTotal]}>
            <Ionicons name="cube" size={24} color="#6366F1" />
            <Text style={styles.statValue}>{productStats.total}</Text>
            <Text style={styles.statLabel}>Products</Text>
          </View>
          <View style={[styles.statCard, styles.statCardInStock]}>
            <Ionicons name="checkmark-circle" size={24} color="#22C55E" />
            <Text style={[styles.statValue, { color: '#22C55E' }]}>{productStats.inStock}</Text>
            <Text style={styles.statLabel}>In Stock</Text>
          </View>
          <View style={[styles.statCard, styles.statCardOutStock]}>
            <Ionicons name="alert-circle" size={24} color="#F59E0B" />
            <Text style={[styles.statValue, { color: '#F59E0B' }]}>{productStats.outOfStock}</Text>
            <Text style={styles.statLabel}>Out</Text>
          </View>
        </View>

        {/* Low Stock Alert */}
        {productStats.lowStock > 0 && (
          <TouchableOpacity 
            style={styles.alertCard}
            onPress={() => router.push('/(main)/(screens)/warehouse')}
          >
            <View style={styles.alertIcon}>
              <Ionicons name="warning" size={24} color="#D97706" />
            </View>
            <View style={styles.alertContent}>
              <Text style={styles.alertTitle}>{productStats.lowStock} items running low</Text>
              <Text style={styles.alertText}>Tap to manage stock in warehouse</Text>
            </View>
            <Ionicons name="chevron-forward" size={20} color="#D97706" />
          </TouchableOpacity>
        )}

        {/* Action Cards */}
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>Manage Shop</Text>
        </View>

        {/* My Warehouse - Main Product Management */}
        <TouchableOpacity 
          style={styles.warehouseCard}
          onPress={() => router.push('/(main)/(screens)/warehouse')}
          activeOpacity={0.9}
        >
          <View style={styles.warehouseIconBg}>
            <Ionicons name="file-tray-stacked" size={36} color="#FFFFFF" />
          </View>
          <View style={styles.warehouseContent}>
            <Text style={styles.warehouseTitle}>My Warehouse</Text>
            <Text style={styles.warehouseSubtitle}>View and manage all your products</Text>
            <View style={styles.warehouseStats}>
              <View style={styles.warehouseStat}>
                <Text style={styles.warehouseStatValue}>{productStats.total}</Text>
                <Text style={styles.warehouseStatLabel}>Total</Text>
              </View>
              <View style={styles.warehouseStatDivider} />
              <View style={styles.warehouseStat}>
                <Text style={[styles.warehouseStatValue, { color: '#22C55E' }]}>{productStats.inStock}</Text>
                <Text style={styles.warehouseStatLabel}>Active</Text>
              </View>
              <View style={styles.warehouseStatDivider} />
              <View style={styles.warehouseStat}>
                <Text style={[styles.warehouseStatValue, { color: '#F59E0B' }]}>{productStats.lowStock}</Text>
                <Text style={styles.warehouseStatLabel}>Low</Text>
              </View>
            </View>
          </View>
          <View style={styles.warehouseArrow}>
            <Ionicons name="arrow-forward-circle" size={32} color="#6366F1" />
          </View>
        </TouchableOpacity>

        {/* Add Product Button */}
        <TouchableOpacity 
          style={styles.addProductBtn}
          onPress={() => router.push('/(main)/products/add')}
        >
          <View style={styles.addProductIconContainer}>
            <Ionicons name="add" size={28} color="#FFFFFF" />
          </View>
          <View style={styles.addProductTextContainer}>
            <Text style={styles.addProductTitle}>Add New Product</Text>
            <Text style={styles.addProductSubtitle}>List items for your customers</Text>
          </View>
          <Ionicons name="chevron-forward" size={24} color="#6366F1" />
        </TouchableOpacity>

        {/* Quick Actions Grid */}
        <View style={styles.quickActionsGrid}>
          <TouchableOpacity style={styles.quickActionCard}>
            <View style={[styles.quickActionIcon, { backgroundColor: '#EEF2FF' }]}>
              <Ionicons name="pricetag" size={24} color="#6366F1" />
            </View>
            <Text style={styles.quickActionText}>Discounts</Text>
          </TouchableOpacity>
          
          <TouchableOpacity style={styles.quickActionCard}>
            <View style={[styles.quickActionIcon, { backgroundColor: '#FEF3C7' }]}>
              <Ionicons name="time" size={24} color="#F59E0B" />
            </View>
            <Text style={styles.quickActionText}>Timings</Text>
          </TouchableOpacity>
          
          <TouchableOpacity 
            style={styles.quickActionCard}
            onPress={() => router.push('/(main)/profile')}
          >
            <View style={[styles.quickActionIcon, { backgroundColor: '#DCFCE7' }]}>
              <Ionicons name="qr-code" size={24} color="#22C55E" />
            </View>
            <Text style={styles.quickActionText}>Shop QR</Text>
          </TouchableOpacity>
          
          <TouchableOpacity 
            style={styles.quickActionCard}
            onPress={() => router.push('/(main)/(screens)/promote')}
          >
            <View style={[styles.quickActionIcon, { backgroundColor: '#FCE7F3' }]}>
              <Ionicons name="megaphone" size={24} color="#EC4899" />
            </View>
            <Text style={styles.quickActionText}>Promote</Text>
          </TouchableOpacity>
        </View>

        {/* Pro Tips */}
        <View style={styles.tipsCard}>
          <View style={styles.tipsHeader}>
            <Ionicons name="bulb" size={20} color="#6366F1" />
            <Text style={styles.tipsTitle}>Pro Tips</Text>
          </View>
          <View style={styles.tipItem}>
            <Ionicons name="checkmark-circle" size={16} color="#22C55E" />
            <Text style={styles.tipText}>Add clear product images for better sales</Text>
          </View>
          <View style={styles.tipItem}>
            <Ionicons name="checkmark-circle" size={16} color="#22C55E" />
            <Text style={styles.tipText}>Keep stock levels updated to avoid cancellations</Text>
          </View>
          <View style={styles.tipItem}>
            <Ionicons name="checkmark-circle" size={16} color="#22C55E" />
            <Text style={styles.tipText}>Use discounts to attract more customers</Text>
          </View>
        </View>

        <View style={{ height: 100 }} />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F8FAFC',
  },
  scrollView: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 16,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  headerTitle: {
    fontSize: 24,
    fontWeight: '800',
    color: '#111827',
  },
  settingsBtn: {
    width: 44,
    height: 44,
    backgroundColor: '#F3F4F6',
    borderRadius: 22,
    justifyContent: 'center',
    alignItems: 'center',
  },
  // Status Card
  statusCard: {
    backgroundColor: '#FFFFFF',
    marginHorizontal: 16,
    marginTop: 16,
    borderRadius: 24,
    padding: 20,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.15,
    shadowRadius: 16,
    elevation: 8,
    overflow: 'hidden',
  },
  statusGlow: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
  },
  statusContent: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  statusLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  statusIconContainer: {
    width: 64,
    height: 64,
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
  },
  statusIconOpen: {
    backgroundColor: '#22C55E',
  },
  statusIconClosed: {
    backgroundColor: '#9CA3AF',
  },
  statusTextContainer: {
    marginLeft: 16,
    flex: 1,
  },
  statusLabel: {
    fontSize: 12,
    color: '#6B7280',
    fontWeight: '500',
  },
  statusValue: {
    fontSize: 16,
    fontWeight: '800',
    color: '#374151',
    marginTop: 2,
  },
  statusValueOpen: {
    color: '#22C55E',
  },
  statusHint: {
    fontSize: 11,
    color: '#9CA3AF',
    marginTop: 4,
  },
  statusToggle: {
    marginLeft: 12,
  },
  statusToggleActive: {},
  toggleTrack: {
    width: 60,
    height: 34,
    backgroundColor: '#E5E7EB',
    borderRadius: 17,
    padding: 3,
    justifyContent: 'center',
  },
  toggleTrackActive: {
    backgroundColor: '#DCFCE7',
  },
  toggleThumb: {
    width: 28,
    height: 28,
    backgroundColor: '#FFFFFF',
    borderRadius: 14,
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2,
  },
  toggleThumbActive: {
    transform: [{ translateX: 26 }],
  },
  statusIndicators: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginTop: 16,
    gap: 6,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#D1D5DB',
  },
  statusDotActive: {
    backgroundColor: '#22C55E',
  },
  // Stats Row
  statsRow: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    marginTop: 16,
    gap: 10,
  },
  statCard: {
    flex: 1,
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 16,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 8,
    elevation: 2,
  },
  statCardTotal: {},
  statCardInStock: {},
  statCardOutStock: {},
  statValue: {
    fontSize: 24,
    fontWeight: '800',
    color: '#111827',
    marginTop: 8,
  },
  statLabel: {
    fontSize: 11,
    color: '#6B7280',
    marginTop: 4,
  },
  // Alert Card
  alertCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFBEB',
    marginHorizontal: 16,
    marginTop: 16,
    padding: 14,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#FDE68A',
  },
  alertIcon: {
    width: 44,
    height: 44,
    backgroundColor: '#FEF3C7',
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
  },
  alertContent: {
    flex: 1,
    marginLeft: 12,
  },
  alertTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#92400E',
  },
  alertText: {
    fontSize: 12,
    color: '#B45309',
    marginTop: 2,
  },
  // Section Header
  sectionHeader: {
    paddingHorizontal: 16,
    marginTop: 24,
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#111827',
  },
  // Warehouse Card
  warehouseCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    marginHorizontal: 16,
    padding: 16,
    borderRadius: 20,
    shadowColor: '#6366F1',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.12,
    shadowRadius: 12,
    elevation: 4,
    borderWidth: 2,
    borderColor: '#EEF2FF',
  },
  warehouseIconBg: {
    width: 64,
    height: 64,
    backgroundColor: '#6366F1',
    borderRadius: 18,
    justifyContent: 'center',
    alignItems: 'center',
  },
  warehouseContent: {
    flex: 1,
    marginLeft: 14,
  },
  warehouseTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: '#111827',
  },
  warehouseSubtitle: {
    fontSize: 13,
    color: '#6B7280',
    marginTop: 2,
  },
  warehouseStats: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 10,
    gap: 12,
  },
  warehouseStat: {
    alignItems: 'center',
  },
  warehouseStatValue: {
    fontSize: 16,
    fontWeight: '700',
    color: '#111827',
  },
  warehouseStatLabel: {
    fontSize: 10,
    color: '#9CA3AF',
  },
  warehouseStatDivider: {
    width: 1,
    height: 24,
    backgroundColor: '#E5E7EB',
  },
  warehouseArrow: {
    marginLeft: 8,
  },
  // Add Product Button
  addProductBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    marginHorizontal: 16,
    marginTop: 12,
    padding: 16,
    borderRadius: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 8,
    elevation: 2,
  },
  addProductIconContainer: {
    width: 52,
    height: 52,
    backgroundColor: '#22C55E',
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
  },
  addProductTextContainer: {
    flex: 1,
    marginLeft: 14,
  },
  addProductTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#111827',
  },
  addProductSubtitle: {
    fontSize: 13,
    color: '#6B7280',
    marginTop: 2,
  },
  // Quick Actions Grid
  quickActionsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    paddingHorizontal: 16,
    marginTop: 20,
    gap: 10,
  },
  quickActionCard: {
    width: (width - 42) / 2,
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 16,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.03,
    shadowRadius: 4,
    elevation: 1,
  },
  quickActionIcon: {
    width: 52,
    height: 52,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 10,
  },
  quickActionText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#374151',
  },
  // Tips Card
  tipsCard: {
    backgroundColor: '#FFFFFF',
    marginHorizontal: 16,
    marginTop: 20,
    padding: 18,
    borderRadius: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.03,
    shadowRadius: 4,
    elevation: 1,
  },
  tipsHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 14,
  },
  tipsTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#111827',
  },
  tipItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 10,
  },
  tipText: {
    fontSize: 13,
    color: '#4B5563',
    flex: 1,
  },
});
