import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  Image,
  Alert,
  Animated,
  Easing,
  FlatList,
  Modal,
  TextInput,
  Switch,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import { useAuthStore } from '../../../src/store/authStore';
import { vendorAPI, productAPI } from '../../../src/utils/api';
import { Product } from '../../../src/types';

const PRODUCT_CATEGORIES = [
  'All', 'Groceries', 'Dairy', 'Beverages', 'Snacks', 'Bakery',
  'Fruits', 'Vegetables', 'Meat', 'Seafood', 'Frozen', 'Other'
];

export default function MyShopScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { user, setUser } = useAuthStore();
  const [refreshing, setRefreshing] = useState(false);
  const [shopOpen, setShopOpen] = useState(user?.partner_status === 'available');
  const [products, setProducts] = useState<Product[]>([]);
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [showAddProduct, setShowAddProduct] = useState(false);
  const [productStats, setProductStats] = useState({ total: 0, inStock: 0, outOfStock: 0 });
  
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
      const response = await productAPI.getAll(selectedCategory === 'All' ? undefined : selectedCategory);
      setProducts(response.data);
      
      // Calculate stats
      const total = response.data.length;
      const inStock = response.data.filter((p: Product) => p.in_stock).length;
      setProductStats({ total, inStock, outOfStock: total - inStock });
    } catch (error) {
      console.error('Load products error:', error);
    }
  };

  useEffect(() => {
    loadData();
  }, [selectedCategory]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  }, [selectedCategory]);

  const toggleShopStatus = async () => {
    const newStatus = shopOpen ? 'offline' : 'available';
    try {
      await vendorAPI.updateStatus(newStatus);
      setShopOpen(!shopOpen);
      if (user) {
        setUser({ ...user, partner_status: newStatus });
      }
    } catch (error) {
      Alert.alert('Error', 'Failed to update shop status');
    }
  };

  const handleToggleStock = async (product: Product) => {
    try {
      await productAPI.updateStock(product.product_id, !product.in_stock);
      setProducts(products.map(p => 
        p.product_id === product.product_id 
          ? { ...p, in_stock: !p.in_stock } 
          : p
      ));
      loadData(); // Refresh stats
    } catch (error) {
      Alert.alert('Error', 'Failed to update stock');
    }
  };

  const handleDeleteProduct = (product: Product) => {
    Alert.alert(
      'Delete Product',
      `Remove "${product.name}" from your shop?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              await productAPI.delete(product.product_id);
              setProducts(products.filter(p => p.product_id !== product.product_id));
              loadData();
            } catch (error) {
              Alert.alert('Error', 'Failed to delete product');
            }
          },
        },
      ]
    );
  };

  const glowColor = glowAnim.interpolate({
    inputRange: [0, 1],
    outputRange: ['rgba(34, 197, 94, 0)', 'rgba(34, 197, 94, 0.3)'],
  });

  const renderProductCard = ({ item }: { item: Product }) => (
    <View style={styles.productCard}>
      <View style={styles.productImageContainer}>
        {item.image ? (
          <Image source={{ uri: item.image }} style={styles.productImage} />
        ) : (
          <View style={styles.productImagePlaceholder}>
            <Ionicons name="cube-outline" size={28} color="#D1D5DB" />
          </View>
        )}
        {!item.in_stock && (
          <View style={styles.outOfStockBadge}>
            <Text style={styles.outOfStockText}>OUT</Text>
          </View>
        )}
      </View>
      
      <View style={styles.productInfo}>
        <Text style={styles.productName} numberOfLines={1}>{item.name}</Text>
        <Text style={styles.productCategory}>{item.category}</Text>
        <View style={styles.productPriceRow}>
          {item.discounted_price ? (
            <>
              <Text style={styles.productOriginalPrice}>₹{item.price}</Text>
              <Text style={styles.productPrice}>₹{item.discounted_price}</Text>
            </>
          ) : (
            <Text style={styles.productPrice}>₹{item.price}</Text>
          )}
        </View>
      </View>
      
      <View style={styles.productActions}>
        <TouchableOpacity
          style={[styles.stockToggleBtn, item.in_stock ? styles.stockToggleBtnActive : styles.stockToggleBtnInactive]}
          onPress={() => handleToggleStock(item)}
        >
          <Ionicons 
            name={item.in_stock ? "checkmark-circle" : "close-circle"} 
            size={16} 
            color={item.in_stock ? "#22C55E" : "#9CA3AF"} 
          />
          <Text style={[styles.stockToggleText, item.in_stock && styles.stockToggleTextActive]}>
            {item.in_stock ? 'In Stock' : 'Out'}
          </Text>
        </TouchableOpacity>
        
        <View style={styles.productActionBtns}>
          <TouchableOpacity 
            style={styles.editBtn}
            onPress={() => router.push(`/(main)/products/${item.product_id}`)}
          >
            <Ionicons name="pencil" size={16} color="#6366F1" />
          </TouchableOpacity>
          <TouchableOpacity 
            style={styles.deleteBtn}
            onPress={() => handleDeleteProduct(item)}
          >
            <Ionicons name="trash" size={16} color="#DC2626" />
          </TouchableOpacity>
        </View>
      </View>
    </View>
  );

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
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
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
            <Text style={styles.statLabel}>Out of Stock</Text>
          </View>
        </View>

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

        {/* Category Filter */}
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>Your Products</Text>
          <Text style={styles.productCount}>{products.length} items</Text>
        </View>
        
        <ScrollView 
          horizontal 
          showsHorizontalScrollIndicator={false}
          style={styles.categoryScroll}
          contentContainerStyle={styles.categoryContainer}
        >
          {PRODUCT_CATEGORIES.map((cat) => (
            <TouchableOpacity
              key={cat}
              style={[
                styles.categoryChip,
                selectedCategory === cat && styles.categoryChipActive
              ]}
              onPress={() => setSelectedCategory(cat)}
            >
              <Text style={[
                styles.categoryText,
                selectedCategory === cat && styles.categoryTextActive
              ]}>
                {cat}
              </Text>
            </TouchableOpacity>
          ))}
        </ScrollView>

        {/* Products List */}
        {products.length > 0 ? (
          <View style={styles.productsList}>
            {products.map((product) => (
              <View key={product.product_id}>
                {renderProductCard({ item: product })}
              </View>
            ))}
          </View>
        ) : (
          <View style={styles.emptyState}>
            <View style={styles.emptyIconContainer}>
              <Ionicons name="cube-outline" size={48} color="#D1D5DB" />
            </View>
            <Text style={styles.emptyTitle}>No products yet</Text>
            <Text style={styles.emptySubtitle}>
              {selectedCategory === 'All' 
                ? 'Start adding products to your shop'
                : `No products in ${selectedCategory}`}
            </Text>
            <TouchableOpacity 
              style={styles.emptyAddBtn}
              onPress={() => router.push('/(main)/products/add')}
            >
              <Ionicons name="add-circle" size={20} color="#FFFFFF" />
              <Text style={styles.emptyAddText}>Add Your First Product</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Quick Tips */}
        <View style={styles.tipsCard}>
          <View style={styles.tipsHeader}>
            <Ionicons name="bulb" size={20} color="#F59E0B" />
            <Text style={styles.tipsTitle}>Pro Tips</Text>
          </View>
          <Text style={styles.tipText}>• Add clear product images to increase sales by 40%</Text>
          <Text style={styles.tipText}>• Keep your stock updated to avoid customer disappointment</Text>
          <Text style={styles.tipText}>• Use discounts to move slow-selling items</Text>
        </View>

        <View style={{ height: 100 }} />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F9FAFB',
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
    gap: 10,
  },
  headerTitle: {
    fontSize: 22,
    fontWeight: '700',
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
  scrollView: {
    flex: 1,
  },
  // Status Card Styles
  statusCard: {
    margin: 16,
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 20,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 12,
    elevation: 8,
    overflow: 'hidden',
  },
  statusGlow: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    borderRadius: 20,
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
    borderRadius: 32,
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
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  statusValue: {
    fontSize: 16,
    fontWeight: '800',
    color: '#9CA3AF',
    marginTop: 4,
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
    width: 64,
    height: 36,
    backgroundColor: '#E5E7EB',
    borderRadius: 18,
    padding: 3,
    justifyContent: 'center',
  },
  toggleTrackActive: {
    backgroundColor: '#DCFCE7',
  },
  toggleThumb: {
    width: 30,
    height: 30,
    backgroundColor: '#FFFFFF',
    borderRadius: 15,
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  toggleThumbActive: {
    alignSelf: 'flex-end',
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
    paddingHorizontal: 12,
    gap: 8,
  },
  statCard: {
    flex: 1,
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 16,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  statCardTotal: {},
  statCardInStock: {},
  statCardOutStock: {},
  statValue: {
    fontSize: 24,
    fontWeight: '700',
    color: '#111827',
    marginTop: 8,
  },
  statLabel: {
    fontSize: 11,
    color: '#6B7280',
    marginTop: 4,
    fontWeight: '500',
  },
  // Add Product Button
  addProductBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    marginHorizontal: 16,
    marginTop: 16,
    padding: 16,
    borderRadius: 16,
    borderWidth: 2,
    borderColor: '#6366F1',
    borderStyle: 'dashed',
  },
  addProductIconContainer: {
    width: 48,
    height: 48,
    backgroundColor: '#6366F1',
    borderRadius: 24,
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
  // Section Header
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    marginTop: 24,
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#111827',
  },
  productCount: {
    fontSize: 14,
    color: '#6B7280',
    fontWeight: '500',
  },
  // Category Filter
  categoryScroll: {
    marginBottom: 16,
  },
  categoryContainer: {
    paddingHorizontal: 16,
    gap: 8,
  },
  categoryChip: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 20,
    backgroundColor: '#F3F4F6',
    marginRight: 8,
  },
  categoryChipActive: {
    backgroundColor: '#6366F1',
  },
  categoryText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#6B7280',
  },
  categoryTextActive: {
    color: '#FFFFFF',
  },
  // Products List
  productsList: {
    paddingHorizontal: 16,
  },
  productCard: {
    flexDirection: 'row',
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 12,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  productImageContainer: {
    width: 80,
    height: 80,
    borderRadius: 12,
    overflow: 'hidden',
    position: 'relative',
  },
  productImage: {
    width: '100%',
    height: '100%',
  },
  productImagePlaceholder: {
    width: '100%',
    height: '100%',
    backgroundColor: '#F3F4F6',
    justifyContent: 'center',
    alignItems: 'center',
  },
  outOfStockBadge: {
    position: 'absolute',
    top: 4,
    left: 4,
    backgroundColor: '#EF4444',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  outOfStockText: {
    fontSize: 9,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  productInfo: {
    flex: 1,
    marginLeft: 12,
    justifyContent: 'center',
  },
  productName: {
    fontSize: 15,
    fontWeight: '600',
    color: '#111827',
  },
  productCategory: {
    fontSize: 12,
    color: '#6B7280',
    marginTop: 2,
  },
  productPriceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 6,
    gap: 6,
  },
  productOriginalPrice: {
    fontSize: 13,
    color: '#9CA3AF',
    textDecorationLine: 'line-through',
  },
  productPrice: {
    fontSize: 16,
    fontWeight: '700',
    color: '#111827',
  },
  productActions: {
    justifyContent: 'space-between',
    alignItems: 'flex-end',
  },
  stockToggleBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 12,
    gap: 4,
  },
  stockToggleBtnActive: {
    backgroundColor: '#DCFCE7',
  },
  stockToggleBtnInactive: {
    backgroundColor: '#F3F4F6',
  },
  stockToggleText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#9CA3AF',
  },
  stockToggleTextActive: {
    color: '#22C55E',
  },
  productActionBtns: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 8,
  },
  editBtn: {
    width: 32,
    height: 32,
    backgroundColor: '#EEF2FF',
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
  },
  deleteBtn: {
    width: 32,
    height: 32,
    backgroundColor: '#FEE2E2',
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
  },
  // Empty State
  emptyState: {
    alignItems: 'center',
    paddingVertical: 40,
    paddingHorizontal: 20,
  },
  emptyIconContainer: {
    width: 80,
    height: 80,
    backgroundColor: '#F3F4F6',
    borderRadius: 40,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#374151',
  },
  emptySubtitle: {
    fontSize: 14,
    color: '#9CA3AF',
    marginTop: 4,
    textAlign: 'center',
  },
  emptyAddBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#6366F1',
    paddingHorizontal: 20,
    paddingVertical: 14,
    borderRadius: 12,
    marginTop: 20,
    gap: 8,
  },
  emptyAddText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  // Tips Card
  tipsCard: {
    backgroundColor: '#FFFBEB',
    marginHorizontal: 16,
    marginTop: 24,
    padding: 16,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#FDE68A',
  },
  tipsHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
  },
  tipsTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#92400E',
  },
  tipText: {
    fontSize: 13,
    color: '#78350F',
    marginBottom: 6,
    lineHeight: 20,
  },
});
