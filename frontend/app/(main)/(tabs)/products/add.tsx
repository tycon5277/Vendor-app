import React, { useState, useRef, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  KeyboardAvoidingView,
  Platform,
  Image,
  Animated,
  ActivityIndicator,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import { productAPI } from '../../../../src/utils/api';
import { useAlert } from '../../../../src/context/AlertContext';

const PRODUCT_CATEGORIES = [
  { id: 'Groceries', icon: 'basket', label: 'Groceries' },
  { id: 'Dairy', icon: 'water', label: 'Dairy' },
  { id: 'Beverages', icon: 'cafe', label: 'Beverages' },
  { id: 'Snacks', icon: 'fast-food', label: 'Snacks' },
  { id: 'Bakery', icon: 'pizza', label: 'Bakery' },
  { id: 'Fruits', icon: 'nutrition', label: 'Fruits' },
  { id: 'Vegetables', icon: 'leaf', label: 'Vegetables' },
  { id: 'Meat', icon: 'restaurant', label: 'Meat' },
  { id: 'Seafood', icon: 'fish', label: 'Seafood' },
  { id: 'Frozen', icon: 'snow', label: 'Frozen' },
  { id: 'Other', icon: 'grid', label: 'Other' },
];

const UNITS = [
  { id: 'piece', label: 'Piece' },
  { id: 'kg', label: 'Kilogram (kg)' },
  { id: 'g', label: 'Gram (g)' },
  { id: 'liter', label: 'Liter (L)' },
  { id: 'ml', label: 'Milliliter (ml)' },
  { id: 'pack', label: 'Pack' },
  { id: 'dozen', label: 'Dozen' },
  { id: 'box', label: 'Box' },
];

export default function AddProductScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { showAlert } = useAlert();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const progressAnim = useRef(new Animated.Value(0)).current;

  // Form state
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [price, setPrice] = useState('');
  const [discountedPrice, setDiscountedPrice] = useState('');
  const [category, setCategory] = useState('');
  const [unit, setUnit] = useState('piece');
  const [stockQuantity, setStockQuantity] = useState('100');
  const [image, setImage] = useState<string | null>(null);
  const [inStock, setInStock] = useState(true);

  // Calculate form completion
  useEffect(() => {
    let filled = 0;
    const total = 4; // Required fields: name, price, category, unit
    if (name.trim()) filled++;
    if (price.trim()) filled++;
    if (category) filled++;
    if (unit) filled++;

    Animated.spring(progressAnim, {
      toValue: filled / total,
      useNativeDriver: false,
    }).start();
  }, [name, price, category, unit]);

  const handlePickImage = async () => {
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      showAlert({
        type: 'warning',
        title: 'Permission Required',
        message: 'Please allow access to your photo library',
      });
      return;
    }

    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: true,
      aspect: [1, 1],
      quality: 0.5,
      base64: true,
    });

    if (!result.canceled && result.assets[0].base64) {
      setImage(`data:image/jpeg;base64,${result.assets[0].base64}`);
    }
  };

  const handleTakePhoto = async () => {
    const permission = await ImagePicker.requestCameraPermissionsAsync();
    if (!permission.granted) {
      showAlert({
        type: 'warning',
        title: 'Permission Required',
        message: 'Please allow access to your camera',
      });
      return;
    }

    const result = await ImagePicker.launchCameraAsync({
      allowsEditing: true,
      aspect: [1, 1],
      quality: 0.5,
      base64: true,
    });

    if (!result.canceled && result.assets[0].base64) {
      setImage(`data:image/jpeg;base64,${result.assets[0].base64}`);
    }
  };

  const handleSubmit = async () => {
    // Validation
    if (!name.trim()) {
      showAlert({
        type: 'warning',
        title: 'Required',
        message: 'Please enter product name',
      });
      return;
    }
    if (!price.trim() || isNaN(Number(price))) {
      showAlert({
        type: 'warning',
        title: 'Required',
        message: 'Please enter a valid price',
      });
      return;
    }
    if (!category) {
      showAlert({
        type: 'warning',
        title: 'Required',
        message: 'Please select a category',
      });
      return;
    }

    const priceNum = parseFloat(price);
    const discountNum = discountedPrice ? parseFloat(discountedPrice) : null;

    if (discountNum && discountNum >= priceNum) {
      showAlert({
        type: 'error',
        title: 'Invalid',
        message: 'Discounted price must be less than original price',
      });
      return;
    }

    setIsSubmitting(true);
    try {
      const productData = {
        name: name.trim(),
        description: description.trim() || null,
        price: priceNum,
        discounted_price: discountNum,
        category,
        unit,
        stock_quantity: parseInt(stockQuantity) || 100,
        in_stock: inStock,
        image,
      };

      await productAPI.create(productData);
      
      // Reset form first in case navigation fails
      resetForm();
      
      // Show success message
      showAlert({
        type: 'success',
        title: 'Success! 🎉',
        message: 'Product added successfully',
      });
      
      // Navigate back to products index - use dismissTo to clear stack
      router.dismissTo('/(main)/(tabs)/products');
    } catch (error: any) {
      showAlert({
        type: 'error',
        title: 'Oops!',
        message: error.response?.data?.detail || 'Failed to add product',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const resetForm = () => {
    setName('');
    setDescription('');
    setPrice('');
    setDiscountedPrice('');
    setCategory('');
    setUnit('piece');
    setStockQuantity('100');
    setImage(null);
    setInStock(true);
  };

  const progressWidth = progressAnim.interpolate({
    inputRange: [0, 1],
    outputRange: ['0%', '100%'],
  });

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity
          style={styles.backBtn}
          onPress={() => router.back()}
        >
          <Ionicons name="arrow-back" size={24} color="#374151" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Add Product</Text>
        <View style={styles.headerRight} />
      </View>

      {/* Progress Bar */}
      <View style={styles.progressContainer}>
        <Animated.View style={[styles.progressBar, { width: progressWidth }]} />
      </View>

      <KeyboardAvoidingView
        style={styles.keyboardView}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={100}
      >
        <ScrollView
          style={styles.scrollView}
          showsVerticalScrollIndicator={false}
          contentContainerStyle={styles.scrollContent}
        >
          {/* Image Section */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Product Image</Text>
            <View style={styles.imageContainer}>
              {image ? (
                <View style={styles.imagePreview}>
                  <Image source={{ uri: image }} style={styles.previewImage} />
                  <TouchableOpacity
                    style={styles.removeImageBtn}
                    onPress={() => setImage(null)}
                  >
                    <Ionicons name="close-circle" size={28} color="#EF4444" />
                  </TouchableOpacity>
                </View>
              ) : (
                <View style={styles.imagePlaceholder}>
                  <Ionicons name="image-outline" size={48} color="#D1D5DB" />
                  <Text style={styles.imagePlaceholderText}>Add product photo</Text>
                </View>
              )}
            </View>
            <View style={styles.imageActions}>
              <TouchableOpacity style={styles.imageActionBtn} onPress={handlePickImage}>
                <Ionicons name="images" size={20} color="#6366F1" />
                <Text style={styles.imageActionText}>Gallery</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.imageActionBtn} onPress={handleTakePhoto}>
                <Ionicons name="camera" size={20} color="#6366F1" />
                <Text style={styles.imageActionText}>Camera</Text>
              </TouchableOpacity>
            </View>
          </View>

          {/* Product Name */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Product Name *</Text>
            <TextInput
              style={styles.input}
              value={name}
              onChangeText={setName}
              placeholder="e.g., Organic Basmati Rice (5kg)"
              placeholderTextColor="#9CA3AF"
              maxLength={100}
            />
          </View>

          {/* Description */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Description</Text>
            <TextInput
              style={[styles.input, styles.textArea]}
              value={description}
              onChangeText={setDescription}
              placeholder="Describe your product..."
              placeholderTextColor="#9CA3AF"
              multiline
              numberOfLines={3}
              maxLength={500}
            />
          </View>

          {/* Category */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Category *</Text>
            <View style={styles.categoryGrid}>
              {PRODUCT_CATEGORIES.map((cat) => (
                <TouchableOpacity
                  key={cat.id}
                  style={[
                    styles.categoryItem,
                    category === cat.id && styles.categoryItemActive,
                  ]}
                  onPress={() => setCategory(cat.id)}
                >
                  <Ionicons
                    name={cat.icon as any}
                    size={24}
                    color={category === cat.id ? '#FFFFFF' : '#6B7280'}
                  />
                  <Text
                    style={[
                      styles.categoryLabel,
                      category === cat.id && styles.categoryLabelActive,
                    ]}
                  >
                    {cat.label}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>

          {/* Pricing */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Pricing *</Text>
            <View style={styles.priceRow}>
              <View style={styles.priceInputContainer}>
                <Text style={styles.inputLabel}>Price (₹)</Text>
                <View style={styles.priceInputWrapper}>
                  <Text style={styles.currencySymbol}>₹</Text>
                  <TextInput
                    style={styles.priceInput}
                    value={price}
                    onChangeText={setPrice}
                    placeholder="0.00"
                    placeholderTextColor="#9CA3AF"
                    keyboardType="decimal-pad"
                  />
                </View>
              </View>
              <View style={styles.priceInputContainer}>
                <Text style={styles.inputLabel}>Discounted Price</Text>
                <View style={styles.priceInputWrapper}>
                  <Text style={styles.currencySymbol}>₹</Text>
                  <TextInput
                    style={styles.priceInput}
                    value={discountedPrice}
                    onChangeText={setDiscountedPrice}
                    placeholder="Optional"
                    placeholderTextColor="#9CA3AF"
                    keyboardType="decimal-pad"
                  />
                </View>
              </View>
            </View>
            {discountedPrice && price && parseFloat(discountedPrice) < parseFloat(price) && (
              <View style={styles.discountBadge}>
                <Ionicons name="pricetag" size={14} color="#22C55E" />
                <Text style={styles.discountText}>
                  {Math.round((1 - parseFloat(discountedPrice) / parseFloat(price)) * 100)}% OFF
                </Text>
              </View>
            )}
          </View>

          {/* Unit */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Unit *</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false}>
              <View style={styles.unitRow}>
                {UNITS.map((u) => (
                  <TouchableOpacity
                    key={u.id}
                    style={[
                      styles.unitChip,
                      unit === u.id && styles.unitChipActive,
                    ]}
                    onPress={() => setUnit(u.id)}
                  >
                    <Text
                      style={[
                        styles.unitText,
                        unit === u.id && styles.unitTextActive,
                      ]}
                    >
                      {u.label}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            </ScrollView>
          </View>

          {/* Stock */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Stock</Text>
            <View style={styles.stockRow}>
              <TouchableOpacity
                style={[
                  styles.stockToggle,
                  inStock ? styles.stockToggleActive : styles.stockToggleInactive,
                ]}
                onPress={() => setInStock(!inStock)}
              >
                <Ionicons
                  name={inStock ? 'checkmark-circle' : 'close-circle'}
                  size={20}
                  color={inStock ? '#22C55E' : '#9CA3AF'}
                />
                <Text style={[styles.stockToggleText, inStock && styles.stockToggleTextActive]}>
                  {inStock ? 'In Stock' : 'Out of Stock'}
                </Text>
              </TouchableOpacity>
              <View style={styles.stockQuantityContainer}>
                <Text style={styles.stockLabel}>Quantity</Text>
                <TextInput
                  style={styles.stockInput}
                  value={stockQuantity}
                  onChangeText={setStockQuantity}
                  keyboardType="number-pad"
                  placeholder="100"
                />
              </View>
            </View>
          </View>

          {/* Spacer for button */}
          <View style={{ height: 120 }} />
        </ScrollView>
      </KeyboardAvoidingView>

      {/* Submit Button */}
      <View style={[styles.bottomBar, { paddingBottom: Math.max(insets.bottom, 16) }]}>
        <TouchableOpacity
          style={[
            styles.submitBtn,
            (!name.trim() || !price.trim() || !category) && styles.submitBtnDisabled,
          ]}
          onPress={handleSubmit}
          disabled={isSubmitting || !name.trim() || !price.trim() || !category}
        >
          {isSubmitting ? (
            <ActivityIndicator color="#FFFFFF" />
          ) : (
            <>
              <Ionicons name="add-circle" size={22} color="#FFFFFF" />
              <Text style={styles.submitBtnText}>Add Product</Text>
            </>
          )}
        </TouchableOpacity>
      </View>
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
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  backBtn: {
    width: 44,
    height: 44,
    justifyContent: 'center',
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#111827',
  },
  headerRight: {
    width: 44,
  },
  progressContainer: {
    height: 4,
    backgroundColor: '#E5E7EB',
  },
  progressBar: {
    height: '100%',
    backgroundColor: '#6366F1',
  },
  keyboardView: {
    flex: 1,
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: 16,
    paddingTop: 20,
  },
  section: {
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#374151',
    marginBottom: 10,
  },
  // Image Styles
  imageContainer: {
    alignItems: 'center',
    marginBottom: 12,
  },
  imagePlaceholder: {
    width: 140,
    height: 140,
    borderRadius: 20,
    backgroundColor: '#F3F4F6',
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 2,
    borderColor: '#E5E7EB',
    borderStyle: 'dashed',
  },
  imagePlaceholderText: {
    fontSize: 13,
    color: '#9CA3AF',
    marginTop: 8,
  },
  imagePreview: {
    position: 'relative',
  },
  previewImage: {
    width: 140,
    height: 140,
    borderRadius: 20,
  },
  removeImageBtn: {
    position: 'absolute',
    top: -8,
    right: -8,
    backgroundColor: '#FFFFFF',
    borderRadius: 14,
  },
  imageActions: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 16,
  },
  imageActionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 10,
    backgroundColor: '#EEF2FF',
    borderRadius: 12,
    gap: 8,
  },
  imageActionText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#6366F1',
  },
  // Input Styles
  input: {
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#E5E7EB',
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 14,
    fontSize: 16,
    color: '#111827',
  },
  textArea: {
    minHeight: 80,
    textAlignVertical: 'top',
  },
  inputLabel: {
    fontSize: 12,
    color: '#6B7280',
    marginBottom: 6,
  },
  // Category Grid
  categoryGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  categoryItem: {
    width: '31%',
    aspectRatio: 1.2,
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  categoryItemActive: {
    backgroundColor: '#6366F1',
    borderColor: '#6366F1',
  },
  categoryLabel: {
    fontSize: 11,
    fontWeight: '500',
    color: '#6B7280',
    marginTop: 6,
    textAlign: 'center',
  },
  categoryLabelActive: {
    color: '#FFFFFF',
  },
  // Pricing
  priceRow: {
    flexDirection: 'row',
    gap: 12,
  },
  priceInputContainer: {
    flex: 1,
  },
  priceInputWrapper: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#E5E7EB',
    borderRadius: 12,
    paddingHorizontal: 12,
  },
  currencySymbol: {
    fontSize: 18,
    fontWeight: '600',
    color: '#6B7280',
    marginRight: 4,
  },
  priceInput: {
    flex: 1,
    paddingVertical: 14,
    fontSize: 18,
    fontWeight: '600',
    color: '#111827',
  },
  discountBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    backgroundColor: '#DCFCE7',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
    marginTop: 10,
    gap: 4,
  },
  discountText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#22C55E',
  },
  // Units
  unitRow: {
    flexDirection: 'row',
    gap: 8,
  },
  unitChip: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: '#FFFFFF',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  unitChipActive: {
    backgroundColor: '#6366F1',
    borderColor: '#6366F1',
  },
  unitText: {
    fontSize: 14,
    fontWeight: '500',
    color: '#374151',
  },
  unitTextActive: {
    color: '#FFFFFF',
  },
  // Stock
  stockRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
  },
  stockToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderRadius: 12,
    gap: 8,
  },
  stockToggleActive: {
    backgroundColor: '#DCFCE7',
  },
  stockToggleInactive: {
    backgroundColor: '#F3F4F6',
  },
  stockToggleText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#6B7280',
  },
  stockToggleTextActive: {
    color: '#22C55E',
  },
  stockQuantityContainer: {
    flex: 1,
  },
  stockLabel: {
    fontSize: 12,
    color: '#6B7280',
    marginBottom: 4,
  },
  stockInput: {
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#E5E7EB',
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 10,
    fontSize: 16,
    color: '#111827',
  },
  // Bottom Bar
  bottomBar: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: '#FFFFFF',
    paddingHorizontal: 16,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: '#E5E7EB',
  },
  submitBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#6366F1',
    paddingVertical: 16,
    borderRadius: 14,
    gap: 8,
  },
  submitBtnDisabled: {
    backgroundColor: '#D1D5DB',
  },
  submitBtnText: {
    fontSize: 16,
    fontWeight: '700',
    color: '#FFFFFF',
  },
});
