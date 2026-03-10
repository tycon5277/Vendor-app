import React, { useState, useEffect, useRef } from 'react';
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
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import { productAPI } from '../../../src/utils/api';
import { useAlert } from '../../../src/context/AlertContext';
import { useToastStore } from '../../../src/store/toastStore';
import { useTheme } from '../../../src/context/ThemeContext';

// Same categories as add.tsx for consistency
const PRODUCT_CATEGORIES = [
  { id: 'groceries', icon: 'basket', label: 'Groceries', subcategories: [
    { id: 'rice_grains', label: 'Rice & Grains' }, { id: 'flour_baking', label: 'Flour & Baking' },
    { id: 'pasta_noodles', label: 'Pasta & Noodles' }, { id: 'oils_ghee', label: 'Oils & Ghee' },
    { id: 'spices_masala', label: 'Spices & Masala' }, { id: 'pulses_lentils', label: 'Pulses & Lentils' },
    { id: 'sugar_salt', label: 'Sugar & Salt' }, { id: 'pickles_chutneys', label: 'Pickles & Chutneys' },
    { id: 'ready_to_cook', label: 'Ready to Cook' }, { id: 'canned_jarred', label: 'Canned & Jarred' },
  ]},
  { id: 'beverages', icon: 'cafe', label: 'Beverages', subcategories: [
    { id: 'tea', label: 'Tea' }, { id: 'coffee', label: 'Coffee' }, { id: 'soft_drinks', label: 'Soft Drinks' },
    { id: 'juices', label: 'Juices' }, { id: 'energy_drinks', label: 'Energy Drinks' },
    { id: 'water', label: 'Water' }, { id: 'health_drinks', label: 'Health Drinks' },
  ]},
  { id: 'dairy', icon: 'ellipse', label: 'Dairy & Eggs', subcategories: [
    { id: 'milk', label: 'Milk' }, { id: 'curd_yogurt', label: 'Curd & Yogurt' }, { id: 'cheese', label: 'Cheese' },
    { id: 'butter_ghee', label: 'Butter & Ghee' }, { id: 'paneer_tofu', label: 'Paneer & Tofu' },
    { id: 'eggs', label: 'Eggs' }, { id: 'cream', label: 'Cream' },
  ]},
  { id: 'fruits', icon: 'nutrition', label: 'Fruits', subcategories: [
    { id: 'fresh_seasonal', label: 'Fresh Seasonal' }, { id: 'exotic_imported', label: 'Exotic' },
    { id: 'citrus', label: 'Citrus' }, { id: 'dry_fruits', label: 'Dry Fruits' },
  ]},
  { id: 'vegetables', icon: 'leaf', label: 'Vegetables', subcategories: [
    { id: 'fresh_daily', label: 'Fresh Daily' }, { id: 'leafy_greens', label: 'Leafy Greens' },
    { id: 'root_tubers', label: 'Root & Tubers' }, { id: 'exotic_veggies', label: 'Exotic' },
  ]},
  { id: 'meat', icon: 'restaurant', label: 'Meat & Poultry', subcategories: [
    { id: 'chicken', label: 'Chicken' }, { id: 'mutton', label: 'Mutton' }, { id: 'beef', label: 'Beef' },
    { id: 'marinated', label: 'Marinated' }, { id: 'sausages_cold_cuts', label: 'Sausages' },
  ]},
  { id: 'seafood', icon: 'fish', label: 'Seafood', subcategories: [
    { id: 'fish_fresh', label: 'Fresh Fish' }, { id: 'prawns_shrimp', label: 'Prawns' },
    { id: 'crabs_lobster', label: 'Crabs' }, { id: 'dried_seafood', label: 'Dried Seafood' },
  ]},
  { id: 'frozen', icon: 'snow', label: 'Frozen Foods', subcategories: [
    { id: 'frozen_veggies', label: 'Frozen Veggies' }, { id: 'frozen_meat', label: 'Frozen Meat' },
    { id: 'ice_cream', label: 'Ice Cream' }, { id: 'frozen_snacks', label: 'Frozen Snacks' },
  ]},
  { id: 'bakery', icon: 'pizza', label: 'Bakery', subcategories: [
    { id: 'breads', label: 'Breads' }, { id: 'cakes_pastries', label: 'Cakes' },
    { id: 'cookies_biscuits', label: 'Cookies' },
  ]},
  { id: 'snacks', icon: 'fast-food', label: 'Snacks', subcategories: [
    { id: 'chips_crisps', label: 'Chips' }, { id: 'namkeen', label: 'Namkeen' }, { id: 'nuts_seeds', label: 'Nuts' },
  ]},
  { id: 'sweets', icon: 'heart', label: 'Sweets', subcategories: [
    { id: 'chocolates', label: 'Chocolates' }, { id: 'indian_sweets', label: 'Indian Sweets' },
  ]},
  { id: 'household', icon: 'home', label: 'Household', subcategories: [
    { id: 'detergents', label: 'Detergents' }, { id: 'cleaners', label: 'Cleaners' },
  ]},
  { id: 'personal_care', icon: 'body', label: 'Personal Care', subcategories: [
    { id: 'bath_body', label: 'Bath & Body' }, { id: 'hair_care', label: 'Hair Care' },
  ]},
  { id: 'other', icon: 'grid', label: 'Other', subcategories: [{ id: 'other_general', label: 'General' }]},
];

