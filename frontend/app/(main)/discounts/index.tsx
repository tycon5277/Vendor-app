import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  Modal,
  TextInput,
  Switch,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { discountAPI, productAPI } from '../../../src/utils/api';
import { useAlert } from '../../../src/context/AlertContext';

const DISCOUNT_TYPES = [
  { id: 'percentage', label: 'Percentage Off', icon: 'trending-down', symbol: '%' },
  { id: 'flat', label: 'Flat Off', icon: 'cash', symbol: '₹' },
  { id: 'bogo', label: 'Buy X Get Y', icon: 'gift', symbol: 'BOGO' },
];

const TAB_FILTERS = ['active', 'scheduled', 'expired', 'disabled'];

interface Discount {
  discount_id: string;
  name: string;
  type: string;
  value: number;
  coupon_code?: string;
  min_order_value: number;
  max_discount?: number;
  apply_to: string;
  categories: string[];
  product_ids: string[];
  // BOGO specific fields
  bogo_buy_product_id?: string;
  bogo_buy_quantity: number;
  bogo_get_product_id?: string;
  bogo_get_quantity: number;
  validity_type: string;
  start_date?: string;
  end_date?: string;
  usage_limit?: number;
  one_per_customer: boolean;
  usage_count: number;
  status: string;
  created_at: string;
}

interface Product {
  product_id: string;
  name: string;
  price: number;
  unit: string;
}

