import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  Image,
  Animated,
  TextInput,
  Dimensions,
  ScrollView,
  AppState,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { useFocusEffect } from '@react-navigation/native';
import { Ionicons } from '@expo/vector-icons';
import { productAPI } from '../../src/utils/api';
import { Product } from '../../src/types';
import { useToastStore } from '../../src/store/toastStore';

const { width } = Dimensions.get('window');

// Category data with icons
const CATEGORY_DATA = [
  { id: 'All', label: 'All', icon: 'grid' },
  { id: 'Groceries', label: 'Groceries', icon: 'basket' },
  { id: 'Dairy', label: 'Dairy', icon: 'water' },
  { id: 'Beverages', label: 'Drinks', icon: 'cafe' },
  { id: 'Snacks', label: 'Snacks', icon: 'fast-food' },
  { id: 'Bakery', label: 'Bakery', icon: 'pizza' },
  { id: 'Fruits', label: 'Fruits', icon: 'nutrition' },
  { id: 'Vegetables', label: 'Veggies', icon: 'leaf' },
  { id: 'Frozen', label: 'Frozen', icon: 'snow' },
  { id: 'Other', label: 'Other', icon: 'ellipsis-horizontal' },
];

type FilterType = 'all' | 'in_stock' | 'low_stock' | 'out_of_stock';