const VARIATION_TYPES = [
  { id: 'weight', label: 'Weight', icon: 'scale', units: ['kg', 'g'] },
  { id: 'volume', label: 'Volume', icon: 'water', units: ['L', 'ml'] },
  { id: 'size', label: 'Size', icon: 'resize', units: ['size'] },
  { id: 'pack', label: 'Pack/Quantity', icon: 'cube', units: ['pieces', 'pack'] },
];

interface Variation {
  id: string;
  label: string;
  value: string;
  price: string;
  discountedPrice: string;
  stockQuantity: string;
  inStock: boolean;
}

export default function EditProductScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { colors, isDark } = useTheme();
  const { showAlert } = useAlert();
  const { setPendingToast } = useToastStore();
  
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [originalProduct, setOriginalProduct] = useState<any>(null);
  
  // Form state
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState('');
  const [subcategory, setSubcategory] = useState('');
  const [image, setImage] = useState<string | null>(null);
  
  // Product type
  const [productType, setProductType] = useState<'simple' | 'variable'>('simple');
  
  // Simple product fields
  const [price, setPrice] = useState('');
  const [discountedPrice, setDiscountedPrice] = useState('');
  const [stockQuantity, setStockQuantity] = useState('100');
  const [inStock, setInStock] = useState(true);
  const [unit, setUnit] = useState('piece');
  
  // Variable product fields
  const [variationType, setVariationType] = useState('');
  const [variationUnit, setVariationUnit] = useState('');
  const [variations, setVariations] = useState<Variation[]>([]);
  const [sharedStock, setSharedStock] = useState(false);
  
  const slideAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    loadProduct();
  }, [id]);

  const loadProduct = async () => {
    try {
      const response = await productAPI.getOne(id!);
      const product = response.data;
      setOriginalProduct(product);
      
      // Basic info
      setName(product.name);
      setDescription(product.description || '');
      setImage(product.image || null);
      
      // Category - try to match with new structure
      const catLower = (product.category || '').toLowerCase();
      const foundCat = PRODUCT_CATEGORIES.find(c => 
        c.id === catLower || c.label.toLowerCase() === catLower
      );
      setCategory(foundCat?.id || 'other');
      setSubcategory(product.subcategory || '');
      
      // Product type
      const pType = product.product_type || 'simple';
      setProductType(pType);
      
      if (pType === 'variable' && product.variations && product.variations.length > 0) {
        // Variable product
        setVariationType(product.variation_type || 'weight');
        setVariationUnit(product.variation_unit || 'kg');
        setSharedStock(product.shared_stock || false);
        
        // Map variations
        const mappedVariations: Variation[] = product.variations.map((v: any, idx: number) => ({
          id: v.variation_id || `var_${idx}`,
          label: v.label || '',
          value: v.value?.toString() || '',
          price: v.price?.toString() || '',
          discountedPrice: v.discounted_price?.toString() || '',
          stockQuantity: v.stock_quantity?.toString() || '100',
          inStock: v.in_stock !== false,
        }));
        setVariations(mappedVariations);
      } else {
        // Simple product
        setPrice(product.price?.toString() || '');
        setDiscountedPrice(product.discounted_price?.toString() || '');
        setStockQuantity(product.stock_quantity?.toString() || '100');
        setInStock(product.in_stock !== false);
        setUnit(product.unit || 'piece');
      }
      
      // Animate in
      Animated.timing(slideAnim, { toValue: 1, duration: 300, useNativeDriver: true }).start();
    } catch (error) {
      console.error('Load product error:', error);
      Alert.alert('Error', 'Failed to load product');
      router.back();
    } finally {
      setIsLoading(false);
    }
  };

  const selectedVariationType = VARIATION_TYPES.find(t => t.id === variationType);
  const selectedCategory = PRODUCT_CATEGORIES.find(c => c.id === category);

  const addVariation = () => {
    const newVariation: Variation = {
      id: `var_${Date.now()}`,
      label: '',
      value: '',
      price: '',
      discountedPrice: '',
      stockQuantity: '100',
      inStock: true,
    };
    setVariations([...variations, newVariation]);
  };

  const updateVariation = (varId: string, field: keyof Variation, value: any) => {
    setVariations(variations.map(v => v.id === varId ? { ...v, [field]: value } : v));
  };

  const removeVariation = (varId: string) => {
    if (variations.length <= 1) {
      Alert.alert('Cannot Remove', 'Variable products must have at least one variation');
      return;
    }
    setVariations(variations.filter(v => v.id !== varId));
  };

  const handlePickImage = async () => {
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      Alert.alert('Permission Required', 'Please allow access to your photo library');
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: true,
      aspect: [1, 1],
      quality: 0.7,
      base64: true,
    });
    if (!result.canceled && result.assets[0].base64) {
      setImage(`data:image/jpeg;base64,${result.assets[0].base64}`);
    }
  };

  const validateForm = (): boolean => {
    if (!name.trim()) {
      showAlert('error', 'Please enter product name');
      return false;
    }
    if (!category) {
      showAlert('error', 'Please select a category');
      return false;
    }
    
    if (productType === 'simple') {
      if (!price.trim() || parseFloat(price) <= 0) {
        showAlert('error', 'Please enter a valid price');
        return false;
      }
    } else {
      if (!variationType) {
        showAlert('error', 'Please select variation type');
        return false;
      }
      if (variations.length === 0) {
        showAlert('error', 'Please add at least one variation');
        return false;
      }
      for (const v of variations) {
        if (!v.label.trim()) {
          showAlert('error', 'Please enter label for all variations');
          return false;
        }
        if (!v.price.trim() || parseFloat(v.price) <= 0) {
          showAlert('error', 'Please enter valid price for all variations');
          return false;
        }
      }
    }
    return true;
  };

  const handleSubmit = async () => {
    if (!validateForm()) return;
    
    setIsSubmitting(true);
    try {
      const productData: any = {
        name: name.trim(),
        description: description.trim() || null,
        category: selectedCategory?.label || category,
        subcategory: subcategory || null,
        image: image,
        product_type: productType,
      };
      
      if (productType === 'simple') {
        productData.price = parseFloat(price);
        productData.discounted_price = discountedPrice ? parseFloat(discountedPrice) : null;
        productData.stock_quantity = parseInt(stockQuantity) || 100;
        productData.in_stock = inStock;
        productData.unit = unit;
        productData.variations = null;
      } else {
        productData.variation_type = variationType;
        productData.variation_unit = variationUnit;
        productData.shared_stock = sharedStock;
        productData.variations = variations.map(v => ({
          variation_id: v.id.startsWith('var_') ? v.id : `var_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`,
          label: v.label,
          value: v.value ? parseFloat(v.value) : null,
          price: parseFloat(v.price),
          discounted_price: v.discountedPrice ? parseFloat(v.discountedPrice) : null,
          stock_quantity: parseInt(v.stockQuantity) || 100,
          in_stock: v.inStock,
        }));
        // Set aggregate values
        const prices = variations.map(v => parseFloat(v.price)).filter(p => !isNaN(p));
        productData.price = Math.min(...prices);
        productData.in_stock = variations.some(v => v.inStock);
        productData.stock_quantity = sharedStock ? parseInt(stockQuantity) : variations.reduce((sum, v) => sum + (parseInt(v.stockQuantity) || 0), 0);
      }
      
      await productAPI.update(id!, productData);
      setPendingToast({ message: 'Product updated successfully!', type: 'success' });
      router.back();
    } catch (error: any) {
      console.error('Update product error:', error);
      showAlert('error', error.response?.data?.detail || 'Failed to update product');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = () => {
    Alert.alert(
      'Delete Product',
      'Are you sure you want to delete this product? This cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              await productAPI.delete(id!);
              setPendingToast({ message: 'Product deleted', type: 'success' });
              router.back();
            } catch (error) {
              showAlert('error', 'Failed to delete product');
            }
          },
        },
      ]
    );
  };

  if (isLoading) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: colors.background.grouped }]} edges={['top']}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.primary} />
          <Text style={[styles.loadingText, { color: colors.text.secondary }]}>Loading product...</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background.grouped }]} edges={['top']}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        {/* Header */}
        <View style={[styles.header, { backgroundColor: colors.card, borderBottomColor: colors.separator }]}>
          <TouchableOpacity onPress={() => router.back()} style={styles.headerBtn}>
            <Ionicons name="close" size={24} color={colors.text.primary} />
          </TouchableOpacity>
          <Text style={[styles.headerTitle, { color: colors.text.primary }]}>Edit Product</Text>
          <TouchableOpacity 
            onPress={handleSubmit} 
            disabled={isSubmitting}
            style={[styles.saveBtn, { backgroundColor: colors.primary }]}
          >
            {isSubmitting ? (
              <ActivityIndicator size="small" color="#FFFFFF" />
            ) : (
              <Text style={styles.saveBtnText}>Save</Text>
            )}
          </TouchableOpacity>
        </View>

        <ScrollView style={styles.scrollView} showsVerticalScrollIndicator={false}>
          <Animated.View style={{ opacity: slideAnim }}>
            {/* Product Image */}
            <TouchableOpacity style={[styles.imageSection, { backgroundColor: colors.card }]} onPress={handlePickImage}>
              {image ? (
                <Image source={{ uri: image }} style={styles.productImage} />
              ) : (
                <View style={[styles.imagePlaceholder, { backgroundColor: colors.background.secondary }]}>
                  <Ionicons name="camera" size={40} color={colors.text.tertiary} />
                  <Text style={[styles.imagePlaceholderText, { color: colors.text.tertiary }]}>Tap to change photo</Text>
                </View>
              )}
              <View style={[styles.imageEditBadge, { backgroundColor: colors.primary }]}>
                <Ionicons name="pencil" size={14} color="#FFFFFF" />
              </View>
            </TouchableOpacity>

            {/* Basic Info */}
            <View style={[styles.section, { backgroundColor: colors.card }]}>
              <Text style={[styles.sectionTitle, { color: colors.text.secondary }]}>BASIC INFO</Text>
              <View style={styles.inputGroup}>
                <Text style={[styles.inputLabel, { color: colors.text.secondary }]}>Product Name</Text>
                <TextInput
                  style={[styles.input, { backgroundColor: colors.background.secondary, color: colors.text.primary }]}
                  value={name}
                  onChangeText={setName}
                  placeholder="Enter product name"
                  placeholderTextColor={colors.text.tertiary}
                />
              </View>
              <View style={styles.inputGroup}>
                <Text style={[styles.inputLabel, { color: colors.text.secondary }]}>Description</Text>
                <TextInput
                  style={[styles.input, styles.textArea, { backgroundColor: colors.background.secondary, color: colors.text.primary }]}
                  value={description}
                  onChangeText={setDescription}
                  placeholder="Enter description (optional)"
                  placeholderTextColor={colors.text.tertiary}
                  multiline
                  numberOfLines={3}
                />
              </View>
            </View>

            {/* Category */}
            <View style={[styles.section, { backgroundColor: colors.card }]}>
              <Text style={[styles.sectionTitle, { color: colors.text.secondary }]}>CATEGORY</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.categoryScroll}>
                {PRODUCT_CATEGORIES.map((cat) => (
                  <TouchableOpacity
                    key={cat.id}
                    style={[
                      styles.categoryChip,
                      { backgroundColor: colors.background.secondary, borderColor: colors.separator },
                      category === cat.id && { backgroundColor: colors.primary, borderColor: colors.primary },
                    ]}
                    onPress={() => { setCategory(cat.id); setSubcategory(''); }}
                  >
                    <Ionicons
                      name={cat.icon as any}
                      size={16}
                      color={category === cat.id ? '#FFFFFF' : colors.text.secondary}
                    />
                    <Text style={[styles.categoryChipText, { color: category === cat.id ? '#FFFFFF' : colors.text.secondary }]}>
                      {cat.label}
                    </Text>
                  </TouchableOpacity>
                ))}
              </ScrollView>
              
              {/* Subcategory */}
              {selectedCategory && selectedCategory.subcategories && (
                <View style={styles.subcategoryContainer}>
                  <Text style={[styles.subLabel, { color: colors.text.tertiary }]}>Subcategory</Text>
                  <View style={styles.subcategoryGrid}>
                    {selectedCategory.subcategories.map((sub) => (
                      <TouchableOpacity
                        key={sub.id}
                        style={[
                          styles.subcategoryChip,
                          { borderColor: colors.separator },
                          subcategory === sub.id && { backgroundColor: colors.primary + '20', borderColor: colors.primary },
                        ]}
                        onPress={() => setSubcategory(sub.id)}
                      >
                        <Text style={[styles.subcategoryChipText, { color: subcategory === sub.id ? colors.primary : colors.text.primary }]}>
                          {sub.label}
                        </Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </View>
              )}
            </View>

            {/* Product Type Toggle */}
            <View style={[styles.section, { backgroundColor: colors.card }]}>
              <Text style={[styles.sectionTitle, { color: colors.text.secondary }]}>PRODUCT TYPE</Text>
              <View style={[styles.typeToggle, { backgroundColor: colors.background.secondary }]}>
                <TouchableOpacity
                  style={[styles.typeOption, productType === 'simple' && { backgroundColor: colors.primary }]}
                  onPress={() => setProductType('simple')}
                >
                  <Ionicons name="cube-outline" size={18} color={productType === 'simple' ? '#FFFFFF' : colors.text.secondary} />
                  <Text style={[styles.typeOptionText, { color: productType === 'simple' ? '#FFFFFF' : colors.text.secondary }]}>
                    Simple
                  </Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[styles.typeOption, productType === 'variable' && { backgroundColor: colors.primary }]}
                  onPress={() => setProductType('variable')}
                >
                  <Ionicons name="layers-outline" size={18} color={productType === 'variable' ? '#FFFFFF' : colors.text.secondary} />
                  <Text style={[styles.typeOptionText, { color: productType === 'variable' ? '#FFFFFF' : colors.text.secondary }]}>
                    With Variations
                  </Text>
                </TouchableOpacity>
              </View>
            </View>

            {/* Simple Product Pricing */}
            {productType === 'simple' && (
              <View style={[styles.section, { backgroundColor: colors.card }]}>
                <Text style={[styles.sectionTitle, { color: colors.text.secondary }]}>PRICING & STOCK</Text>
                <View style={styles.priceRow}>
                  <View style={[styles.inputGroup, { flex: 1 }]}>
                    <Text style={[styles.inputLabel, { color: colors.text.secondary }]}>Price (₹)</Text>
                    <TextInput
                      style={[styles.input, { backgroundColor: colors.background.secondary, color: colors.text.primary }]}
                      value={price}
                      onChangeText={setPrice}
                      placeholder="0.00"
                      placeholderTextColor={colors.text.tertiary}
                      keyboardType="decimal-pad"
                    />
                  </View>
                  <View style={{ width: 12 }} />
                  <View style={[styles.inputGroup, { flex: 1 }]}>
                    <Text style={[styles.inputLabel, { color: colors.text.secondary }]}>Discounted</Text>
                    <TextInput
                      style={[styles.input, { backgroundColor: colors.background.secondary, color: colors.text.primary }]}
                      value={discountedPrice}
                      onChangeText={setDiscountedPrice}
                      placeholder="Optional"
                      placeholderTextColor={colors.text.tertiary}
                      keyboardType="decimal-pad"
                    />
                  </View>
                </View>
                <View style={styles.stockRow}>
                  <TouchableOpacity
                    style={[styles.stockToggle, { backgroundColor: inStock ? colors.success + '20' : colors.danger + '20' }]}
                    onPress={() => setInStock(!inStock)}
                  >
                    <Ionicons name={inStock ? 'checkmark-circle' : 'close-circle'} size={18} color={inStock ? colors.success : colors.danger} />
                    <Text style={[styles.stockToggleText, { color: inStock ? colors.success : colors.danger }]}>
                      {inStock ? 'In Stock' : 'Out of Stock'}
                    </Text>
                  </TouchableOpacity>
                  <View style={[styles.inputGroup, { flex: 1, marginLeft: 12 }]}>
                    <Text style={[styles.inputLabel, { color: colors.text.secondary }]}>Quantity</Text>
                    <TextInput
                      style={[styles.input, { backgroundColor: colors.background.secondary, color: colors.text.primary }]}
                      value={stockQuantity}
                      onChangeText={setStockQuantity}
                      keyboardType="number-pad"
                      placeholderTextColor={colors.text.tertiary}
                    />
                  </View>
                </View>
              </View>
            )}

            {/* Variable Product */}
            {productType === 'variable' && (
              <>
                {/* Variation Type Selection */}
                <View style={[styles.section, { backgroundColor: colors.card }]}>
                  <Text style={[styles.sectionTitle, { color: colors.text.secondary }]}>VARIATION TYPE</Text>
                  <View style={styles.variationTypeRow}>
                    {VARIATION_TYPES.map((type) => (
                      <TouchableOpacity
                        key={type.id}
                        style={[
                          styles.variationTypeChip,
                          { backgroundColor: colors.background.secondary, borderColor: colors.separator },
                          variationType === type.id && { backgroundColor: colors.primary, borderColor: colors.primary },
                        ]}
                        onPress={() => { setVariationType(type.id); setVariationUnit(type.units[0]); }}
                      >
                        <Ionicons name={type.icon as any} size={18} color={variationType === type.id ? '#FFFFFF' : colors.text.secondary} />
                        <Text style={[styles.variationTypeText, { color: variationType === type.id ? '#FFFFFF' : colors.text.secondary }]}>
                          {type.label}
                        </Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                  
                  {/* Unit Selection */}
                  {selectedVariationType && (
                    <View style={styles.unitRow}>
                      <Text style={[styles.subLabel, { color: colors.text.tertiary }]}>Unit:</Text>
                      {selectedVariationType.units.map((u) => (
                        <TouchableOpacity
                          key={u}
                          style={[
                            styles.unitChip,
                            { borderColor: colors.separator },
                            variationUnit === u && { backgroundColor: colors.primary, borderColor: colors.primary },
                          ]}
                          onPress={() => setVariationUnit(u)}
                        >
                          <Text style={[styles.unitChipText, { color: variationUnit === u ? '#FFFFFF' : colors.text.secondary }]}>
                            {u}
                          </Text>
                        </TouchableOpacity>
                      ))}
                    </View>
                  )}
                </View>

                {/* Variations List */}
                <View style={[styles.section, { backgroundColor: colors.card }]}>
                  <View style={styles.sectionHeader}>
                    <Text style={[styles.sectionTitle, { color: colors.text.secondary }]}>VARIATIONS ({variations.length})</Text>
                    <TouchableOpacity style={[styles.addBtn, { backgroundColor: colors.primary }]} onPress={addVariation}>
                      <Ionicons name="add" size={18} color="#FFFFFF" />
                      <Text style={styles.addBtnText}>Add</Text>
                    </TouchableOpacity>
                  </View>
                  
                  {variations.length === 0 ? (
                    <View style={[styles.emptyState, { backgroundColor: colors.background.secondary }]}>
                      <Ionicons name="layers-outline" size={32} color={colors.text.tertiary} />
                      <Text style={[styles.emptyText, { color: colors.text.tertiary }]}>No variations added</Text>
                    </View>
                  ) : (
                    variations.map((variation, index) => (
                      <View key={variation.id} style={[styles.variationCard, { backgroundColor: colors.background.secondary }]}>
                        <View style={styles.variationHeader}>
                          <View style={[styles.variationBadge, { backgroundColor: colors.primary + '20' }]}>
                            <Text style={[styles.variationBadgeText, { color: colors.primary }]}>#{index + 1}</Text>
                          </View>
                          <TouchableOpacity onPress={() => removeVariation(variation.id)} style={styles.deleteBtn}>
                            <Ionicons name="trash-outline" size={18} color={colors.danger} />
                          </TouchableOpacity>
                        </View>
                        
                        <View style={styles.variationRow}>
                          <View style={[styles.inputGroup, { flex: 1 }]}>
                            <Text style={[styles.inputLabel, { color: colors.text.tertiary }]}>Label</Text>
                            <TextInput
                              style={[styles.input, styles.inputSmall, { backgroundColor: colors.card, color: colors.text.primary }]}
                              value={variation.label}
                              onChangeText={(v) => updateVariation(variation.id, 'label', v)}
                              placeholder={variationType === 'weight' ? 'e.g., 1 kg' : 'e.g., Small'}
                              placeholderTextColor={colors.text.tertiary}
                            />
                          </View>
                          <View style={{ width: 8 }} />
                          <View style={[styles.inputGroup, { flex: 1 }]}>
                            <Text style={[styles.inputLabel, { color: colors.text.tertiary }]}>Price (₹)</Text>
                            <TextInput
                              style={[styles.input, styles.inputSmall, { backgroundColor: colors.card, color: colors.text.primary }]}
                              value={variation.price}
                              onChangeText={(v) => updateVariation(variation.id, 'price', v)}
                              placeholder="0.00"
                              placeholderTextColor={colors.text.tertiary}
                              keyboardType="decimal-pad"
                            />
                          </View>
                        </View>
                        
                        <View style={styles.variationRow}>
                          <View style={[styles.inputGroup, { flex: 1 }]}>
                            <Text style={[styles.inputLabel, { color: colors.text.tertiary }]}>Discounted</Text>
                            <TextInput
                              style={[styles.input, styles.inputSmall, { backgroundColor: colors.card, color: colors.text.primary }]}
                              value={variation.discountedPrice}
                              onChangeText={(v) => updateVariation(variation.id, 'discountedPrice', v)}
                              placeholder="Optional"
                              placeholderTextColor={colors.text.tertiary}
                              keyboardType="decimal-pad"
                            />
                          </View>
                          <View style={{ width: 8 }} />
                          <View style={[styles.inputGroup, { flex: 1 }]}>
                            <Text style={[styles.inputLabel, { color: colors.text.tertiary }]}>Stock</Text>
                            <TextInput
                              style={[styles.input, styles.inputSmall, { backgroundColor: colors.card, color: colors.text.primary }]}
                              value={variation.stockQuantity}
                              onChangeText={(v) => updateVariation(variation.id, 'stockQuantity', v)}
                              keyboardType="number-pad"
                              placeholderTextColor={colors.text.tertiary}
                            />
                          </View>
                        </View>
                        
                        <TouchableOpacity
                          style={[styles.inStockToggle, { backgroundColor: variation.inStock ? colors.success + '15' : colors.danger + '15' }]}
                          onPress={() => updateVariation(variation.id, 'inStock', !variation.inStock)}
                        >
                          <Ionicons
                            name={variation.inStock ? 'checkmark-circle' : 'close-circle'}
                            size={16}
                            color={variation.inStock ? colors.success : colors.danger}
                          />
                          <Text style={[styles.inStockText, { color: variation.inStock ? colors.success : colors.danger }]}>
                            {variation.inStock ? 'In Stock' : 'Out of Stock'}
                          </Text>
                        </TouchableOpacity>
                      </View>
                    ))
                  )}
                </View>
              </>
            )}

            {/* Delete Button */}
            <TouchableOpacity style={[styles.deleteProductBtn, { backgroundColor: colors.danger + '15' }]} onPress={handleDelete}>
              <Ionicons name="trash-outline" size={20} color={colors.danger} />
              <Text style={[styles.deleteProductText, { color: colors.danger }]}>Delete Product</Text>
            </TouchableOpacity>

            <View style={{ height: 40 }} />
          </Animated.View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  loadingText: { marginTop: 12, fontSize: 14 },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  headerBtn: { padding: 4 },
  headerTitle: { fontSize: 17, fontWeight: '600' },
  saveBtn: { paddingHorizontal: 16, paddingVertical: 8, borderRadius: 8, minWidth: 60, alignItems: 'center' },
  saveBtnText: { color: '#FFFFFF', fontWeight: '600', fontSize: 15 },
  scrollView: { flex: 1 },
  imageSection: { margin: 16, borderRadius: 16, overflow: 'hidden', position: 'relative' },
  productImage: { width: '100%', aspectRatio: 1, resizeMode: 'cover' },
  imagePlaceholder: { width: '100%', aspectRatio: 1, justifyContent: 'center', alignItems: 'center' },
  imagePlaceholderText: { marginTop: 8, fontSize: 14 },
  imageEditBadge: {
    position: 'absolute', bottom: 12, right: 12, width: 32, height: 32, borderRadius: 16,
    justifyContent: 'center', alignItems: 'center',
  },
  section: { marginHorizontal: 16, marginBottom: 16, borderRadius: 12, padding: 16 },
  sectionTitle: { fontSize: 12, fontWeight: '600', letterSpacing: 0.5, marginBottom: 12 },
  sectionHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  inputGroup: { marginBottom: 12 },
  inputLabel: { fontSize: 12, fontWeight: '500', marginBottom: 6 },
  input: { height: 44, borderRadius: 10, paddingHorizontal: 12, fontSize: 15 },
  inputSmall: { height: 40, fontSize: 14 },
  textArea: { height: 80, textAlignVertical: 'top', paddingTop: 10 },
  categoryScroll: { marginBottom: 12 },
  categoryChip: {
    flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, paddingVertical: 8,
    borderRadius: 8, marginRight: 8, borderWidth: 1,
  },
  categoryChipText: { marginLeft: 6, fontSize: 13, fontWeight: '500' },
  subcategoryContainer: { marginTop: 8 },
  subLabel: { fontSize: 11, fontWeight: '500', marginBottom: 8 },
  subcategoryGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  subcategoryChip: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 6, borderWidth: 1 },
  subcategoryChipText: { fontSize: 12 },
  typeToggle: { flexDirection: 'row', borderRadius: 10, padding: 4 },
  typeOption: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: 10, borderRadius: 8, gap: 6 },
  typeOptionText: { fontSize: 14, fontWeight: '500' },
  priceRow: { flexDirection: 'row' },
  stockRow: { flexDirection: 'row', alignItems: 'flex-end' },
  stockToggle: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, paddingVertical: 10, borderRadius: 8, gap: 6 },
  stockToggleText: { fontSize: 13, fontWeight: '500' },
  variationTypeRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  variationTypeChip: {
    flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, paddingVertical: 10,
    borderRadius: 8, borderWidth: 1, gap: 6,
  },
  variationTypeText: { fontSize: 13, fontWeight: '500' },
  unitRow: { flexDirection: 'row', alignItems: 'center', marginTop: 12, gap: 8 },
  unitChip: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 6, borderWidth: 1 },
  unitChipText: { fontSize: 12, fontWeight: '500' },
  addBtn: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, paddingVertical: 6, borderRadius: 6, gap: 4 },
  addBtnText: { color: '#FFFFFF', fontSize: 13, fontWeight: '600' },
  emptyState: { padding: 24, borderRadius: 10, alignItems: 'center' },
  emptyText: { marginTop: 8, fontSize: 13 },
  variationCard: { borderRadius: 10, padding: 12, marginBottom: 10 },
  variationHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  variationBadge: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 4 },
  variationBadgeText: { fontSize: 12, fontWeight: '600' },
  deleteBtn: { padding: 4 },
  variationRow: { flexDirection: 'row', marginBottom: 8 },
  inStockToggle: { flexDirection: 'row', alignItems: 'center', alignSelf: 'flex-start', paddingHorizontal: 10, paddingVertical: 6, borderRadius: 6, gap: 4 },
  inStockText: { fontSize: 12, fontWeight: '500' },
  deleteProductBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    marginHorizontal: 16, padding: 14, borderRadius: 12, gap: 8,
  },
  deleteProductText: { fontSize: 15, fontWeight: '600' },
});