export default function DiscountsScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { showAlert } = useAlert();
  
  const [discounts, setDiscounts] = useState<Discount[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState('active');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingDiscount, setEditingDiscount] = useState<Discount | null>(null);
  const [saving, setSaving] = useState(false);
  const [products, setProducts] = useState<Product[]>([]);
  
  // Form state
  const [formData, setFormData] = useState({
    name: '',
    type: 'percentage',
    value: 10,
    coupon_code: '',
    min_order_value: 0,
    max_discount: 0,
    apply_to: 'all',
    // BOGO specific fields
    bogo_buy_product_id: '',
    bogo_buy_quantity: 1,
    bogo_get_product_id: '', // empty string means same product
    bogo_get_quantity: 1,
    validity_type: 'always',
    start_date: new Date(),
    end_date: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000),
    usage_limit: 0,
    one_per_customer: false,
  });

  const loadDiscounts = useCallback(async () => {
    try {
      const response = await discountAPI.getAll();
      setDiscounts(response.data.discounts || []);
    } catch (error) {
      console.error('Load discounts error:', error);
    } finally {
      setLoading(false);
    }
  }, []);
  
  const loadProducts = useCallback(async () => {
    try {
      const response = await productAPI.getAll();
      setProducts(response.data || []);
    } catch (error) {
      console.error('Load products error:', error);
    }
  }, []);

  useEffect(() => {
    loadDiscounts();
    loadProducts();
  }, [loadDiscounts, loadProducts]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadDiscounts();
    setRefreshing(false);
  }, [loadDiscounts]);

  const filteredDiscounts = discounts.filter(d => d.status === activeTab);

  const generateCouponCode = () => {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
    let code = '';
    for (let i = 0; i < 8; i++) {
      code += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    setFormData(prev => ({ ...prev, coupon_code: code }));
  };

  const resetForm = () => {
    setFormData({
      name: '',
      type: 'percentage',
      value: 10,
      coupon_code: '',
      min_order_value: 0,
      max_discount: 0,
      apply_to: 'all',
      // BOGO fields
      bogo_buy_product_id: '',
      bogo_buy_quantity: 1,
      bogo_get_product_id: '',
      bogo_get_quantity: 1,
      validity_type: 'always',
      start_date: new Date(),
      end_date: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000),
      usage_limit: 0,
      one_per_customer: false,
    });
    setEditingDiscount(null);
  };

  const openCreateModal = () => {
    resetForm();
    loadProducts(); // Reload products when opening modal
    setShowCreateModal(true);
  };

  const openEditModal = (discount: Discount) => {
    loadProducts(); // Reload products when opening modal
    setEditingDiscount(discount);
    setFormData({
      name: discount.name,
      type: discount.type,
      value: discount.value,
      coupon_code: discount.coupon_code || '',
      min_order_value: discount.min_order_value,
      max_discount: discount.max_discount || 0,
      apply_to: discount.apply_to,
      // BOGO fields
      bogo_buy_product_id: discount.bogo_buy_product_id || '',
      bogo_buy_quantity: discount.bogo_buy_quantity || 1,
      bogo_get_product_id: discount.bogo_get_product_id || '',
      bogo_get_quantity: discount.bogo_get_quantity || 1,
      validity_type: discount.validity_type,
      start_date: discount.start_date ? new Date(discount.start_date) : new Date(),
      end_date: discount.end_date ? new Date(discount.end_date) : new Date(Date.now() + 7 * 24 * 60 * 60 * 1000),
      usage_limit: discount.usage_limit || 0,
      one_per_customer: discount.one_per_customer,
    });
    setShowCreateModal(true);
  };

  const handleSave = async () => {
    if (!formData.name.trim()) {
      showAlert({ type: 'warning', title: 'Required', message: 'Please enter a discount name' });
      return;
    }
    
    // Validate BOGO fields
    if (formData.type === 'bogo' && !formData.bogo_buy_product_id) {
      showAlert({ type: 'warning', title: 'Required', message: 'Please select a product for "Buy" in BOGO offer' });
      return;
    }
    
    setSaving(true);
    try {
      const payload = {
        name: formData.name,
        type: formData.type,
        value: formData.value,
        coupon_code: formData.coupon_code || null,
        min_order_value: formData.min_order_value,
        max_discount: formData.max_discount || null,
        apply_to: formData.apply_to,
        categories: [],
        product_ids: [],
        // BOGO fields
        bogo_buy_product_id: formData.type === 'bogo' ? formData.bogo_buy_product_id : null,
        bogo_buy_quantity: formData.type === 'bogo' ? formData.bogo_buy_quantity : 1,
        bogo_get_product_id: formData.type === 'bogo' ? (formData.bogo_get_product_id || null) : null,
        bogo_get_quantity: formData.type === 'bogo' ? formData.bogo_get_quantity : 1,
        validity_type: formData.validity_type,
        start_date: formData.validity_type === 'date_range' ? formData.start_date.toISOString() : null,
        end_date: formData.validity_type === 'date_range' ? formData.end_date.toISOString() : null,
        usage_limit: formData.usage_limit || null,
        one_per_customer: formData.one_per_customer,
      };
      
      if (editingDiscount) {
        await discountAPI.update(editingDiscount.discount_id, payload);
        showAlert({ type: 'success', title: 'Updated!', message: 'Discount has been updated' });
      } else {
        await discountAPI.create(payload);
        showAlert({ type: 'success', title: 'Created!', message: 'New discount has been created' });
      }
      
      setShowCreateModal(false);
      resetForm();
      loadDiscounts();
    } catch (error: any) {
      console.error('Save discount error:', error);
      showAlert({ type: 'error', title: 'Error', message: error.response?.data?.detail || 'Failed to save discount' });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (discount: Discount) => {
    Alert.alert(
      'Delete Discount',
      `Are you sure you want to delete "${discount.name}"?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              await discountAPI.delete(discount.discount_id);
              showAlert({ type: 'success', title: 'Deleted', message: 'Discount has been deleted' });
              loadDiscounts();
            } catch (error) {
              showAlert({ type: 'error', title: 'Error', message: 'Failed to delete discount' });
            }
          },
        },
      ]
    );
  };

  const handleToggle = async (discount: Discount) => {
    try {
      await discountAPI.toggle(discount.discount_id);
      loadDiscounts();
    } catch (error) {
      showAlert({ type: 'error', title: 'Error', message: 'Failed to toggle discount' });
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
  };

  const getDiscountDisplay = (discount: Discount) => {
    if (discount.type === 'percentage') {
      return `${discount.value}% OFF`;
    } else if (discount.type === 'flat') {
      return `₹${discount.value} OFF`;
    } else {
      return 'BOGO';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return '#22C55E';
      case 'scheduled': return '#F59E0B';
      case 'expired': return '#9CA3AF';
      case 'disabled': return '#EF4444';
      default: return '#6B7280';
    }
  };

  const renderDiscountCard = (discount: Discount) => (
    <TouchableOpacity
      key={discount.discount_id}
      style={styles.discountCard}
      onPress={() => openEditModal(discount)}
      data-testid={`discount-card-${discount.discount_id}`}
    >
      <View style={styles.discountHeader}>
        <View style={[styles.discountBadge, { backgroundColor: discount.type === 'percentage' ? '#EEF2FF' : '#DCFCE7' }]}>
          <Text style={[styles.discountBadgeText, { color: discount.type === 'percentage' ? '#6366F1' : '#22C55E' }]}>
            {getDiscountDisplay(discount)}
          </Text>
        </View>
        <View style={[styles.statusDot, { backgroundColor: getStatusColor(discount.status) }]} />
      </View>
      
      <Text style={styles.discountName}>{discount.name}</Text>
      
      {discount.coupon_code && (
        <View style={styles.couponRow}>
          <Ionicons name="ticket" size={14} color="#6366F1" />
          <Text style={styles.couponCode}>{discount.coupon_code}</Text>
        </View>
      )}
      
      <View style={styles.discountMeta}>
        {discount.validity_type === 'date_range' && discount.end_date && (
          <View style={styles.metaItem}>
            <Ionicons name="time" size={14} color="#6B7280" />
            <Text style={styles.metaText}>
              {discount.status === 'scheduled' ? `Starts ${formatDate(discount.start_date!)}` : `Ends ${formatDate(discount.end_date)}`}
            </Text>
          </View>
        )}
        {discount.validity_type === 'always' && (
          <View style={styles.metaItem}>
            <Ionicons name="infinite" size={14} color="#6B7280" />
            <Text style={styles.metaText}>Always Active</Text>
          </View>
        )}
        <View style={styles.metaItem}>
          <Ionicons name="bar-chart" size={14} color="#6B7280" />
          <Text style={styles.metaText}>Used: {discount.usage_count} times</Text>
        </View>
      </View>
      
      <View style={styles.discountActions}>
        <TouchableOpacity 
          style={styles.actionBtn}
          onPress={() => handleToggle(discount)}
        >
          <Ionicons name={discount.status === 'active' ? 'pause-circle' : 'play-circle'} size={20} color="#6366F1" />
        </TouchableOpacity>
        <TouchableOpacity 
          style={styles.actionBtn}
          onPress={() => handleDelete(discount)}
        >
          <Ionicons name="trash" size={20} color="#EF4444" />
        </TouchableOpacity>
      </View>
    </TouchableOpacity>
  );

  if (loading) {
    return (
      <View style={[styles.container, styles.centered, { paddingTop: insets.top }]}>
        <ActivityIndicator size="large" color="#6366F1" />
      </View>
    );
  }

  return (
    <View style={[styles.container, { paddingTop: insets.top }]} data-testid="discount-list-screen">
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.backBtn} onPress={() => router.back()}>
          <Ionicons name="arrow-back" size={24} color="#374151" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Discounts</Text>
        <TouchableOpacity 
          style={styles.addBtn} 
          onPress={openCreateModal}
          data-testid="discount-add-btn"
        >
          <Ionicons name="add" size={24} color="#FFFFFF" />
        </TouchableOpacity>
      </View>

      {/* Tabs */}
      <View style={styles.tabsContainer}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.tabs}>
          {TAB_FILTERS.map(tab => (
            <TouchableOpacity
              key={tab}
              style={[styles.tab, activeTab === tab && styles.tabActive]}
              onPress={() => setActiveTab(tab)}
              data-testid={`discount-tab-${tab}`}
            >
              <View style={[styles.tabDot, { backgroundColor: getStatusColor(tab) }]} />
              <Text style={[styles.tabText, activeTab === tab && styles.tabTextActive]}>
                {tab.charAt(0).toUpperCase() + tab.slice(1)}
              </Text>
              <Text style={styles.tabCount}>
                {discounts.filter(d => d.status === tab).length}
              </Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>

      {/* Discounts List */}
      <ScrollView
        style={styles.scrollView}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={['#6366F1']} />}
        showsVerticalScrollIndicator={false}
      >
        {filteredDiscounts.length === 0 ? (
          <View style={styles.emptyState}>
            <View style={styles.emptyIcon}>
              <Ionicons name="pricetag-outline" size={48} color="#D1D5DB" />
            </View>
            <Text style={styles.emptyTitle}>No {activeTab} discounts</Text>
            <Text style={styles.emptyText}>Create a discount to attract more customers</Text>
            <TouchableOpacity style={styles.emptyBtn} onPress={openCreateModal}>
              <Ionicons name="add" size={20} color="#FFFFFF" />
              <Text style={styles.emptyBtnText}>Create Discount</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <View style={styles.discountsList}>
            {filteredDiscounts.map(renderDiscountCard)}
          </View>
        )}
        <View style={{ height: 100 }} />
      </ScrollView>

      {/* Create/Edit Modal */}
      <Modal
        visible={showCreateModal}
        animationType="slide"
        onRequestClose={() => setShowCreateModal(false)}
      >
        <View style={[styles.modalContainer, { paddingTop: insets.top }]}>
          <View style={styles.modalHeader}>
            <TouchableOpacity onPress={() => setShowCreateModal(false)}>
              <Ionicons name="close" size={24} color="#374151" />
            </TouchableOpacity>
            <Text style={styles.modalTitle}>{editingDiscount ? 'Edit Discount' : 'Create Discount'}</Text>
            <View style={{ width: 24 }} />
          </View>

          <ScrollView style={styles.modalContent} showsVerticalScrollIndicator={false}>
            {/* Discount Type */}
            <Text style={styles.sectionTitle}>Discount Type</Text>
            <View style={styles.typeGrid}>
              {DISCOUNT_TYPES.map(type => (
                <TouchableOpacity
                  key={type.id}
                  style={[styles.typeCard, formData.type === type.id && styles.typeCardActive]}
                  onPress={() => setFormData(prev => ({ ...prev, type: type.id }))}
                  data-testid={`discount-type-${type.id}`}
                >
                  <View style={[styles.typeIcon, formData.type === type.id && styles.typeIconActive]}>
                    <Text style={[styles.typeSymbol, formData.type === type.id && styles.typeSymbolActive]}>
                      {type.symbol}
                    </Text>
                  </View>
                  <Text style={[styles.typeLabel, formData.type === type.id && styles.typeLabelActive]}>
                    {type.label}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            {/* Discount Name */}
            <Text style={styles.sectionTitle}>Discount Name</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g., Summer Sale 2026"
              placeholderTextColor="#9CA3AF"
              value={formData.name}
              onChangeText={(text) => setFormData(prev => ({ ...prev, name: text }))}
              data-testid="discount-name-input"
            />

            {/* Discount Value - Different UI for BOGO */}
            {formData.type !== 'bogo' ? (
              <>
                <Text style={styles.sectionTitle}>
                  {formData.type === 'percentage' ? 'Discount Percentage' : 'Discount Amount'}
                </Text>
                <View style={styles.valueRow}>
                  <TextInput
                    style={[styles.input, styles.valueInput]}
                    placeholder={formData.type === 'percentage' ? '10' : '50'}
                    placeholderTextColor="#9CA3AF"
                    keyboardType="numeric"
                    value={formData.value.toString()}
                    onChangeText={(text) => setFormData(prev => ({ ...prev, value: parseInt(text) || 0 }))}
                  />
                  <Text style={styles.valueUnit}>
                    {formData.type === 'percentage' ? '%' : '₹'}
                  </Text>
                </View>
              </>
            ) : (
              <>
                {/* BOGO Section */}
                <View style={styles.bogoSection}>
                  {/* BUY Section */}
                  <View style={styles.bogoCard}>
                    <View style={styles.bogoHeader}>
                      <View style={[styles.bogoLabel, { backgroundColor: '#EEF2FF' }]}>
                        <Text style={[styles.bogoLabelText, { color: '#6366F1' }]}>BUY</Text>
                      </View>
                    </View>
                    
                    <Text style={styles.bogoFieldLabel}>Select Product</Text>
                    <ScrollView 
                      horizontal 
                      showsHorizontalScrollIndicator={false}
                      style={styles.productScroll}
                    >
                      {products.length === 0 ? (
                        <Text style={styles.noProductsText}>No products available. Add products first.</Text>
                      ) : (
                        products.map(product => (
                          <TouchableOpacity
                            key={product.product_id}
                            style={[
                              styles.productChip,
                              formData.bogo_buy_product_id === product.product_id && styles.productChipActive
                            ]}
                            onPress={() => setFormData(prev => ({ ...prev, bogo_buy_product_id: product.product_id }))}
                          >
                            <Text style={[
                              styles.productChipText,
                              formData.bogo_buy_product_id === product.product_id && styles.productChipTextActive
                            ]}>
                              {product.name}
                            </Text>
                            <Text style={styles.productChipPrice}>₹{product.price}/{product.unit}</Text>
                          </TouchableOpacity>
                        ))
                      )}
                    </ScrollView>
                    
                    <Text style={styles.bogoFieldLabel}>Quantity</Text>
                    <View style={styles.quantityRow}>
                      <TouchableOpacity
                        style={styles.quantityBtn}
                        onPress={() => setFormData(prev => ({ ...prev, bogo_buy_quantity: Math.max(1, prev.bogo_buy_quantity - 1) }))}
                      >
                        <Ionicons name="remove" size={20} color="#6366F1" />
                      </TouchableOpacity>
                      <Text style={styles.quantityValue}>{formData.bogo_buy_quantity}</Text>
                      <TouchableOpacity
                        style={styles.quantityBtn}
                        onPress={() => setFormData(prev => ({ ...prev, bogo_buy_quantity: prev.bogo_buy_quantity + 1 }))}
                      >
                        <Ionicons name="add" size={20} color="#6366F1" />
                      </TouchableOpacity>
                    </View>
                  </View>

                  {/* Arrow */}
                  <View style={styles.bogoArrow}>
                    <Ionicons name="arrow-down" size={24} color="#6366F1" />
                  </View>

                  {/* GET Section */}
                  <View style={styles.bogoCard}>
                    <View style={styles.bogoHeader}>
                      <View style={[styles.bogoLabel, { backgroundColor: '#DCFCE7' }]}>
                        <Text style={[styles.bogoLabelText, { color: '#22C55E' }]}>GET FREE</Text>
                      </View>
                    </View>
                    
                    <Text style={styles.bogoFieldLabel}>Select Product</Text>
                    <ScrollView 
                      horizontal 
                      showsHorizontalScrollIndicator={false}
                      style={styles.productScroll}
                    >
                      <TouchableOpacity
                        style={[
                          styles.productChip,
                          formData.bogo_get_product_id === '' && styles.productChipActive
                        ]}
                        onPress={() => setFormData(prev => ({ ...prev, bogo_get_product_id: '' }))}
                      >
                        <Text style={[
                          styles.productChipText,
                          formData.bogo_get_product_id === '' && styles.productChipTextActive
                        ]}>
                          Same Product
                        </Text>
                      </TouchableOpacity>
                      {products.map(product => (
                        <TouchableOpacity
                          key={product.product_id}
                          style={[
                            styles.productChip,
                            formData.bogo_get_product_id === product.product_id && styles.productChipActive
                          ]}
                          onPress={() => setFormData(prev => ({ ...prev, bogo_get_product_id: product.product_id }))}
                        >
                          <Text style={[
                            styles.productChipText,
                            formData.bogo_get_product_id === product.product_id && styles.productChipTextActive
                          ]}>
                            {product.name}
                          </Text>
                          <Text style={styles.productChipPrice}>₹{product.price}/{product.unit}</Text>
                        </TouchableOpacity>
                      ))}
                    </ScrollView>
                    
                    <Text style={styles.bogoFieldLabel}>Quantity (Free)</Text>
                    <View style={styles.quantityRow}>
                      <TouchableOpacity
                        style={styles.quantityBtn}
                        onPress={() => setFormData(prev => ({ ...prev, bogo_get_quantity: Math.max(1, prev.bogo_get_quantity - 1) }))}
                      >
                        <Ionicons name="remove" size={20} color="#22C55E" />
                      </TouchableOpacity>
                      <Text style={styles.quantityValue}>{formData.bogo_get_quantity}</Text>
                      <TouchableOpacity
                        style={styles.quantityBtn}
                        onPress={() => setFormData(prev => ({ ...prev, bogo_get_quantity: prev.bogo_get_quantity + 1 }))}
                      >
                        <Ionicons name="add" size={20} color="#22C55E" />
                      </TouchableOpacity>
                    </View>
                  </View>

                  {/* BOGO Summary */}
                  {formData.bogo_buy_product_id && (
                    <View style={styles.bogoSummary}>
                      <Ionicons name="gift" size={20} color="#6366F1" />
                      <Text style={styles.bogoSummaryText}>
                        Buy {formData.bogo_buy_quantity} {products.find(p => p.product_id === formData.bogo_buy_product_id)?.name || 'product'} → Get {formData.bogo_get_quantity} {formData.bogo_get_product_id ? products.find(p => p.product_id === formData.bogo_get_product_id)?.name : 'same product'} FREE
                      </Text>
                    </View>
                  )}
                </View>
              </>
            )}

            {/* Coupon Code */}
            <Text style={styles.sectionTitle}>Coupon Code (Optional)</Text>
            <View style={styles.couponInputRow}>
              <TextInput
                style={[styles.input, { flex: 1 }]}
                placeholder="SUMMER20"
                placeholderTextColor="#9CA3AF"
                value={formData.coupon_code}
                onChangeText={(text) => setFormData(prev => ({ ...prev, coupon_code: text.toUpperCase() }))}
                autoCapitalize="characters"
                data-testid="discount-code-input"
              />
              <TouchableOpacity style={styles.generateBtn} onPress={generateCouponCode} data-testid="discount-generate-code-btn">
                <Ionicons name="refresh" size={20} color="#6366F1" />
              </TouchableOpacity>
            </View>

            {/* Minimum Order */}
            <Text style={styles.sectionTitle}>Minimum Order Value</Text>
            <View style={styles.valueRow}>
              <Text style={styles.currencyPrefix}>₹</Text>
              <TextInput
                style={[styles.input, { flex: 1 }]}
                placeholder="0 (No minimum)"
                placeholderTextColor="#9CA3AF"
                keyboardType="numeric"
                value={formData.min_order_value > 0 ? formData.min_order_value.toString() : ''}
                onChangeText={(text) => setFormData(prev => ({ ...prev, min_order_value: parseInt(text) || 0 }))}
              />
            </View>

            {/* Max Discount (for percentage) */}
            {formData.type === 'percentage' && (
              <>
                <Text style={styles.sectionTitle}>Maximum Discount Cap (Optional)</Text>
                <View style={styles.valueRow}>
                  <Text style={styles.currencyPrefix}>₹</Text>
                  <TextInput
                    style={[styles.input, { flex: 1 }]}
                    placeholder="No cap"
                    placeholderTextColor="#9CA3AF"
                    keyboardType="numeric"
                    value={formData.max_discount > 0 ? formData.max_discount.toString() : ''}
                    onChangeText={(text) => setFormData(prev => ({ ...prev, max_discount: parseInt(text) || 0 }))}
                  />
                </View>
              </>
            )}

            {/* Validity */}
            <Text style={styles.sectionTitle}>Validity</Text>
            <View style={styles.validityRow}>
              <TouchableOpacity
                style={[styles.validityOption, formData.validity_type === 'always' && styles.validityOptionActive]}
                onPress={() => setFormData(prev => ({ ...prev, validity_type: 'always' }))}
              >
                <Ionicons 
                  name={formData.validity_type === 'always' ? 'radio-button-on' : 'radio-button-off'} 
                  size={20} 
                  color={formData.validity_type === 'always' ? '#6366F1' : '#9CA3AF'} 
                />
                <Text style={[styles.validityText, formData.validity_type === 'always' && styles.validityTextActive]}>
                  Always Active
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.validityOption, formData.validity_type === 'date_range' && styles.validityOptionActive]}
                onPress={() => setFormData(prev => ({ ...prev, validity_type: 'date_range' }))}
              >
                <Ionicons 
                  name={formData.validity_type === 'date_range' ? 'radio-button-on' : 'radio-button-off'} 
                  size={20} 
                  color={formData.validity_type === 'date_range' ? '#6366F1' : '#9CA3AF'} 
                />
                <Text style={[styles.validityText, formData.validity_type === 'date_range' && styles.validityTextActive]}>
                  Date Range
                </Text>
              </TouchableOpacity>
            </View>

            {formData.validity_type === 'date_range' && (
              <View style={styles.dateRow}>
                <View style={styles.dateInputContainer}>
                  <Ionicons name="calendar" size={18} color="#6366F1" />
                  <TextInput
                    style={styles.dateInput}
                    placeholder="YYYY-MM-DD"
                    placeholderTextColor="#9CA3AF"
                    value={formData.start_date.toISOString().split('T')[0]}
                    onChangeText={(text) => {
                      const date = new Date(text);
                      if (!isNaN(date.getTime())) {
                        setFormData(prev => ({ ...prev, start_date: date }));
                      }
                    }}
                  />
                </View>
                <Text style={styles.dateSeparator}>to</Text>
                <View style={styles.dateInputContainer}>
                  <Ionicons name="calendar" size={18} color="#6366F1" />
                  <TextInput
                    style={styles.dateInput}
                    placeholder="YYYY-MM-DD"
                    placeholderTextColor="#9CA3AF"
                    value={formData.end_date.toISOString().split('T')[0]}
                    onChangeText={(text) => {
                      const date = new Date(text);
                      if (!isNaN(date.getTime())) {
                        setFormData(prev => ({ ...prev, end_date: date }));
                      }
                    }}
                  />
                </View>
              </View>
            )}

            {/* Usage Limit */}
            <Text style={styles.sectionTitle}>Usage Limit</Text>
            <TextInput
              style={styles.input}
              placeholder="0 (Unlimited)"
              placeholderTextColor="#9CA3AF"
              keyboardType="numeric"
              value={formData.usage_limit > 0 ? formData.usage_limit.toString() : ''}
              onChangeText={(text) => setFormData(prev => ({ ...prev, usage_limit: parseInt(text) || 0 }))}
            />

            {/* One per customer */}
            <View style={styles.switchRow}>
              <View>
                <Text style={styles.switchLabel}>One per customer</Text>
                <Text style={styles.switchHint}>Each customer can use this discount only once</Text>
              </View>
              <Switch
                value={formData.one_per_customer}
                onValueChange={(value) => setFormData(prev => ({ ...prev, one_per_customer: value }))}
                trackColor={{ false: '#E5E7EB', true: '#A5B4FC' }}
                thumbColor={formData.one_per_customer ? '#6366F1' : '#9CA3AF'}
              />
            </View>

            {/* Save Button */}
            <TouchableOpacity
              style={[styles.saveBtn, saving && styles.saveBtnDisabled]}
              onPress={handleSave}
              disabled={saving}
              data-testid="discount-save-btn"
            >
              {saving ? (
                <ActivityIndicator color="#FFFFFF" />
              ) : (
                <>
                  <Ionicons name="checkmark" size={20} color="#FFFFFF" />
                  <Text style={styles.saveBtnText}>
                    {editingDiscount ? 'Update Discount' : 'Create Discount'}
                  </Text>
                </>
              )}
            </TouchableOpacity>

            <View style={{ height: 40 }} />
          </ScrollView>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F8FAFC',
  },
  centered: {
    justifyContent: 'center',
    alignItems: 'center',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
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
  headerTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#111827',
  },
  addBtn: {
    width: 40,
    height: 40,
    backgroundColor: '#6366F1',
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
  },
  tabsContainer: {
    backgroundColor: '#FFFFFF',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  tabs: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    gap: 8,
  },
  tab: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingVertical: 8,
    backgroundColor: '#F3F4F6',
    borderRadius: 20,
    gap: 6,
  },
  tabActive: {
    backgroundColor: '#EEF2FF',
  },
  tabDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  tabText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#6B7280',
  },
  tabTextActive: {
    color: '#6366F1',
  },
  tabCount: {
    fontSize: 12,
    fontWeight: '700',
    color: '#9CA3AF',
    backgroundColor: '#FFFFFF',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 8,
  },
  scrollView: {
    flex: 1,
  },
  discountsList: {
    padding: 16,
    gap: 12,
  },
  discountCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  discountHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  discountBadge: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
  },
  discountBadgeText: {
    fontSize: 14,
    fontWeight: '800',
  },
  statusDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  discountName: {
    fontSize: 16,
    fontWeight: '700',
    color: '#111827',
    marginBottom: 8,
  },
  couponRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 8,
  },
  couponCode: {
    fontSize: 13,
    fontWeight: '600',
    color: '#6366F1',
    letterSpacing: 1,
  },
  discountMeta: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    marginBottom: 12,
  },
  metaItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  metaText: {
    fontSize: 12,
    color: '#6B7280',
  },
  discountActions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 12,
    borderTopWidth: 1,
    borderTopColor: '#F3F4F6',
    paddingTop: 12,
  },
  actionBtn: {
    padding: 8,
  },
  emptyState: {
    alignItems: 'center',
    paddingVertical: 60,
    paddingHorizontal: 40,
  },
  emptyIcon: {
    width: 100,
    height: 100,
    backgroundColor: '#F3F4F6',
    borderRadius: 50,
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
  emptyText: {
    fontSize: 14,
    color: '#6B7280',
    textAlign: 'center',
    marginBottom: 24,
  },
  emptyBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#6366F1',
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 12,
    gap: 8,
  },
  emptyBtnText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  // Modal styles
  modalContainer: {
    flex: 1,
    backgroundColor: '#F8FAFC',
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 14,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#111827',
  },
  modalContent: {
    flex: 1,
    padding: 16,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#374151',
    marginBottom: 10,
    marginTop: 16,
  },
  typeGrid: {
    flexDirection: 'row',
    gap: 10,
  },
  typeCard: {
    flex: 1,
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 14,
    padding: 14,
    borderWidth: 2,
    borderColor: '#E5E7EB',
  },
  typeCardActive: {
    borderColor: '#6366F1',
    backgroundColor: '#EEF2FF',
  },
  typeIcon: {
    width: 48,
    height: 48,
    backgroundColor: '#F3F4F6',
    borderRadius: 14,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 8,
  },
  typeIconActive: {
    backgroundColor: '#6366F1',
  },
  typeSymbol: {
    fontSize: 16,
    fontWeight: '800',
    color: '#6B7280',
  },
  typeSymbolActive: {
    color: '#FFFFFF',
  },
  typeLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: '#6B7280',
    textAlign: 'center',
  },
  typeLabelActive: {
    color: '#6366F1',
  },
  input: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#E5E7EB',
    paddingHorizontal: 14,
    paddingVertical: 14,
    fontSize: 16,
    color: '#111827',
  },
  valueRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  valueInput: {
    flex: 1,
  },
  valueUnit: {
    fontSize: 18,
    fontWeight: '700',
    color: '#6366F1',
    marginLeft: 10,
  },
  currencyPrefix: {
    fontSize: 18,
    fontWeight: '600',
    color: '#6B7280',
    marginRight: 8,
  },
  couponInputRow: {
    flexDirection: 'row',
    gap: 10,
  },
  generateBtn: {
    width: 52,
    backgroundColor: '#EEF2FF',
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
  },
  validityRow: {
    flexDirection: 'row',
    gap: 12,
  },
  validityOption: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    padding: 14,
    borderWidth: 1,
    borderColor: '#E5E7EB',
    gap: 8,
  },
  validityOptionActive: {
    borderColor: '#6366F1',
    backgroundColor: '#EEF2FF',
  },
  validityText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#6B7280',
  },
  validityTextActive: {
    color: '#6366F1',
  },
  dateRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 12,
    gap: 10,
  },
  dateBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    padding: 14,
    borderWidth: 1,
    borderColor: '#E5E7EB',
    gap: 10,
  },
  dateInputContainer: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    padding: 10,
    borderWidth: 1,
    borderColor: '#E5E7EB',
    gap: 8,
  },
  dateInput: {
    flex: 1,
    fontSize: 14,
    fontWeight: '600',
    color: '#374151',
    padding: 4,
  },
  dateText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#374151',
  },
  dateSeparator: {
    fontSize: 14,
    color: '#9CA3AF',
  },
  switchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    padding: 14,
    marginTop: 16,
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  switchLabel: {
    fontSize: 15,
    fontWeight: '600',
    color: '#111827',
  },
  switchHint: {
    fontSize: 12,
    color: '#6B7280',
    marginTop: 2,
  },
  saveBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#6366F1',
    borderRadius: 14,
    paddingVertical: 16,
    marginTop: 24,
    gap: 8,
  },
  saveBtnDisabled: {
    backgroundColor: '#A5B4FC',
  },
  saveBtnText: {
    fontSize: 16,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  // BOGO Styles
  bogoSection: {
    marginTop: 8,
  },
  bogoCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: '#E5E7EB',
    marginBottom: 8,
  },
  bogoHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  bogoLabel: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
  },
  bogoLabelText: {
    fontSize: 12,
    fontWeight: '800',
    letterSpacing: 1,
  },
  bogoFieldLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: '#374151',
    marginBottom: 8,
    marginTop: 8,
  },
  productScroll: {
    flexGrow: 0,
    marginBottom: 8,
  },
  productChip: {
    backgroundColor: '#F3F4F6',
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 10,
    marginRight: 8,
    borderWidth: 2,
    borderColor: '#F3F4F6',
  },
  productChipActive: {
    backgroundColor: '#EEF2FF',
    borderColor: '#6366F1',
  },
  productChipText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#6B7280',
  },
  productChipTextActive: {
    color: '#6366F1',
  },
  productChipPrice: {
    fontSize: 11,
    color: '#9CA3AF',
    marginTop: 2,
  },
  noProductsText: {
    fontSize: 13,
    color: '#9CA3AF',
    fontStyle: 'italic',
  },
  quantityRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 16,
    marginTop: 4,
  },
  quantityBtn: {
    width: 40,
    height: 40,
    backgroundColor: '#EEF2FF',
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
  },
  quantityValue: {
    fontSize: 24,
    fontWeight: '700',
    color: '#111827',
    minWidth: 40,
    textAlign: 'center',
  },
  bogoArrow: {
    alignItems: 'center',
    paddingVertical: 4,
  },
  bogoSummary: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#EEF2FF',
    borderRadius: 12,
    padding: 14,
    marginTop: 8,
    gap: 10,
  },
  bogoSummaryText: {
    flex: 1,
    fontSize: 14,
    fontWeight: '600',
    color: '#6366F1',
  },
});