export default function WarehouseScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const params = useLocalSearchParams<{ filter?: string }>();
  const { pendingToast, clearPendingToast } = useToastStore();
  const [products, setProducts] = useState<Product[]>([]);
  const [filteredProducts, setFilteredProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [selectedFilter, setSelectedFilter] = useState<FilterType>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const fadeAnim = useRef(new Animated.Value(0)).current;

  // Set initial filter from params when screen loads (from Orders page navigation)
  useEffect(() => {
    if (params?.filter && ['all', 'in_stock', 'low_stock', 'out_of_stock'].includes(params.filter)) {
      setSelectedFilter(params.filter as FilterType);
    }
  }, [params?.filter]);

  // Check for pending toast from add/edit product screens
  useFocusEffect(
    useCallback(() => {
      if (pendingToast) {
        showClaymorphismAlert(pendingToast.type, pendingToast.title, pendingToast.message);
        clearPendingToast();
      }
    }, [pendingToast])
  );

  // Claymorphism Alert State
  const [alertVisible, setAlertVisible] = useState(false);
  const [alertType, setAlertType] = useState<'success' | 'error' | 'warning'>('success');
  const [alertTitle, setAlertTitle] = useState('');
  const [alertMessage, setAlertMessage] = useState('');
  const alertAnim = useRef(new Animated.Value(0)).current;
  const alertScale = useRef(new Animated.Value(0.8)).current;

  // Confirmation modal state
  const [confirmModalVisible, setConfirmModalVisible] = useState(false);
  const [pendingDeleteProduct, setPendingDeleteProduct] = useState<Product | null>(null);
  const confirmModalAnim = useRef(new Animated.Value(0)).current;
  const confirmModalScale = useRef(new Animated.Value(0.8)).current;

  const showClaymorphismAlert = (type: 'success' | 'error' | 'warning', title: string, message: string) => {
    setAlertType(type);
    setAlertTitle(title);
    setAlertMessage(message);
    setAlertVisible(true);
    
    Animated.parallel([
      Animated.spring(alertAnim, {
        toValue: 1,
        friction: 8,
        tension: 40,
        useNativeDriver: true,
      }),
      Animated.spring(alertScale, {
        toValue: 1,
        friction: 8,
        tension: 40,
        useNativeDriver: true,
      }),
    ]).start();

    setTimeout(() => {
      hideClaymorphismAlert();
    }, 2000);
  };

  const hideClaymorphismAlert = () => {
    Animated.parallel([
      Animated.timing(alertAnim, {
        toValue: 0,
        duration: 200,
        useNativeDriver: true,
      }),
      Animated.timing(alertScale, {
        toValue: 0.8,
        duration: 200,
        useNativeDriver: true,
      }),
    ]).start(() => {
      setAlertVisible(false);
    });
  };

  const showConfirmModal = (product: Product) => {
    setPendingDeleteProduct(product);
    setConfirmModalVisible(true);
    Animated.parallel([
      Animated.spring(confirmModalAnim, {
        toValue: 1,
        friction: 8,
        tension: 40,
        useNativeDriver: true,
      }),
      Animated.spring(confirmModalScale, {
        toValue: 1,
        friction: 8,
        tension: 40,
        useNativeDriver: true,
      }),
    ]).start();
  };

  const hideConfirmModal = () => {
    Animated.parallel([
      Animated.timing(confirmModalAnim, {
        toValue: 0,
        duration: 200,
        useNativeDriver: true,
      }),
      Animated.timing(confirmModalScale, {
        toValue: 0.8,
        duration: 200,
        useNativeDriver: true,
      }),
    ]).start(() => {
      setConfirmModalVisible(false);
      setPendingDeleteProduct(null);
    });
  };

  const loadProducts = async () => {
    try {
      const response = await productAPI.getAll();
      setProducts(response.data);
      applyFilters(response.data, selectedCategory, selectedFilter, searchQuery);
    } catch (error) {
      console.error('Load products error:', error);
    } finally {
      setLoading(false);
    }
  };

  const applyFilters = (data: Product[], category: string, filter: FilterType, search: string) => {
    let filtered = [...data];

    // Category filter
    if (category !== 'All') {
      filtered = filtered.filter(p => p.category === category);
    }

    // Stock filter - with robust checks
    switch (filter) {
      case 'in_stock':
        // Products that are in stock AND have more than 10 items
        filtered = filtered.filter(p => p.in_stock === true && (p.stock_quantity || 0) > 10);
        break;
      case 'low_stock':
        // Products that are in stock but have 10 or fewer items
        filtered = filtered.filter(p => p.in_stock === true && (p.stock_quantity || 0) <= 10);
        break;
      case 'out_of_stock':
        // Products that are marked as out of stock
        filtered = filtered.filter(p => p.in_stock === false || p.in_stock === undefined);
        break;
      // 'all' case - no filtering needed
    }

    // Search filter
    if (search.trim()) {
      filtered = filtered.filter(p => 
        p.name.toLowerCase().includes(search.toLowerCase()) ||
        p.category.toLowerCase().includes(search.toLowerCase())
      );
    }

    setFilteredProducts(filtered);
  };

  // Auto-refresh when screen comes into focus
  useFocusEffect(
    useCallback(() => {
      loadProducts();
      Animated.timing(fadeAnim, {
        toValue: 1,
        duration: 400,
        useNativeDriver: true,
      }).start();
    }, [])
  );

  // Refresh when app comes to foreground
  useEffect(() => {
    const subscription = AppState.addEventListener('change', (nextAppState) => {
      if (nextAppState === 'active') {
        loadProducts();
      }
    });

    return () => subscription.remove();
  }, []);

  // Handle hardware back button - removed, handled in _layout.tsx

  useEffect(() => {
    applyFilters(products, selectedCategory, selectedFilter, searchQuery);
  }, [selectedCategory, selectedFilter, searchQuery]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadProducts();
    setRefreshing(false);
  }, [selectedCategory, selectedFilter, searchQuery]);

  const handleToggleStock = async (product: Product) => {
    try {
      await productAPI.updateStock(product.product_id, !product.in_stock);
      setProducts(products.map(p => 
        p.product_id === product.product_id 
          ? { ...p, in_stock: !p.in_stock } 
          : p
      ));
      loadProducts();
      showClaymorphismAlert(
        'success', 
        product.in_stock ? 'Out of Stock 📦' : 'Back in Stock! 🎉',
        product.in_stock ? `${product.name} marked as out of stock` : `${product.name} is now available`
      );
    } catch (error) {
      showClaymorphismAlert('error', 'Oops! 😅', 'Failed to update stock status');
    }
  };

  const handleDeleteProduct = (product: Product) => {
    showConfirmModal(product);
  };

  const confirmDeleteProduct = async () => {
    if (!pendingDeleteProduct) return;
    
    try {
      await productAPI.delete(pendingDeleteProduct.product_id);
      setProducts(products.filter(p => p.product_id !== pendingDeleteProduct.product_id));
      loadProducts();
      hideConfirmModal();
      showClaymorphismAlert('success', 'Deleted! 🗑️', `${pendingDeleteProduct.name} removed from warehouse`);
    } catch (error) {
      hideConfirmModal();
      showClaymorphismAlert('error', 'Oops! 😅', 'Failed to delete product');
    }
  };

  // Stats - consistent with filter logic
  const stats = {
    total: products.length,
    inStock: products.filter(p => p.in_stock === true && (p.stock_quantity || 0) > 10).length,
    lowStock: products.filter(p => p.in_stock === true && (p.stock_quantity || 0) <= 10).length,
    outOfStock: products.filter(p => p.in_stock === false || p.in_stock === undefined).length,
  };

  const filters: { key: FilterType; label: string; count: number; color: string }[] = [
    { key: 'all', label: 'All', count: stats.total, color: '#6366F1' },
    { key: 'in_stock', label: 'In Stock', count: stats.inStock, color: '#22C55E' },
    { key: 'low_stock', label: 'Low Stock', count: stats.lowStock, color: '#F59E0B' },
    { key: 'out_of_stock', label: 'Out', count: stats.outOfStock, color: '#EF4444' },
  ];

  const renderProduct = ({ item }: { item: Product }) => {
    const isLowStock = item.in_stock && item.stock_quantity <= 10;
    
    return (
      <TouchableOpacity
        style={[
          styles.productCard,
          !item.in_stock && styles.productCardOutOfStock,
          isLowStock && styles.productCardLowStock,
        ]}
        onPress={() => router.push(`/(main)/product-edit/${item.product_id}`)}
        activeOpacity={0.7}
      >
        <View style={styles.productImageContainer}>
          {item.image ? (
            <Image source={{ uri: item.image }} style={styles.productImage} />
          ) : (
            <View style={styles.productImagePlaceholder}>
              <Ionicons name="cube-outline" size={28} color="#D1D5DB" />
            </View>
          )}
          {!item.in_stock && (
            <View style={styles.outOfStockOverlay}>
              <Text style={styles.outOfStockText}>OUT</Text>
            </View>
          )}
          {isLowStock && (
            <View style={styles.lowStockBadge}>
              <Text style={styles.lowStockText}>{item.stock_quantity}</Text>
            </View>
          )}
        </View>
        
        <View style={styles.productInfo}>
          <Text style={styles.productName} numberOfLines={2}>{item.name}</Text>
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
          <View style={styles.stockInfo}>
            <Ionicons 
              name="cube" 
              size={14} 
              color={item.in_stock ? (isLowStock ? '#F59E0B' : '#22C55E') : '#EF4444'} 
            />
            <Text style={[
              styles.stockText,
              { color: item.in_stock ? (isLowStock ? '#F59E0B' : '#22C55E') : '#EF4444' }
            ]}>
              {item.in_stock ? `${item.stock_quantity} in stock` : 'Out of stock'}
            </Text>
          </View>
        </View>
        
        <View style={styles.productActions}>
          <TouchableOpacity
            style={[
              styles.stockToggleBtn,
              item.in_stock ? styles.stockToggleBtnActive : styles.stockToggleBtnInactive
            ]}
            onPress={() => handleToggleStock(item)}
          >
            <Ionicons 
              name={item.in_stock ? "checkmark-circle" : "close-circle"} 
              size={20} 
              color={item.in_stock ? "#22C55E" : "#9CA3AF"} 
            />
          </TouchableOpacity>
          
          <TouchableOpacity 
            style={styles.editBtn}
            onPress={() => router.push(`/(main)/product-edit/${item.product_id}`)}
          >
            <Ionicons name="pencil" size={18} color="#6366F1" />
          </TouchableOpacity>
          
          <TouchableOpacity 
            style={styles.deleteBtn}
            onPress={() => handleDeleteProduct(item)}
          >
            <Ionicons name="trash" size={18} color="#DC2626" />
          </TouchableOpacity>
        </View>
      </TouchableOpacity>
    );
  };

  return (
    <Animated.View style={[styles.container, { paddingTop: insets.top, opacity: fadeAnim }]}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.backBtn} onPress={() => router.back()}>
          <Ionicons name="arrow-back" size={24} color="#374151" />
        </TouchableOpacity>
        <View style={styles.headerCenter}>
          <Text style={styles.headerTitle}>My Warehouse</Text>
          <Text style={styles.headerSubtitle}>{stats.total} products</Text>
        </View>
        <TouchableOpacity 
          style={styles.addBtn}
          onPress={() => router.push('/(main)/product-add')}
        >
          <Ionicons name="add" size={24} color="#FFFFFF" />
        </TouchableOpacity>
      </View>

      {/* Search Bar */}
      <View style={styles.searchContainer}>
        <View style={styles.searchBar}>
          <Ionicons name="search" size={20} color="#9CA3AF" />
          <TextInput
            style={styles.searchInput}
            placeholder="Search products..."
            placeholderTextColor="#9CA3AF"
            value={searchQuery}
            onChangeText={setSearchQuery}
          />
          {searchQuery.length > 0 && (
            <TouchableOpacity onPress={() => setSearchQuery('')}>
              <Ionicons name="close-circle" size={20} color="#9CA3AF" />
            </TouchableOpacity>
          )}
        </View>
      </View>

      {/* Filter Tabs - Scrollable */}
      <View style={styles.filterWrapper}>
        <ScrollView 
          horizontal 
          showsHorizontalScrollIndicator={false}
          style={styles.filterScrollContainer}
          contentContainerStyle={styles.filterContainer}
        >
          {filters.map((filter) => {
            const isActive = selectedFilter === filter.key;
            return (
              <TouchableOpacity
                key={filter.key}
                style={[
                  styles.filterTab,
                  isActive && { 
                    backgroundColor: filter.color, 
                    borderColor: filter.color,
                  },
                ]}
                onPress={() => setSelectedFilter(filter.key)}
              >
                <Ionicons 
                  name={
                    filter.key === 'all' ? 'apps' :
                    filter.key === 'in_stock' ? 'checkmark-circle' :
                    filter.key === 'low_stock' ? 'warning' : 'close-circle'
                  } 
                  size={16} 
                  color={isActive ? '#FFFFFF' : '#6B7280'} 
                />
                <Text style={[
                  styles.filterTabText,
                  isActive && { color: '#FFFFFF', fontWeight: '700' },
                ]}>
                  {filter.label}
                </Text>
                <View style={[
                  styles.filterBadge,
                  { backgroundColor: isActive ? 'rgba(255,255,255,0.3)' : '#E5E7EB' },
                ]}>
                  <Text style={[
                    styles.filterBadgeText,
                    { color: isActive ? '#FFFFFF' : '#6B7280' },
                  ]}>
                    {filter.count}
                  </Text>
                </View>
              </TouchableOpacity>
            );
          })}
        </ScrollView>
      </View>

      {/* Category Scroll - With Icons */}
      <View style={styles.categoryWrapper}>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.categoryContainer}
        >
          {CATEGORY_DATA.map((cat) => {
            const isActive = selectedCategory === cat.id;
            // Count products in this category
            const catCount = cat.id === 'All' 
              ? products.length 
              : products.filter(p => p.category === cat.id).length;
            
            return (
              <TouchableOpacity
                key={cat.id}
                style={[
                  styles.categoryChip,
                  isActive && styles.categoryChipActive,
                ]}
                onPress={() => setSelectedCategory(cat.id)}
              >
                <View style={[
                  styles.categoryIconBg,
                  isActive && styles.categoryIconBgActive,
                ]}>
                  <Ionicons 
                    name={cat.icon as any} 
                    size={18} 
                    color={isActive ? '#FFFFFF' : '#6366F1'} 
                  />
                </View>
                <Text style={[
                  styles.categoryText,
                  isActive && styles.categoryTextActive,
                ]}>
                  {cat.label}
                </Text>
                {catCount > 0 && (
                  <View style={[
                    styles.categoryBadge,
                    isActive && styles.categoryBadgeActive,
                  ]}>
                    <Text style={[
                      styles.categoryBadgeText,
                      isActive && styles.categoryBadgeTextActive,
                    ]}>
                      {catCount}
                    </Text>
                  </View>
                )}
              </TouchableOpacity>
            );
          })}
        </ScrollView>
      </View>

      {/* Products List */}
      <FlatList
        data={filteredProducts}
        renderItem={renderProduct}
        keyExtractor={(item) => item.product_id}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={['#6366F1']} />
        }
        showsVerticalScrollIndicator={false}
        numColumns={2}
        columnWrapperStyle={styles.columnWrapper}
        ListEmptyComponent={
          <View style={styles.emptyState}>
            <View style={styles.emptyIconBg}>
              <Ionicons name="cube-outline" size={48} color="#D1D5DB" />
            </View>
            <Text style={styles.emptyTitle}>
              {searchQuery ? 'No products found' : 'No products yet'}
            </Text>
            <Text style={styles.emptySubtitle}>
              {searchQuery 
                ? 'Try adjusting your search or filters'
                : 'Add products to start selling'}
            </Text>
            {!searchQuery && (
              <TouchableOpacity 
                style={styles.emptyAddBtn}
                onPress={() => router.push('/(main)/product-add')}
              >
                <Ionicons name="add-circle" size={20} color="#FFFFFF" />
                <Text style={styles.emptyAddBtnText}>Add Product</Text>
              </TouchableOpacity>
            )}
          </View>
        }
      />

      {/* Claymorphism Alert */}
      {alertVisible && (
        <Animated.View 
          style={[
            styles.alertContainer,
            {
              opacity: alertAnim,
              transform: [
                { scale: alertScale },
                { translateY: alertAnim.interpolate({
                  inputRange: [0, 1],
                  outputRange: [50, 0],
                })}
              ],
            }
          ]}
        >
          <View style={[
            styles.alertBox,
            alertType === 'success' && styles.alertBoxSuccess,
            alertType === 'error' && styles.alertBoxError,
            alertType === 'warning' && styles.alertBoxWarning,
          ]}>
            <View style={styles.alertInner}>
              <View style={[
                styles.alertIconBg,
                alertType === 'success' && styles.alertIconBgSuccess,
                alertType === 'error' && styles.alertIconBgError,
                alertType === 'warning' && styles.alertIconBgWarning,
              ]}>
                <Ionicons 
                  name={
                    alertType === 'success' ? 'checkmark-circle' :
                    alertType === 'error' ? 'close-circle' : 'warning'
                  } 
                  size={28} 
                  color={
                    alertType === 'success' ? '#22C55E' :
                    alertType === 'error' ? '#EF4444' : '#F59E0B'
                  } 
                />
              </View>
              <View style={styles.alertContent}>
                <Text style={styles.alertTitle}>{alertTitle}</Text>
                <Text style={styles.alertMessage}>{alertMessage}</Text>
              </View>
            </View>
          </View>
        </Animated.View>
      )}

      {/* Claymorphism Delete Confirmation Modal */}
      {confirmModalVisible && (
        <Animated.View 
          style={[
            styles.modalOverlay,
            { opacity: confirmModalAnim }
          ]}
        >
          <Animated.View 
            style={[
              styles.confirmModal,
              { transform: [{ scale: confirmModalScale }] }
            ]}
          >
            <View style={styles.confirmModalInner}>
              <View style={styles.confirmIconBg}>
                <Ionicons name="trash" size={32} color="#EF4444" />
              </View>
              <Text style={styles.confirmTitle}>Delete Product? 🗑️</Text>
              <Text style={styles.confirmMessage}>
                Remove "{pendingDeleteProduct?.name}" from your warehouse?
              </Text>
              <View style={styles.confirmButtons}>
                <TouchableOpacity 
                  style={styles.confirmCancelBtn}
                  onPress={hideConfirmModal}
                >
                  <Text style={styles.confirmCancelText}>Cancel</Text>
                </TouchableOpacity>
                <TouchableOpacity 
                  style={styles.confirmDeleteBtn}
                  onPress={confirmDeleteProduct}
                >
                  <Ionicons name="trash" size={18} color="#FFFFFF" />
                  <Text style={styles.confirmDeleteText}>Delete</Text>
                </TouchableOpacity>
              </View>
            </View>
          </Animated.View>
        </Animated.View>
      )}
    </Animated.View>
  );
}

