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
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import { productAPI } from '../../../../src/utils/api';
import { useAlert } from '../../../../src/context/AlertContext';
import { useToastStore } from '../../../../src/store/toastStore';
import { useTheme } from '../../../../src/context/ThemeContext';

// Comprehensive category structure with subcategories (inspired by Yandex Market)
const PRODUCT_CATEGORIES = [
  {
    id: 'groceries',
    icon: 'basket',
    label: 'Groceries',
    subcategories: [
      { id: 'rice_grains', label: 'Rice & Grains' },
      { id: 'flour_baking', label: 'Flour & Baking' },
      { id: 'pasta_noodles', label: 'Pasta & Noodles' },
      { id: 'oils_ghee', label: 'Oils & Ghee' },
      { id: 'spices_masala', label: 'Spices & Masala' },
      { id: 'pulses_lentils', label: 'Pulses & Lentils' },
      { id: 'sugar_salt', label: 'Sugar & Salt' },
      { id: 'pickles_chutneys', label: 'Pickles & Chutneys' },
      { id: 'ready_to_cook', label: 'Ready to Cook' },
      { id: 'canned_jarred', label: 'Canned & Jarred' },
    ],
  },
  {
    id: 'beverages',
    icon: 'cafe',
    label: 'Beverages',
    subcategories: [
      { id: 'tea', label: 'Tea (Leaves & Bags)' },
      { id: 'coffee', label: 'Coffee (Powder & Beans)' },
      { id: 'soft_drinks', label: 'Soft Drinks & Soda' },
      { id: 'juices', label: 'Juices & Nectars' },
      { id: 'energy_drinks', label: 'Energy & Sports Drinks' },
      { id: 'water', label: 'Mineral & Packaged Water' },
      { id: 'health_drinks', label: 'Health Drinks & Mixes' },
      { id: 'syrups_squash', label: 'Syrups & Squash' },
    ],
  },
  {
    id: 'dairy',
    icon: 'ellipse',
    label: 'Dairy & Eggs',
    subcategories: [
      { id: 'milk', label: 'Milk (Fresh & Flavored)' },
      { id: 'curd_yogurt', label: 'Curd & Yogurt' },
      { id: 'cheese', label: 'Cheese' },
      { id: 'butter_ghee', label: 'Butter & Ghee' },
      { id: 'paneer_tofu', label: 'Paneer & Tofu' },
      { id: 'eggs', label: 'Eggs' },
      { id: 'cream', label: 'Cream & Whiteners' },
      { id: 'condensed_milk', label: 'Condensed & Evaporated' },
    ],
  },
  {
    id: 'fruits',
    icon: 'nutrition',
    label: 'Fruits',
    subcategories: [
      { id: 'fresh_seasonal', label: 'Fresh Seasonal Fruits' },
      { id: 'exotic_imported', label: 'Exotic & Imported' },
      { id: 'citrus', label: 'Citrus Fruits' },
      { id: 'berries', label: 'Berries' },
      { id: 'dry_fruits', label: 'Dry Fruits & Nuts' },
      { id: 'dates_figs', label: 'Dates & Figs' },
      { id: 'fruit_baskets', label: 'Fruit Baskets & Combos' },
    ],
  },
  {
    id: 'vegetables',
    icon: 'leaf',
    label: 'Vegetables',
    subcategories: [
      { id: 'fresh_daily', label: 'Fresh Daily Vegetables' },
      { id: 'leafy_greens', label: 'Leafy Greens' },
      { id: 'root_tubers', label: 'Root & Tubers' },
      { id: 'exotic_veggies', label: 'Exotic Vegetables' },
      { id: 'herbs_seasonings', label: 'Fresh Herbs' },
      { id: 'mushrooms', label: 'Mushrooms' },
      { id: 'sprouts', label: 'Sprouts & Microgreens' },
      { id: 'cut_ready', label: 'Cut & Ready to Cook' },
    ],
  },
  {
    id: 'meat',
    icon: 'restaurant',
    label: 'Meat & Poultry',
    subcategories: [
      { id: 'chicken', label: 'Chicken' },
      { id: 'mutton', label: 'Mutton & Lamb' },
      { id: 'beef', label: 'Beef' },
      { id: 'pork', label: 'Pork' },
      { id: 'duck_turkey', label: 'Duck & Turkey' },
      { id: 'organ_meat', label: 'Organ Meat (Liver, Kidney)' },
      { id: 'marinated', label: 'Marinated & Ready to Cook' },
      { id: 'sausages_cold_cuts', label: 'Sausages & Cold Cuts' },
      { id: 'mince_keema', label: 'Mince & Keema' },
    ],
  },
  {
    id: 'seafood',
    icon: 'fish',
    label: 'Seafood',
    subcategories: [
      { id: 'fish_fresh', label: 'Fresh Fish' },
      { id: 'fish_fillets', label: 'Fish Fillets & Steaks' },
      { id: 'prawns_shrimp', label: 'Prawns & Shrimp' },
      { id: 'crabs_lobster', label: 'Crabs & Lobster' },
      { id: 'squid_octopus', label: 'Squid & Octopus' },
      { id: 'shellfish', label: 'Shellfish & Mussels' },
      { id: 'dried_seafood', label: 'Dried Seafood' },
      { id: 'marinated_seafood', label: 'Marinated & Ready to Cook' },
    ],
  },
  {
    id: 'frozen',
    icon: 'snow',
    label: 'Frozen Foods',
    subcategories: [
      { id: 'frozen_veggies', label: 'Frozen Vegetables' },
      { id: 'frozen_fruits', label: 'Frozen Fruits & Berries' },
      { id: 'frozen_meat', label: 'Frozen Meat & Poultry' },
      { id: 'frozen_seafood', label: 'Frozen Seafood' },
      { id: 'frozen_snacks', label: 'Frozen Snacks & Appetizers' },
      { id: 'frozen_meals', label: 'Frozen Ready Meals' },
      { id: 'ice_cream', label: 'Ice Cream & Desserts' },
      { id: 'frozen_parathas', label: 'Frozen Parathas & Breads' },
      { id: 'frozen_fries', label: 'Fries & Potato Products' },
    ],
  },
  {
    id: 'bakery',
    icon: 'pizza',
    label: 'Bakery & Breads',
    subcategories: [
      { id: 'breads', label: 'Breads & Buns' },
      { id: 'cakes_pastries', label: 'Cakes & Pastries' },
      { id: 'cookies_biscuits', label: 'Cookies & Biscuits' },
      { id: 'rusks_toast', label: 'Rusks & Toast' },
      { id: 'croissants', label: 'Croissants & Danish' },
      { id: 'puffs_patties', label: 'Puffs & Patties' },
    ],
  },
  {
    id: 'snacks',
    icon: 'fast-food',
    label: 'Snacks & Chips',
    subcategories: [
      { id: 'chips_crisps', label: 'Chips & Crisps' },
      { id: 'namkeen', label: 'Namkeen & Savory' },
      { id: 'nuts_seeds', label: 'Nuts & Seeds' },
      { id: 'popcorn', label: 'Popcorn' },
      { id: 'crackers', label: 'Crackers & Wafers' },
      { id: 'protein_bars', label: 'Protein & Energy Bars' },
    ],
  },
  {
    id: 'sweets',
    icon: 'heart',
    label: 'Sweets & Chocolates',
    subcategories: [
      { id: 'chocolates', label: 'Chocolates' },
      { id: 'indian_sweets', label: 'Indian Sweets (Mithai)' },
      { id: 'candies', label: 'Candies & Toffees' },
      { id: 'dessert_mixes', label: 'Dessert Mixes' },
    ],
  },
  {
    id: 'baby_care',
    icon: 'happy',
    label: 'Baby Food & Care',
    subcategories: [
      { id: 'baby_formula', label: 'Baby Formula' },
      { id: 'baby_food', label: 'Baby Food & Cereals' },
      { id: 'diapers', label: 'Diapers & Wipes' },
      { id: 'baby_care', label: 'Baby Care Products' },
    ],
  },
  {
    id: 'household',
    icon: 'home',
    label: 'Household & Cleaning',
    subcategories: [
      { id: 'detergents', label: 'Detergents & Laundry' },
      { id: 'dishwash', label: 'Dishwash & Kitchen Clean' },
      { id: 'cleaners', label: 'Floor & Surface Cleaners' },
      { id: 'fresheners', label: 'Air Fresheners' },
      { id: 'tissue_napkins', label: 'Tissues & Napkins' },
    ],
  },
  {
    id: 'personal_care',
    icon: 'body',
    label: 'Personal Care',
    subcategories: [
      { id: 'bath_body', label: 'Bath & Body' },
      { id: 'hair_care', label: 'Hair Care' },
      { id: 'oral_care', label: 'Oral Care' },
      { id: 'skin_care', label: 'Skin Care' },
      { id: 'feminine_care', label: 'Feminine Care' },
    ],
  },
  {
    id: 'pet_supplies',
    icon: 'paw',
    label: 'Pet Supplies',
    subcategories: [
      { id: 'pet_food', label: 'Pet Food' },
      { id: 'pet_treats', label: 'Pet Treats' },
      { id: 'pet_care', label: 'Pet Care & Grooming' },
    ],
  },
  {
    id: 'other',
    icon: 'grid',
    label: 'Other',
    subcategories: [
      { id: 'other_general', label: 'General' },
    ],
  },
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

export default function AddProductScreen() {
  const router = useRouter();
  const { colors, isDark } = useTheme();
  const { showAlert } = useAlert();
  const { setPendingToast } = useToastStore();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const progressAnim = useRef(new Animated.Value(0)).current;

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

  // Variable product fields
  const [variationType, setVariationType] = useState('');
  const [variationUnit, setVariationUnit] = useState('');
  const [variations, setVariations] = useState<Variation[]>([]);
  const [sharedStock, setSharedStock] = useState(false);

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

  const updateVariation = (id: string, field: keyof Variation, value: any) => {
    setVariations(variations.map(v => 
      v.id === id ? { ...v, [field]: value } : v
    ));
  };

  const removeVariation = (id: string) => {
    setVariations(variations.filter(v => v.id !== id));
  };

  // Calculate form completion
  useEffect(() => {
    let filled = 0;
    const total = productType === 'simple' ? 4 : 5;
    if (name.trim()) filled++;
    if (category) filled++;
    if (productType === 'simple') {
      if (price.trim()) filled++;
      filled++; // stock is always filled by default
    } else {
      if (variationType) filled++;
      if (variations.length > 0) filled++;
      if (variations.every(v => v.label && v.price)) filled++;
    }

    Animated.spring(progressAnim, {
      toValue: filled / total,
      useNativeDriver: false,
    }).start();
  }, [name, price, category, productType, variationType, variations]);

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

  const handleSubmit = async () => {
    // Validation
    if (!name.trim()) {
      showAlert({ type: 'warning', title: 'Required', message: 'Please enter product name' });
      return;
    }
    if (!category) {
      showAlert({ type: 'warning', title: 'Required', message: 'Please select a category' });
      return;
    }
    if (!subcategory) {
      showAlert({ type: 'warning', title: 'Required', message: 'Please select a subcategory' });
      return;
    }

    if (productType === 'simple') {
      if (!price.trim() || isNaN(Number(price))) {
        showAlert({ type: 'warning', title: 'Required', message: 'Please enter a valid price' });
        return;
      }
      const priceNum = parseFloat(price);
      const discountNum = discountedPrice ? parseFloat(discountedPrice) : null;
      if (discountNum && discountNum >= priceNum) {
        showAlert({ type: 'error', title: 'Invalid', message: 'Discounted price must be less than original price' });
        return;
      }
    } else {
      if (!variationType) {
        showAlert({ type: 'warning', title: 'Required', message: 'Please select variation type' });
        return;
      }
      if (variations.length === 0) {
        showAlert({ type: 'warning', title: 'Required', message: 'Please add at least one variation' });
        return;
      }
      for (const v of variations) {
        if (!v.label.trim()) {
          showAlert({ type: 'warning', title: 'Required', message: 'Please fill all variation labels' });
          return;
        }
        if (!v.price.trim() || isNaN(Number(v.price))) {
          showAlert({ type: 'warning', title: 'Required', message: `Please enter valid price for ${v.label || 'variation'}` });
          return;
        }
      }
    }

    setIsSubmitting(true);
    try {
      const productData: any = {
        name: name.trim(),
        description: description.trim() || null,
        category,
        image,
        product_type: productType,
      };

      if (productType === 'simple') {
        productData.price = parseFloat(price);
        productData.discounted_price = discountedPrice ? parseFloat(discountedPrice) : null;
        productData.stock_quantity = parseInt(stockQuantity) || 100;
        productData.in_stock = inStock;
        productData.unit = 'piece';
      } else {
        productData.variation_type = variationType;
        productData.variation_unit = variationUnit;
        productData.shared_stock = sharedStock;
        productData.stock_quantity = sharedStock ? parseInt(stockQuantity) || 100 : 0;
        productData.variations = variations.map(v => ({
          label: v.label,
          value: v.value ? parseFloat(v.value) : null,
          price: parseFloat(v.price),
          discounted_price: v.discountedPrice ? parseFloat(v.discountedPrice) : null,
          stock_quantity: parseInt(v.stockQuantity) || 100,
          in_stock: v.inStock,
        }));
      }

      await productAPI.create(productData);
      
      setPendingToast({
        type: 'success',
        title: 'Success! 🎉',
        message: 'Product added successfully!',
      });
      
      router.back();
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

  const progressWidth = progressAnim.interpolate({
    inputRange: [0, 1],
    outputRange: ['0%', '100%'],
  });

  const selectedVariationType = VARIATION_TYPES.find(v => v.id === variationType);

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background.grouped }]} edges={['top']}>
      {/* Header */}
      <View style={[styles.header, { backgroundColor: colors.card }]}>
        <TouchableOpacity style={styles.backBtn} onPress={() => router.back()}>
          <Ionicons name="arrow-back" size={24} color={colors.text.primary} />
        </TouchableOpacity>
        <Text style={[styles.headerTitle, { color: colors.text.primary }]}>Add Product ✨</Text>
        <View style={styles.headerRight} />
      </View>

      {/* Progress Bar */}
      <View style={[styles.progressContainer, { backgroundColor: colors.background.secondary }]}>
        <Animated.View style={[styles.progressBar, { width: progressWidth, backgroundColor: colors.primary }]} />
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
            <Text style={[styles.sectionTitle, { color: colors.text.secondary }]}>PRODUCT IMAGE</Text>
            <TouchableOpacity
              style={[styles.imageContainer, { backgroundColor: colors.card, borderColor: colors.separator }]}
              onPress={handlePickImage}
            >
              {image ? (
                <Image source={{ uri: image }} style={styles.productImage} />
              ) : (
                <View style={styles.imagePlaceholder}>
                  <Ionicons name="camera" size={40} color={colors.text.tertiary} />
                  <Text style={[styles.imagePlaceholderText, { color: colors.text.tertiary }]}>Tap to add photo</Text>
                </View>
              )}
            </TouchableOpacity>
          </View>

          {/* Basic Info */}
          <View style={styles.section}>
            <Text style={[styles.sectionTitle, { color: colors.text.secondary }]}>BASIC INFO</Text>
            <View style={[styles.card, { backgroundColor: colors.card }]}>
              <View style={styles.inputGroup}>
                <Text style={[styles.inputLabel, { color: colors.text.secondary }]}>Product Name *</Text>
                <TextInput
                  style={[styles.input, { backgroundColor: colors.background.secondary, color: colors.text.primary }]}
                  placeholder="e.g., Basmati Rice"
                  placeholderTextColor={colors.text.tertiary}
                  value={name}
                  onChangeText={setName}
                />
              </View>
              <View style={styles.inputGroup}>
                <Text style={[styles.inputLabel, { color: colors.text.secondary }]}>Description</Text>
                <TextInput
                  style={[styles.input, styles.textArea, { backgroundColor: colors.background.secondary, color: colors.text.primary }]}
                  placeholder="Describe your product..."
                  placeholderTextColor={colors.text.tertiary}
                  value={description}
                  onChangeText={setDescription}
                  multiline
                  numberOfLines={3}
                />
              </View>
            </View>
          </View>

          {/* Category Selection */}
          <View style={styles.section}>
            <Text style={[styles.sectionTitle, { color: colors.text.secondary }]}>CATEGORY *</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.categoryScroll}>
              {PRODUCT_CATEGORIES.map((cat) => (
                <TouchableOpacity
                  key={cat.id}
                  style={[
                    styles.categoryChip,
                    { backgroundColor: colors.card, borderColor: colors.separator },
                    category === cat.id && { backgroundColor: colors.primary, borderColor: colors.primary },
                  ]}
                  onPress={() => {
                    setCategory(cat.id);
                    setSubcategory(''); // Reset subcategory when category changes
                  }}
                >
                  <Ionicons
                    name={cat.icon as any}
                    size={18}
                    color={category === cat.id ? '#FFFFFF' : colors.text.secondary}
                  />
                  <Text
                    style={[
                      styles.categoryChipText,
                      { color: colors.text.secondary },
                      category === cat.id && { color: '#FFFFFF' },
                    ]}
                  >
                    {cat.label}
                  </Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
          </View>

          {/* Subcategory Selection */}
          {category && (
            <View style={styles.section}>
              <Text style={[styles.sectionTitle, { color: colors.text.secondary }]}>SUBCATEGORY *</Text>
              <View style={[styles.subcategoryGrid, { backgroundColor: colors.card }]}>
                {PRODUCT_CATEGORIES.find(c => c.id === category)?.subcategories?.map((sub) => (
                  <TouchableOpacity
                    key={sub.id}
                    style={[
                      styles.subcategoryChip,
                      { borderColor: colors.separator },
                      subcategory === sub.id && { backgroundColor: isDark ? 'rgba(10, 132, 255, 0.2)' : 'rgba(0, 122, 255, 0.1)', borderColor: colors.primary },
                    ]}
                    onPress={() => setSubcategory(sub.id)}
                  >
                    {subcategory === sub.id && (
                      <Ionicons name="checkmark-circle" size={16} color={colors.primary} style={{ marginRight: 6 }} />
                    )}
                    <Text
                      style={[
                        styles.subcategoryChipText,
                        { color: colors.text.primary },
                        subcategory === sub.id && { color: colors.primary, fontWeight: '600' },
                      ]}
                    >
                      {sub.label}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>
          )}

          {/* Product Type Selection */}
          <View style={styles.section}>
            <Text style={[styles.sectionTitle, { color: colors.text.secondary }]}>PRODUCT TYPE *</Text>
            <View style={[styles.typeToggle, { backgroundColor: colors.card }]}>
              <TouchableOpacity
                style={[
                  styles.typeOption,
                  productType === 'simple' && { backgroundColor: colors.primary },
                ]}
                onPress={() => setProductType('simple')}
              >
                <Ionicons
                  name="cube-outline"
                  size={20}
                  color={productType === 'simple' ? '#FFFFFF' : colors.text.secondary}
                />
                <Text
                  style={[
                    styles.typeOptionText,
                    { color: colors.text.secondary },
                    productType === 'simple' && { color: '#FFFFFF' },
                  ]}
                >
                  Simple Product
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[
                  styles.typeOption,
                  productType === 'variable' && { backgroundColor: colors.primary },
                ]}
                onPress={() => setProductType('variable')}
              >
                <Ionicons
                  name="layers-outline"
                  size={20}
                  color={productType === 'variable' ? '#FFFFFF' : colors.text.secondary}
                />
                <Text
                  style={[
                    styles.typeOptionText,
                    { color: colors.text.secondary },
                    productType === 'variable' && { color: '#FFFFFF' },
                  ]}
                >
                  With Variations
                </Text>
              </TouchableOpacity>
            </View>
          </View>

          {/* Simple Product Pricing */}
          {productType === 'simple' && (
            <View style={styles.section}>
              <Text style={[styles.sectionTitle, { color: colors.text.secondary }]}>PRICING & STOCK</Text>
              <View style={[styles.card, { backgroundColor: colors.card }]}>
                <View style={styles.priceRow}>
                  <View style={[styles.inputGroup, { flex: 1 }]}>
                    <Text style={[styles.inputLabel, { color: colors.text.secondary }]}>Price (₹) *</Text>
                    <TextInput
                      style={[styles.input, { backgroundColor: colors.background.secondary, color: colors.text.primary }]}
                      placeholder="0.00"
                      placeholderTextColor={colors.text.tertiary}
                      value={price}
                      onChangeText={setPrice}
                      keyboardType="decimal-pad"
                    />
                  </View>
                  <View style={{ width: 12 }} />
                  <View style={[styles.inputGroup, { flex: 1 }]}>
                    <Text style={[styles.inputLabel, { color: colors.text.secondary }]}>Discounted</Text>
                    <TextInput
                      style={[styles.input, { backgroundColor: colors.background.secondary, color: colors.text.primary }]}
                      placeholder="Optional"
                      placeholderTextColor={colors.text.tertiary}
                      value={discountedPrice}
                      onChangeText={setDiscountedPrice}
                      keyboardType="decimal-pad"
                    />
                  </View>
                </View>
                <View style={styles.stockRow}>
                  <TouchableOpacity
                    style={[styles.stockToggle, inStock && { backgroundColor: isDark ? 'rgba(48, 209, 88, 0.2)' : '#D1FAE5' }]}
                    onPress={() => setInStock(!inStock)}
                  >
                    <Ionicons
                      name={inStock ? 'checkmark-circle' : 'close-circle'}
                      size={20}
                      color={inStock ? colors.success : colors.danger}
                    />
                    <Text style={[styles.stockToggleText, { color: inStock ? colors.success : colors.danger }]}>
                      {inStock ? 'In Stock' : 'Out of Stock'}
                    </Text>
                  </TouchableOpacity>
                  <View style={[styles.inputGroup, { flex: 1, marginLeft: 12 }]}>
                    <Text style={[styles.inputLabel, { color: colors.text.secondary }]}>Quantity</Text>
                    <TextInput
                      style={[styles.input, { backgroundColor: colors.background.secondary, color: colors.text.primary }]}
                      placeholder="100"
                      placeholderTextColor={colors.text.tertiary}
                      value={stockQuantity}
                      onChangeText={setStockQuantity}
                      keyboardType="number-pad"
                    />
                  </View>
                </View>
              </View>
            </View>
          )}

          {/* Variable Product - Variation Type */}
          {productType === 'variable' && (
            <>
              <View style={styles.section}>
                <Text style={[styles.sectionTitle, { color: colors.text.secondary }]}>VARIATION TYPE *</Text>
                <View style={styles.variationTypeGrid}>
                  {VARIATION_TYPES.map((type) => (
                    <TouchableOpacity
                      key={type.id}
                      style={[
                        styles.variationTypeCard,
                        { backgroundColor: colors.card, borderColor: colors.separator },
                        variationType === type.id && { borderColor: colors.primary, borderWidth: 2 },
                      ]}
                      onPress={() => {
                        setVariationType(type.id);
                        setVariationUnit(type.units[0]);
                      }}
                    >
                      <Ionicons
                        name={type.icon as any}
                        size={24}
                        color={variationType === type.id ? colors.primary : colors.text.secondary}
                      />
                      <Text
                        style={[
                          styles.variationTypeLabel,
                          { color: colors.text.primary },
                          variationType === type.id && { color: colors.primary },
                        ]}
                      >
                        {type.label}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </View>

              {/* Unit Selection */}
              {variationType && selectedVariationType && (
                <View style={styles.section}>
                  <Text style={[styles.sectionTitle, { color: colors.text.secondary }]}>UNIT</Text>
                  <View style={styles.unitRow}>
                    {selectedVariationType.units.map((unit) => (
                      <TouchableOpacity
                        key={unit}
                        style={[
                          styles.unitChip,
                          { backgroundColor: colors.card, borderColor: colors.separator },
                          variationUnit === unit && { backgroundColor: colors.primary, borderColor: colors.primary },
                        ]}
                        onPress={() => setVariationUnit(unit)}
                      >
                        <Text
                          style={[
                            styles.unitChipText,
                            { color: colors.text.secondary },
                            variationUnit === unit && { color: '#FFFFFF' },
                          ]}
                        >
                          {unit}
                        </Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </View>
              )}

              {/* Variations List */}
              {variationType && (
                <View style={styles.section}>
                  <View style={styles.sectionHeaderRow}>
                    <Text style={[styles.sectionTitle, { color: colors.text.secondary }]}>VARIATIONS</Text>
                    <TouchableOpacity style={[styles.addVariationBtn, { backgroundColor: colors.primary }]} onPress={addVariation}>
                      <Ionicons name="add" size={18} color="#FFFFFF" />
                      <Text style={styles.addVariationBtnText}>Add</Text>
                    </TouchableOpacity>
                  </View>

                  {variations.length === 0 ? (
                    <View style={[styles.emptyVariations, { backgroundColor: colors.card }]}>
                      <Ionicons name="layers-outline" size={40} color={colors.text.tertiary} />
                      <Text style={[styles.emptyVariationsText, { color: colors.text.tertiary }]}>
                        No variations added yet
                      </Text>
                      <Text style={[styles.emptyVariationsHint, { color: colors.text.tertiary }]}>
                        Tap "Add" to create variations like 1kg, 3kg, 5kg
                      </Text>
                    </View>
                  ) : (
                    variations.map((variation, index) => (
                      <View key={variation.id} style={[styles.variationCard, { backgroundColor: colors.card }]}>
                        <View style={styles.variationHeader}>
                          <Text style={[styles.variationIndex, { color: colors.primary }]}>#{index + 1}</Text>
                          <TouchableOpacity onPress={() => removeVariation(variation.id)}>
                            <Ionicons name="trash-outline" size={20} color={colors.danger} />
                          </TouchableOpacity>
                        </View>

                        <View style={styles.variationRow}>
                          <View style={[styles.inputGroup, { flex: 1 }]}>
                            <Text style={[styles.inputLabel, { color: colors.text.secondary }]}>Label *</Text>
                            <TextInput
                              style={[styles.input, { backgroundColor: colors.background.secondary, color: colors.text.primary }]}
                              placeholder={variationType === 'weight' ? 'e.g., 1 kg' : 'e.g., Small'}
                              placeholderTextColor={colors.text.tertiary}
                              value={variation.label}
                              onChangeText={(v) => updateVariation(variation.id, 'label', v)}
                            />
                          </View>
                          <View style={{ width: 12 }} />
                          <View style={[styles.inputGroup, { flex: 1 }]}>
                            <Text style={[styles.inputLabel, { color: colors.text.secondary }]}>Value</Text>
                            <TextInput
                              style={[styles.input, { backgroundColor: colors.background.secondary, color: colors.text.primary }]}
                              placeholder="e.g., 1"
                              placeholderTextColor={colors.text.tertiary}
                              value={variation.value}
                              onChangeText={(v) => updateVariation(variation.id, 'value', v)}
                              keyboardType="decimal-pad"
                            />
                          </View>
                        </View>

                        <View style={styles.variationRow}>
                          <View style={[styles.inputGroup, { flex: 1 }]}>
                            <Text style={[styles.inputLabel, { color: colors.text.secondary }]}>Price (₹) *</Text>
                            <TextInput
                              style={[styles.input, { backgroundColor: colors.background.secondary, color: colors.text.primary }]}
                              placeholder="0.00"
                              placeholderTextColor={colors.text.tertiary}
                              value={variation.price}
                              onChangeText={(v) => updateVariation(variation.id, 'price', v)}
                              keyboardType="decimal-pad"
                            />
                          </View>
                          <View style={{ width: 12 }} />
                          <View style={[styles.inputGroup, { flex: 1 }]}>
                            <Text style={[styles.inputLabel, { color: colors.text.secondary }]}>Discounted</Text>
                            <TextInput
                              style={[styles.input, { backgroundColor: colors.background.secondary, color: colors.text.primary }]}
                              placeholder="Optional"
                              placeholderTextColor={colors.text.tertiary}
                              value={variation.discountedPrice}
                              onChangeText={(v) => updateVariation(variation.id, 'discountedPrice', v)}
                              keyboardType="decimal-pad"
                            />
                          </View>
                        </View>

                        {!sharedStock && (
                          <View style={styles.variationRow}>
                            <TouchableOpacity
                              style={[styles.stockToggle, variation.inStock && { backgroundColor: isDark ? 'rgba(48, 209, 88, 0.2)' : '#D1FAE5' }]}
                              onPress={() => updateVariation(variation.id, 'inStock', !variation.inStock)}
                            >
                              <Ionicons
                                name={variation.inStock ? 'checkmark-circle' : 'close-circle'}
                                size={18}
                                color={variation.inStock ? colors.success : colors.danger}
                              />
                              <Text style={[styles.stockToggleText, { color: variation.inStock ? colors.success : colors.danger, fontSize: 12 }]}>
                                {variation.inStock ? 'In Stock' : 'Out'}
                              </Text>
                            </TouchableOpacity>
                            <View style={[styles.inputGroup, { flex: 1, marginLeft: 12 }]}>
                              <Text style={[styles.inputLabel, { color: colors.text.secondary }]}>Stock Qty</Text>
                              <TextInput
                                style={[styles.input, { backgroundColor: colors.background.secondary, color: colors.text.primary }]}
                                placeholder="100"
                                placeholderTextColor={colors.text.tertiary}
                                value={variation.stockQuantity}
                                onChangeText={(v) => updateVariation(variation.id, 'stockQuantity', v)}
                                keyboardType="number-pad"
                              />
                            </View>
                          </View>
                        )}
                      </View>
                    ))
                  )}

                  {/* Shared Stock Option */}
                  {variations.length > 0 && (
                    <TouchableOpacity
                      style={[styles.sharedStockToggle, { backgroundColor: colors.card }]}
                      onPress={() => setSharedStock(!sharedStock)}
                    >
                      <View style={[styles.checkbox, sharedStock && { backgroundColor: colors.primary, borderColor: colors.primary }]}>
                        {sharedStock && <Ionicons name="checkmark" size={14} color="#FFFFFF" />}
                      </View>
                      <View style={styles.sharedStockContent}>
                        <Text style={[styles.sharedStockTitle, { color: colors.text.primary }]}>Use shared stock</Text>
                        <Text style={[styles.sharedStockHint, { color: colors.text.secondary }]}>
                          Single stock quantity for all variations
                        </Text>
                      </View>
                    </TouchableOpacity>
                  )}

                  {sharedStock && (
                    <View style={[styles.card, { backgroundColor: colors.card, marginTop: 12 }]}>
                      <View style={styles.inputGroup}>
                        <Text style={[styles.inputLabel, { color: colors.text.secondary }]}>Total Stock Quantity</Text>
                        <TextInput
                          style={[styles.input, { backgroundColor: colors.background.secondary, color: colors.text.primary }]}
                          placeholder="100"
                          placeholderTextColor={colors.text.tertiary}
                          value={stockQuantity}
                          onChangeText={setStockQuantity}
                          keyboardType="number-pad"
                        />
                      </View>
                    </View>
                  )}
                </View>
              )}
            </>
          )}

          <View style={{ height: 120 }} />
        </ScrollView>
      </KeyboardAvoidingView>

      {/* Submit Button */}
      <View style={[styles.submitContainer, { backgroundColor: colors.card, borderTopColor: colors.separator }]}>
        <TouchableOpacity
          style={[styles.submitBtn, { backgroundColor: colors.primary }, isSubmitting && { opacity: 0.7 }]}
          onPress={handleSubmit}
          disabled={isSubmitting}
        >
          {isSubmitting ? (
            <ActivityIndicator color="#FFFFFF" size="small" />
          ) : (
            <>
              <Ionicons name="add-circle" size={20} color="#FFFFFF" />
              <Text style={styles.submitBtnText}>Add Product ✨</Text>
            </>
          )}
        </TouchableOpacity>
      </View>
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
  progressContainer: {
    height: 3,
  },
  progressBar: {
    height: '100%',
  },
  keyboardView: {
    flex: 1,
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    padding: 16,
  },
  section: {
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 12,
    fontWeight: '600',
    letterSpacing: 0.5,
    marginBottom: 8,
    marginLeft: 4,
  },
  sectionHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  card: {
    borderRadius: 12,
    padding: 16,
  },
  imageContainer: {
    height: 180,
    borderRadius: 12,
    borderWidth: 1,
    borderStyle: 'dashed',
    overflow: 'hidden',
  },
  productImage: {
    width: '100%',
    height: '100%',
  },
  imagePlaceholder: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  imagePlaceholderText: {
    marginTop: 8,
    fontSize: 14,
  },
  inputGroup: {
    marginBottom: 12,
  },
  inputLabel: {
    fontSize: 12,
    fontWeight: '500',
    marginBottom: 6,
  },
  input: {
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 16,
  },
  textArea: {
    height: 80,
    textAlignVertical: 'top',
  },
  categoryScroll: {
    marginHorizontal: -16,
    paddingHorizontal: 16,
  },
  categoryChip: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 20,
    marginRight: 8,
    borderWidth: 1,
  },
  categoryChipText: {
    fontSize: 13,
    fontWeight: '500',
    marginLeft: 6,
  },
  subcategoryGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    padding: 12,
    borderRadius: 12,
    gap: 8,
  },
  subcategoryChip: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
  },
  subcategoryChipText: {
    fontSize: 13,
  },
  typeToggle: {
    flexDirection: 'row',
    borderRadius: 12,
    padding: 4,
  },
  typeOption: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    borderRadius: 10,
    gap: 8,
  },
  typeOptionText: {
    fontSize: 14,
    fontWeight: '600',
  },
  priceRow: {
    flexDirection: 'row',
  },
  stockRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    marginTop: 4,
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
  variationTypeGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  variationTypeCard: {
    width: '48%',
    padding: 16,
    borderRadius: 12,
    alignItems: 'center',
    borderWidth: 1,
  },
  variationTypeLabel: {
    fontSize: 13,
    fontWeight: '600',
    marginTop: 8,
  },
  unitRow: {
    flexDirection: 'row',
    gap: 8,
  },
  unitChip: {
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 20,
    borderWidth: 1,
  },
  unitChipText: {
    fontSize: 14,
    fontWeight: '600',
  },
  addVariationBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    gap: 4,
  },
  addVariationBtnText: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: '600',
  },
  emptyVariations: {
    padding: 32,
    borderRadius: 12,
    alignItems: 'center',
  },
  emptyVariationsText: {
    fontSize: 15,
    fontWeight: '500',
    marginTop: 12,
  },
  emptyVariationsHint: {
    fontSize: 13,
    marginTop: 4,
    textAlign: 'center',
  },
  variationCard: {
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
  },
  variationHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  variationIndex: {
    fontSize: 14,
    fontWeight: '700',
  },
  variationRow: {
    flexDirection: 'row',
    marginBottom: 8,
  },
  sharedStockToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    borderRadius: 12,
    marginTop: 12,
  },
  checkbox: {
    width: 22,
    height: 22,
    borderRadius: 6,
    borderWidth: 2,
    borderColor: '#D1D5DB',
    justifyContent: 'center',
    alignItems: 'center',
  },
  sharedStockContent: {
    marginLeft: 12,
  },
  sharedStockTitle: {
    fontSize: 15,
    fontWeight: '600',
  },
  sharedStockHint: {
    fontSize: 12,
    marginTop: 2,
  },
  submitContainer: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    padding: 16,
    paddingBottom: 32,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  submitBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 16,
    borderRadius: 12,
    gap: 8,
  },
  submitBtnText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
});
