import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  Image,
  Alert,
  Animated,
  TextInput,
  Dimensions,
  BackHandler,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { productAPI } from '../../src/utils/api';
import { Product } from '../../src/types';

const { width } = Dimensions.get('window');

const PRODUCT_CATEGORIES = [
  'All', 'Groceries', 'Dairy', 'Beverages', 'Snacks', 'Bakery',
  'Fruits', 'Vegetables', 'Meat', 'Seafood', 'Frozen', 'Other'
];

type FilterType = 'all' | 'in_stock' | 'low_stock' | 'out_of_stock';

export default function WarehouseScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [products, setProducts] = useState<Product[]>([]);
  const [filteredProducts, setFilteredProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [selectedFilter, setSelectedFilter] = useState<FilterType>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const fadeAnim = useRef(new Animated.Value(0)).current;

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

    // Stock filter
    switch (filter) {
      case 'in_stock':
        filtered = filtered.filter(p => p.in_stock && p.stock_quantity > 10);
        break;
      case 'low_stock':
        filtered = filtered.filter(p => p.in_stock && p.stock_quantity <= 10);
        break;
      case 'out_of_stock':
        filtered = filtered.filter(p => !p.in_stock);
        break;
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

  useEffect(() => {
    loadProducts();
    Animated.timing(fadeAnim, {
      toValue: 1,
      duration: 400,
      useNativeDriver: true,
    }).start();
  }, []);

  // Handle hardware back button - go to previous screen
  useEffect(() => {
    const backHandler = BackHandler.addEventListener('hardwareBackPress', () => {
      router.back();
      return true;
    });
    return () => backHandler.remove();
  }, []);

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
    } catch (error) {
      Alert.alert('Error', 'Failed to update stock');
    }
  };

  const handleDeleteProduct = (product: Product) => {
    Alert.alert(
      'Delete Product',
      `Remove "${product.name}" from your warehouse?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              await productAPI.delete(product.product_id);
              setProducts(products.filter(p => p.product_id !== product.product_id));
              loadProducts();
            } catch (error) {
              Alert.alert('Error', 'Failed to delete product');
            }
          },
        },
      ]
    );
  };

  // Stats
  const stats = {
    total: products.length,
    inStock: products.filter(p => p.in_stock && p.stock_quantity > 10).length,
    lowStock: products.filter(p => p.in_stock && p.stock_quantity <= 10).length,
    outOfStock: products.filter(p => !p.in_stock).length,
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
        onPress={() => router.push(`/(main)/products/${item.product_id}`)}
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
            onPress={() => router.push(`/(main)/products/${item.product_id}`)}
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
          onPress={() => router.push('/(main)/products/add')}
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

      {/* Filter Tabs */}
      <View style={styles.filterContainer}>
        {filters.map((filter) => (
          <TouchableOpacity
            key={filter.key}
            style={[
              styles.filterTab,
              selectedFilter === filter.key && { backgroundColor: filter.color + '15', borderColor: filter.color },
            ]}
            onPress={() => setSelectedFilter(filter.key)}
          >
            <Text style={[
              styles.filterTabText,
              selectedFilter === filter.key && { color: filter.color, fontWeight: '700' },
            ]}>
              {filter.label}
            </Text>
            <View style={[
              styles.filterBadge,
              { backgroundColor: selectedFilter === filter.key ? filter.color : '#E5E7EB' },
            ]}>
              <Text style={[
                styles.filterBadgeText,
                { color: selectedFilter === filter.key ? '#FFFFFF' : '#6B7280' },
              ]}>
                {filter.count}
              </Text>
            </View>
          </TouchableOpacity>
        ))}
      </View>

      {/* Category Scroll */}
      <FlatList
        horizontal
        data={PRODUCT_CATEGORIES}
        keyExtractor={(item) => item}
        showsHorizontalScrollIndicator={false}
        style={styles.categoryScroll}
        contentContainerStyle={styles.categoryContainer}
        renderItem={({ item }) => (
          <TouchableOpacity
            style={[
              styles.categoryChip,
              selectedCategory === item && styles.categoryChipActive,
            ]}
            onPress={() => setSelectedCategory(item)}
          >
            <Text style={[
              styles.categoryText,
              selectedCategory === item && styles.categoryTextActive,
            ]}>
              {item}
            </Text>
          </TouchableOpacity>
        )}
      />

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
                onPress={() => router.push('/(main)/products/add')}
              >
                <Ionicons name="add-circle" size={20} color="#FFFFFF" />
                <Text style={styles.emptyAddBtnText}>Add Product</Text>
              </TouchableOpacity>
            )}
          </View>
        }
      />
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
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
    gap: 8,
  },
  filterTab: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#E5E7EB',
    gap: 6,
  },
  filterTabText: {
    fontSize: 13,
    color: '#6B7280',
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
  // Category
  categoryScroll: {
    maxHeight: 50,
    backgroundColor: '#FFFFFF',
  },
  categoryContainer: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    gap: 8,
  },
  categoryChip: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    backgroundColor: '#F3F4F6',
    borderRadius: 20,
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
});