const cardWidth = (width - 48) / 2;

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F8FAFC',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  backBtn: {
    width: 40,
    height: 40,
    justifyContent: 'center',
    alignItems: 'center',
  },
  headerCenter: {
    flex: 1,
    marginLeft: 8,
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: '800',
    color: '#111827',
  },
  headerSubtitle: {
    fontSize: 13,
    color: '#6B7280',
  },
  addBtn: {
    width: 44,
    height: 44,
    backgroundColor: '#6366F1',
    borderRadius: 14,
    justifyContent: 'center',
    alignItems: 'center',
  },
  // Search
  searchContainer: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: '#FFFFFF',
  },
  searchBar: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F3F4F6',
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 10,
    gap: 10,
  },
  searchInput: {
    flex: 1,
    fontSize: 15,
    color: '#111827',
  },
  // Filters
  filterContainer: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: '#FFFFFF',
    gap: 10,
  },
  filterTab: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 12,
    borderWidth: 1.5,
    borderColor: '#E5E7EB',
    backgroundColor: '#F9FAFB',
    gap: 8,
  },
  filterTabText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#374151',
  },
  filterBadge: {
    minWidth: 20,
    height: 20,
    borderRadius: 10,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 6,
  },
  filterBadgeText: {
    fontSize: 11,
    fontWeight: '700',
  },
  // Category with icons
  categoryWrapper: {
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  categoryContainer: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    gap: 12,
  },
  categoryChip: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingVertical: 10,
    backgroundColor: '#F9FAFB',
    borderRadius: 16,
    borderWidth: 1.5,
    borderColor: '#E5E7EB',
    gap: 8,
  },
  categoryChipActive: {
    backgroundColor: '#6366F1',
    borderColor: '#6366F1',
    shadowColor: '#6366F1',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 4,
  },
  categoryIconBg: {
    width: 32,
    height: 32,
    borderRadius: 10,
    backgroundColor: '#EEF2FF',
    justifyContent: 'center',
    alignItems: 'center',
  },
  categoryIconBgActive: {
    backgroundColor: 'rgba(255,255,255,0.2)',
  },
  categoryText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#374151',
  },
  categoryTextActive: {
    color: '#FFFFFF',
  },
  categoryBadge: {
    backgroundColor: '#E5E7EB',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 10,
    minWidth: 24,
    alignItems: 'center',
  },
  categoryBadgeActive: {
    backgroundColor: 'rgba(255,255,255,0.3)',
  },
  categoryBadgeText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#6B7280',
  },
  categoryBadgeTextActive: {
    color: '#FFFFFF',
  },
  // List
  listContent: {
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 100,
  },
  columnWrapper: {
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  // Product Card
  productCard: {
    width: cardWidth,
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    overflow: 'hidden',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  productCardOutOfStock: {
    opacity: 0.7,
    borderWidth: 1,
    borderColor: '#FEE2E2',
  },
  productCardLowStock: {
    borderWidth: 1,
    borderColor: '#FDE68A',
  },
  productImageContainer: {
    width: '100%',
    height: 120,
    backgroundColor: '#F9FAFB',
    position: 'relative',
  },
  productImage: {
    width: '100%',
    height: '100%',
    resizeMode: 'cover',
  },
  productImagePlaceholder: {
    width: '100%',
    height: '100%',
    justifyContent: 'center',
    alignItems: 'center',
  },
  outOfStockOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  outOfStockText: {
    fontSize: 14,
    fontWeight: '800',
    color: '#FFFFFF',
  },
  lowStockBadge: {
    position: 'absolute',
    top: 8,
    right: 8,
    backgroundColor: '#F59E0B',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
  },
  lowStockText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  productInfo: {
    padding: 12,
  },
  productName: {
    fontSize: 14,
    fontWeight: '600',
    color: '#111827',
    marginBottom: 4,
    minHeight: 36,
  },
  productCategory: {
    fontSize: 11,
    color: '#9CA3AF',
    marginBottom: 6,
  },
  productPriceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  productPrice: {
    fontSize: 16,
    fontWeight: '700',
    color: '#111827',
  },
  productOriginalPrice: {
    fontSize: 13,
    color: '#9CA3AF',
    textDecorationLine: 'line-through',
  },
  stockInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
    gap: 4,
  },
  stockText: {
    fontSize: 12,
    fontWeight: '600',
  },
  productActions: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    paddingVertical: 10,
    paddingHorizontal: 8,
    borderTopWidth: 1,
    borderTopColor: '#F3F4F6',
  },
  stockToggleBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    justifyContent: 'center',
    alignItems: 'center',
  },
  stockToggleBtnActive: {
    backgroundColor: '#DCFCE7',
  },
  stockToggleBtnInactive: {
    backgroundColor: '#F3F4F6',
  },
  editBtn: {
    width: 36,
    height: 36,
    backgroundColor: '#EEF2FF',
    borderRadius: 18,
    justifyContent: 'center',
    alignItems: 'center',
  },
  deleteBtn: {
    width: 36,
    height: 36,
    backgroundColor: '#FEE2E2',
    borderRadius: 18,
    justifyContent: 'center',
    alignItems: 'center',
  },
  // Empty State
  emptyState: {
    alignItems: 'center',
    paddingVertical: 60,
    paddingHorizontal: 32,
  },
  emptyIconBg: {
    width: 96,
    height: 96,
    backgroundColor: '#F3F4F6',
    borderRadius: 48,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 20,
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#374151',
    marginBottom: 8,
  },
  emptySubtitle: {
    fontSize: 14,
    color: '#9CA3AF',
    textAlign: 'center',
  },
  emptyAddBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#6366F1',
    paddingHorizontal: 24,
    paddingVertical: 14,
    borderRadius: 14,
    marginTop: 24,
    gap: 8,
  },
  emptyAddBtnText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  // Claymorphism Alert Styles
  alertContainer: {
    position: 'absolute',
    bottom: 100,
    left: 16,
    right: 16,
    alignItems: 'center',
    zIndex: 1000,
  },
  alertBox: {
    width: '100%',
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 4,
    shadowColor: '#6366F1',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.25,
    shadowRadius: 20,
    elevation: 12,
    borderWidth: 2,
    borderColor: 'rgba(99, 102, 241, 0.15)',
  },
  alertBoxSuccess: {
    shadowColor: '#22C55E',
    borderColor: 'rgba(34, 197, 94, 0.2)',
  },
  alertBoxError: {
    shadowColor: '#EF4444',
    borderColor: 'rgba(239, 68, 68, 0.2)',
  },
  alertBoxWarning: {
    shadowColor: '#F59E0B',
    borderColor: 'rgba(245, 158, 11, 0.2)',
  },
  alertInner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 14,
  },
  alertIconBg: {
    width: 48,
    height: 48,
    backgroundColor: '#EEF2FF',
    borderRadius: 14,
    justifyContent: 'center',
    alignItems: 'center',
  },
  alertIconBgSuccess: {
    backgroundColor: '#DCFCE7',
  },
  alertIconBgError: {
    backgroundColor: '#FEE2E2',
  },
  alertIconBgWarning: {
    backgroundColor: '#FEF3C7',
  },
  alertContent: {
    flex: 1,
    marginLeft: 12,
  },
  alertTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#111827',
  },
  alertMessage: {
    fontSize: 13,
    color: '#6B7280',
    marginTop: 2,
  },
  // Confirmation Modal Styles
  modalOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'center',
    alignItems: 'center',
    zIndex: 1000,
  },
  confirmModal: {
    width: width - 48,
    backgroundColor: '#FFFFFF',
    borderRadius: 24,
    padding: 6,
    shadowColor: '#EF4444',
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.3,
    shadowRadius: 24,
    elevation: 15,
    borderWidth: 2,
    borderColor: 'rgba(239, 68, 68, 0.15)',
  },
  confirmModalInner: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 24,
    alignItems: 'center',
  },
  confirmIconBg: {
    width: 72,
    height: 72,
    backgroundColor: '#FEE2E2',
    borderRadius: 22,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
    shadowColor: '#EF4444',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
    elevation: 4,
  },
  confirmTitle: {
    fontSize: 20,
    fontWeight: '800',
    color: '#111827',
    marginBottom: 8,
  },
  confirmMessage: {
    fontSize: 14,
    color: '#6B7280',
    textAlign: 'center',
    marginBottom: 24,
  },
  confirmButtons: {
    flexDirection: 'row',
    gap: 12,
  },
  confirmCancelBtn: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 14,
    backgroundColor: '#F3F4F6',
    alignItems: 'center',
  },
  confirmCancelText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#6B7280',
  },
  confirmDeleteBtn: {
    flex: 1,
    flexDirection: 'row',
    paddingVertical: 14,
    borderRadius: 14,
    backgroundColor: '#EF4444',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
  },
  confirmDeleteText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  // Filter Scroll
  filterScrollContainer: {
    backgroundColor: '#FFFFFF',
  },
  filterWrapper: {
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
});
