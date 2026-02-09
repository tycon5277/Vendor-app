import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Switch,
  Image,
  Modal,
  Platform,
  Animated,
  Dimensions,
  Alert,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import * as Location from 'expo-location';
import { WebView } from 'react-native-webview';
import { vendorAPI } from '../../src/utils/api';
import { useAuthStore } from '../../src/store/authStore';
import { useAlert } from '../../src/context/AlertContext';

const { width: SCREEN_WIDTH, height: SCREEN_HEIGHT } = Dimensions.get('window');

// Shop types with icons
const SHOP_TYPES = [
  { id: 'Grocery', name: 'Grocery', icon: 'cart' },
  { id: 'Restaurant', name: 'Restaurant', icon: 'restaurant' },
  { id: 'Pharmacy', name: 'Pharmacy', icon: 'medkit' },
  { id: 'Electronics', name: 'Electronics', icon: 'phone-portrait' },
  { id: 'Fashion', name: 'Fashion', icon: 'shirt' },
  { id: 'Bakery', name: 'Bakery', icon: 'cafe' },
  { id: 'Farm Produce', name: 'Farm Produce', icon: 'leaf' },
  { id: 'Fish & Seafood', name: 'Fish & Seafood', icon: 'fish' },
  { id: 'Nursery & Plants', name: 'Plants', icon: 'flower' },
  { id: 'Hardware', name: 'Hardware', icon: 'hammer' },
  { id: 'Stationery', name: 'Stationery', icon: 'pencil' },
  { id: 'Supermarket', name: 'Supermarket', icon: 'storefront' },
  { id: 'Sweet Shop', name: 'Sweets', icon: 'ice-cream' },
  { id: 'Dairy', name: 'Dairy', icon: 'water' },
  { id: 'Meat Shop', name: 'Meat', icon: 'nutrition' },
  { id: 'Other', name: 'Other', icon: 'ellipsis-horizontal' },
];

// Description examples based on shop type
const DESCRIPTION_EXAMPLES: Record<string, string> = {
  'Grocery': 'Your neighborhood grocery store with fresh produce, daily essentials, and household items at competitive prices. We offer home delivery within 2km radius.',
  'Restaurant': 'Authentic home-style cooking with a variety of cuisines. Specializing in North Indian dishes, Chinese fusion, and quick bites. Dine-in and takeaway available.',
  'Pharmacy': '24/7 pharmacy with all prescription medicines, OTC drugs, and healthcare products. Licensed pharmacist available for consultation.',
  'Electronics': 'One-stop shop for mobile phones, accessories, repair services, and electronics. Authorized service center for major brands.',
  'Fashion': 'Trendy clothing and accessories for men, women, and kids. Latest collections, seasonal discounts, and alterations available.',
  'Bakery': 'Freshly baked bread, cakes, pastries, and confectioneries. Custom cake orders for birthdays and celebrations. Using premium ingredients.',
  'Farm Produce': 'Farm-fresh fruits, vegetables, and organic produce directly from local farmers. Daily fresh stock with seasonal specialties.',
  'Fish & Seafood': 'Fresh catch daily! Premium quality fish, prawns, crabs, and seafood. Cleaning and cutting services available.',
  'Nursery & Plants': 'Beautiful indoor and outdoor plants, gardening supplies, fertilizers, and pots. Expert advice for plant care and landscaping.',
  'Hardware': 'Complete hardware solutions - tools, paints, plumbing, electrical supplies, and construction materials. Bulk orders welcome.',
  'Stationery': 'School and office supplies, art materials, gift items, and printing services. Back-to-school special offers available.',
  'Supermarket': 'Wide range of groceries, fresh produce, dairy, beverages, and household items under one roof. Weekly deals and membership benefits.',
  'Sweet Shop': 'Traditional Indian sweets, savories, and snacks made fresh daily. Perfect for festivals, celebrations, and gifting.',
  'Dairy': 'Fresh milk, curd, paneer, ghee, and dairy products delivered daily. Farm-fresh quality guaranteed.',
  'Meat Shop': 'Halal certified fresh meat - chicken, mutton, and beef. Hygienically processed with custom cutting options.',
  'Other': 'Describe your shop and what makes it special. Mention your products, services, and any unique offerings.',
};

// Time options for picker
const HOURS = Array.from({ length: 24 }, (_, i) => i.toString().padStart(2, '0'));
const MINUTES = ['00', '15', '30', '45'];

interface TimePickerModalProps {
  visible: boolean;
  onClose: () => void;
  onSelect: (time: string) => void;
  title: string;
  initialTime?: string;
}

const TimePickerModal: React.FC<TimePickerModalProps> = ({
  visible,
  onClose,
  onSelect,
  title,
  initialTime = '09:00',
}) => {
  const [selectedHour, setSelectedHour] = useState(initialTime.split(':')[0] || '09');
  const [selectedMinute, setSelectedMinute] = useState(initialTime.split(':')[1] || '00');

  const formatTime = (hour: string, minute: string) => {
    const h = parseInt(hour);
    const ampm = h >= 12 ? 'PM' : 'AM';
    const displayHour = h === 0 ? 12 : h > 12 ? h - 12 : h;
    return `${displayHour}:${minute} ${ampm}`;
  };

  return (
    <Modal visible={visible} transparent animationType="slide">
      <View style={styles.modalOverlay}>
        <View style={styles.modalContent}>
          <Text style={styles.modalTitle}>{title}</Text>
          
          <View style={styles.timePickerContainer}>
            {/* Hour Picker */}
            <View style={styles.pickerColumn}>
              <Text style={styles.pickerLabel}>Hour</Text>
              <ScrollView style={styles.pickerScroll} showsVerticalScrollIndicator={false}>
                {HOURS.map((hour) => (
                  <TouchableOpacity
                    key={hour}
                    style={[
                      styles.pickerItem,
                      selectedHour === hour && styles.pickerItemSelected,
                    ]}
                    onPress={() => setSelectedHour(hour)}
                  >
                    <Text
                      style={[
                        styles.pickerItemText,
                        selectedHour === hour && styles.pickerItemTextSelected,
                      ]}
                    >
                      {hour}
                    </Text>
                  </TouchableOpacity>
                ))}
              </ScrollView>
            </View>

            <Text style={styles.timeSeparator}>:</Text>

            {/* Minute Picker */}
            <View style={styles.pickerColumn}>
              <Text style={styles.pickerLabel}>Min</Text>
              <ScrollView style={styles.pickerScroll} showsVerticalScrollIndicator={false}>
                {MINUTES.map((minute) => (
                  <TouchableOpacity
                    key={minute}
                    style={[
                      styles.pickerItem,
                      selectedMinute === minute && styles.pickerItemSelected,
                    ]}
                    onPress={() => setSelectedMinute(minute)}
                  >
                    <Text
                      style={[
                        styles.pickerItemText,
                        selectedMinute === minute && styles.pickerItemTextSelected,
                      ]}
                    >
                      {minute}
                    </Text>
                  </TouchableOpacity>
                ))}
              </ScrollView>
            </View>
          </View>

          <View style={styles.selectedTimeDisplay}>
            <Ionicons name="time" size={24} color="#6366F1" />
            <Text style={styles.selectedTimeText}>
              {formatTime(selectedHour, selectedMinute)}
            </Text>
          </View>

          <View style={styles.modalButtons}>
            <TouchableOpacity style={styles.modalCancelBtn} onPress={onClose}>
              <Text style={styles.modalCancelText}>Cancel</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.modalConfirmBtn}
              onPress={() => {
                onSelect(`${selectedHour}:${selectedMinute}`);
                onClose();
              }}
            >
              <Text style={styles.modalConfirmText}>Confirm</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
};

export default function RegisterScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { setUser, user } = useAuthStore();
  const { showAlert } = useAlert();
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState(1);
  const [showOpeningTimePicker, setShowOpeningTimePicker] = useState(false);
  const [showClosingTimePicker, setShowClosingTimePicker] = useState(false);
  const [showMapModal, setShowMapModal] = useState(false);
  const [tempMapLocation, setTempMapLocation] = useState<{ lat: number; lng: number } | null>(null);
  const mapRef = useRef<MapView>(null);

  const [formData, setFormData] = useState({
    name: user?.name || '',
    shop_name: '',
    shop_type: '',
    custom_shop_type: '',
    shop_address: '',
    shop_location: null as { lat: number; lng: number } | null,
    can_deliver: false,
    opening_time: '09:00',
    closing_time: '21:00',
    description: '',
    shop_image: null as string | null,
    gst_number: '',
    license_number: '',
    fssai_number: '',
  });

  // Calculate progress percentage
  const getProgress = () => {
    let progress = 0;
    if (formData.name) progress += 10;
    if (formData.shop_name) progress += 15;
    if (formData.shop_type) progress += 15;
    if (formData.shop_address) progress += 15;
    if (formData.opening_time && formData.closing_time) progress += 15;
    if (formData.description) progress += 15;
    if (formData.shop_image) progress += 15;
    return Math.min(progress, 100);
  };

  const formatTimeDisplay = (time: string) => {
    const [hour, minute] = time.split(':');
    const h = parseInt(hour);
    const ampm = h >= 12 ? 'PM' : 'AM';
    const displayHour = h === 0 ? 12 : h > 12 ? h - 12 : h;
    return `${displayHour}:${minute} ${ampm}`;
  };

  const getCurrentLocation = async () => {
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        showAlert({
          type: 'error',
          title: 'Permission Denied',
          message: 'Location permission is required to capture your shop location.',
        });
        return;
      }

      const location = await Location.getCurrentPositionAsync({});
      const coords = {
        lat: location.coords.latitude,
        lng: location.coords.longitude,
      };
      setTempMapLocation(coords);
      setShowMapModal(true);
    } catch (error) {
      showAlert({
        type: 'error',
        title: 'Error',
        message: 'Failed to get location. Please try again.',
      });
    }
  };

  const openMapForManualSelection = async () => {
    // Default to Bangalore if no location is set
    const defaultLocation = formData.shop_location || { lat: 12.9716, lng: 77.5946 };
    setTempMapLocation(defaultLocation);
    setShowMapModal(true);
  };

  const confirmMapLocation = () => {
    if (tempMapLocation) {
      setFormData((prev) => ({
        ...prev,
        shop_location: tempMapLocation,
      }));
      showAlert({
        type: 'success',
        title: 'Location Saved! 📍',
        message: 'Your shop location has been pinned on the map.',
      });
    }
    setShowMapModal(false);
  };

  const pickImage = async () => {
    try {
      const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Permission Denied', 'Gallery permission is required');
        return;
      }

      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: true,
        aspect: [16, 9],
        quality: 0.5,
        base64: true,
      });

      if (!result.canceled && result.assets[0].base64) {
        setFormData((prev) => ({
          ...prev,
          shop_image: `data:image/jpeg;base64,${result.assets[0].base64}`,
        }));
      }
    } catch (error) {
      showAlert({
        type: 'error',
        title: 'Oops!',
        message: 'Failed to pick image. Please try again.',
      });
    }
  };

  const handleRegister = async () => {
    if (!formData.name || !formData.shop_name || !formData.shop_type || !formData.shop_address) {
      showAlert({
        type: 'warning',
        title: 'Missing Information',
        message: 'Please fill all required fields to continue.',
      });
      return;
    }

    if (!formData.description) {
      showAlert({
        type: 'warning',
        title: 'Missing Description',
        message: 'Please add a description for your shop.',
      });
      return;
    }

    setLoading(true);
    try {
      const response = await vendorAPI.register(formData);
      setUser(response.data.user);
      showAlert({
        type: 'success',
        title: 'Congratulations! 🎉',
        message: 'Your shop is now registered! Time to start selling.',
        buttons: [
          { text: 'Start Selling', onPress: () => router.replace('/(main)/home') },
        ],
      });
    } catch (error: any) {
      console.error('Register Error:', error);
      showAlert({
        type: 'error',
        title: 'Registration Failed',
        message: error.response?.data?.detail || 'Something went wrong. Please try again.',
      });
    } finally {
      setLoading(false);
    }
  };

  // Step 1: Owner & Shop Info with Shop Type Grid
  const renderStep1 = () => (
    <View style={styles.stepContainer}>
      <View style={styles.stepHeader}>
        <View style={styles.stepBadge}>
          <Ionicons name="person" size={20} color="#FFFFFF" />
        </View>
        <Text style={styles.stepTitle}>Let's Get Started!</Text>
        <Text style={styles.stepSubtitle}>Tell us about you and your shop</Text>
      </View>

      <View style={styles.inputGroup}>
        <Text style={styles.label}>Your Name</Text>
        <View style={styles.inputWithIcon}>
          <Ionicons name="person-outline" size={20} color="#9CA3AF" />
          <TextInput
            style={styles.inputField}
            placeholder="Enter your full name"
            placeholderTextColor="#9CA3AF"
            value={formData.name}
            onChangeText={(text) => setFormData((prev) => ({ ...prev, name: text }))}
          />
          {formData.name && <Ionicons name="checkmark-circle" size={20} color="#22C55E" />}
        </View>
      </View>

      <View style={styles.inputGroup}>
        <Text style={styles.label}>Shop Name</Text>
        <View style={styles.inputWithIcon}>
          <Ionicons name="storefront-outline" size={20} color="#9CA3AF" />
          <TextInput
            style={styles.inputField}
            placeholder="What's your shop called?"
            placeholderTextColor="#9CA3AF"
            value={formData.shop_name}
            onChangeText={(text) => setFormData((prev) => ({ ...prev, shop_name: text }))}
          />
          {formData.shop_name && <Ionicons name="checkmark-circle" size={20} color="#22C55E" />}
        </View>
      </View>

      <View style={styles.inputGroup}>
        <Text style={styles.label}>What do you sell?</Text>
        <Text style={styles.labelHint}>Select your shop type</Text>
        <View style={styles.shopTypeGrid}>
          {SHOP_TYPES.map((type) => (
            <TouchableOpacity
              key={type.id}
              style={[
                styles.shopTypeCard,
                formData.shop_type === type.id && styles.shopTypeCardSelected,
              ]}
              onPress={() => setFormData((prev) => ({ ...prev, shop_type: type.id }))}
            >
              <View
                style={[
                  styles.shopTypeIconContainer,
                  formData.shop_type === type.id && styles.shopTypeIconContainerSelected,
                ]}
              >
                <Ionicons
                  name={type.icon as any}
                  size={24}
                  color={formData.shop_type === type.id ? '#FFFFFF' : '#6366F1'}
                />
              </View>
              <Text
                style={[
                  styles.shopTypeText,
                  formData.shop_type === type.id && styles.shopTypeTextSelected,
                ]}
                numberOfLines={1}
              >
                {type.name}
              </Text>
              {formData.shop_type === type.id && (
                <View style={styles.shopTypeCheck}>
                  <Ionicons name="checkmark" size={12} color="#FFFFFF" />
                </View>
              )}
            </TouchableOpacity>
          ))}
        </View>

        {formData.shop_type === 'Other' && (
          <View style={[styles.inputWithIcon, { marginTop: 12 }]}>
            <Ionicons name="create-outline" size={20} color="#9CA3AF" />
            <TextInput
              style={styles.inputField}
              placeholder="Enter your shop type"
              placeholderTextColor="#9CA3AF"
              value={formData.custom_shop_type}
              onChangeText={(text) => setFormData((prev) => ({ ...prev, custom_shop_type: text }))}
            />
          </View>
        )}
      </View>

      <TouchableOpacity
        style={[
          styles.continueButton,
          (!formData.name || !formData.shop_name || !formData.shop_type) && styles.continueButtonDisabled,
        ]}
        onPress={() => {
          if (formData.name && formData.shop_name && formData.shop_type) {
            setStep(2);
          } else {
            Alert.alert('Missing Information', 'Please fill all fields');
          }
        }}
        disabled={!formData.name || !formData.shop_name || !formData.shop_type}
      >
        <Text style={styles.continueButtonText}>Continue</Text>
        <Ionicons name="arrow-forward" size={20} color="#FFFFFF" />
      </TouchableOpacity>
    </View>
  );

  // Step 2: Location & Operating Hours
  const renderStep2 = () => (
    <View style={styles.stepContainer}>
      <View style={styles.stepHeader}>
        <View style={[styles.stepBadge, { backgroundColor: '#22C55E' }]}>
          <Ionicons name="location" size={20} color="#FFFFFF" />
        </View>
        <Text style={styles.stepTitle}>Where's Your Shop?</Text>
        <Text style={styles.stepSubtitle}>Help customers find you</Text>
      </View>

      <View style={styles.inputGroup}>
        <Text style={styles.label}>Shop Address</Text>
        <TextInput
          style={styles.textArea}
          placeholder="Enter complete address with landmarks"
          placeholderTextColor="#9CA3AF"
          multiline
          numberOfLines={3}
          value={formData.shop_address}
          onChangeText={(text) => setFormData((prev) => ({ ...prev, shop_address: text }))}
        />
      </View>

      <TouchableOpacity style={styles.locationButton} onPress={getCurrentLocation}>
        <View style={styles.locationIconContainer}>
          <Ionicons name="locate" size={24} color="#6366F1" />
        </View>
        <View style={styles.locationTextContainer}>
          <Text style={styles.locationButtonTitle}>
            {formData.shop_location ? 'Location Captured!' : 'Get Current Location'}
          </Text>
          <Text style={styles.locationButtonSubtitle}>
            {formData.shop_location
              ? `Lat: ${formData.shop_location.lat.toFixed(4)}, Lng: ${formData.shop_location.lng.toFixed(4)}`
              : 'Tap to detect your shop location'}
          </Text>
        </View>
        {formData.shop_location ? (
          <Ionicons name="checkmark-circle" size={28} color="#22C55E" />
        ) : (
          <Ionicons name="chevron-forward" size={24} color="#9CA3AF" />
        )}
      </TouchableOpacity>

      {/* Map Preview Tile */}
      <View style={styles.mapPreviewContainer}>
        <Text style={styles.mapPreviewLabel}>
          {formData.shop_location ? 'Pin your exact location' : 'Or select manually on map'}
        </Text>
        <TouchableOpacity 
          style={styles.mapPreviewTile}
          onPress={openMapForManualSelection}
          activeOpacity={0.9}
        >
          {formData.shop_location ? (
            <Image
              source={{
                uri: `https://maps.googleapis.com/maps/api/staticmap?center=${formData.shop_location.lat},${formData.shop_location.lng}&zoom=16&size=400x200&markers=color:purple%7C${formData.shop_location.lat},${formData.shop_location.lng}&key=AIzaSyBDaeWicvigtP9xPv919E-RNoxfvC-Hrqg`
              }}
              style={styles.mapPreview}
              resizeMode="cover"
            />
          ) : (
            <View style={styles.mapPlaceholder}>
              <Ionicons name="map-outline" size={48} color="#D1D5DB" />
              <Text style={styles.mapPlaceholderText}>Tap to select location on map</Text>
            </View>
          )}
          <View style={styles.mapOverlay}>
            <View style={styles.mapEditBadge}>
              <Ionicons name="pencil" size={14} color="#FFFFFF" />
              <Text style={styles.mapEditText}>
                {formData.shop_location ? 'Adjust Pin' : 'Select Location'}
              </Text>
            </View>
          </View>
        </TouchableOpacity>
      </View>

      {/* Operating Hours */}
      <View style={styles.operatingHoursSection}>
        <Text style={styles.sectionTitle}>Operating Hours</Text>
        <Text style={styles.sectionSubtitle}>When is your shop open?</Text>

        <View style={styles.timePickersRow}>
          <TouchableOpacity
            style={styles.timePickerButton}
            onPress={() => setShowOpeningTimePicker(true)}
          >
            <View style={styles.timePickerIcon}>
              <Ionicons name="sunny" size={24} color="#F59E0B" />
            </View>
            <View style={styles.timePickerContent}>
              <Text style={styles.timePickerLabel}>Opens At</Text>
              <Text style={styles.timePickerValue}>{formatTimeDisplay(formData.opening_time)}</Text>
            </View>
            <Ionicons name="chevron-down" size={20} color="#6366F1" />
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.timePickerButton}
            onPress={() => setShowClosingTimePicker(true)}
          >
            <View style={styles.timePickerIcon}>
              <Ionicons name="moon" size={24} color="#6366F1" />
            </View>
            <View style={styles.timePickerContent}>
              <Text style={styles.timePickerLabel}>Closes At</Text>
              <Text style={styles.timePickerValue}>{formatTimeDisplay(formData.closing_time)}</Text>
            </View>
            <Ionicons name="chevron-down" size={20} color="#6366F1" />
          </TouchableOpacity>
        </View>
      </View>

      <View style={styles.deliveryToggleCard}>
        <View style={styles.deliveryToggleLeft}>
          <Ionicons name="bicycle" size={28} color="#6366F1" />
          <View style={styles.deliveryToggleText}>
            <Text style={styles.deliveryToggleTitle}>Own Delivery</Text>
            <Text style={styles.deliveryToggleSubtitle}>We deliver to customers</Text>
          </View>
        </View>
        <Switch
          value={formData.can_deliver}
          onValueChange={(value) => setFormData((prev) => ({ ...prev, can_deliver: value }))}
          trackColor={{ false: '#E5E7EB', true: '#A5B4FC' }}
          thumbColor={formData.can_deliver ? '#6366F1' : '#9CA3AF'}
        />
      </View>

      <View style={styles.navigationButtons}>
        <TouchableOpacity style={styles.backButton} onPress={() => setStep(1)}>
          <Ionicons name="arrow-back" size={20} color="#6366F1" />
          <Text style={styles.backButtonText}>Back</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.continueButton, { flex: 1 }, !formData.shop_address && styles.continueButtonDisabled]}
          onPress={() => {
            if (formData.shop_address) {
              setStep(3);
            } else {
              Alert.alert('Missing Information', 'Please enter shop address');
            }
          }}
          disabled={!formData.shop_address}
        >
          <Text style={styles.continueButtonText}>Continue</Text>
          <Ionicons name="arrow-forward" size={20} color="#FFFFFF" />
        </TouchableOpacity>
      </View>

      <TimePickerModal
        visible={showOpeningTimePicker}
        onClose={() => setShowOpeningTimePicker(false)}
        onSelect={(time) => setFormData((prev) => ({ ...prev, opening_time: time }))}
        title="Opening Time"
        initialTime={formData.opening_time}
      />

      <TimePickerModal
        visible={showClosingTimePicker}
        onClose={() => setShowClosingTimePicker(false)}
        onSelect={(time) => setFormData((prev) => ({ ...prev, closing_time: time }))}
        title="Closing Time"
        initialTime={formData.closing_time}
      />
    </View>
  );

  // Step 3: Business Details & Description
  const renderStep3 = () => {
    const descriptionExample = DESCRIPTION_EXAMPLES[formData.shop_type] || DESCRIPTION_EXAMPLES['Other'];

    return (
      <View style={styles.stepContainer}>
        <View style={styles.stepHeader}>
          <View style={[styles.stepBadge, { backgroundColor: '#EC4899' }]}>
            <Ionicons name="document-text" size={20} color="#FFFFFF" />
          </View>
          <Text style={styles.stepTitle}>Almost Done!</Text>
          <Text style={styles.stepSubtitle}>Add final details about your shop</Text>
        </View>

        {/* Shop Image */}
        <TouchableOpacity style={styles.imagePickerLarge} onPress={pickImage}>
          {formData.shop_image ? (
            <Image source={{ uri: formData.shop_image }} style={styles.shopImageLarge} />
          ) : (
            <View style={styles.imagePlaceholderLarge}>
              <View style={styles.cameraIconContainer}>
                <Ionicons name="camera" size={32} color="#6366F1" />
              </View>
              <Text style={styles.imagePlaceholderTitle}>Add Shop Photo</Text>
              <Text style={styles.imagePlaceholderSubtitle}>Help customers recognize your shop</Text>
            </View>
          )}
          {formData.shop_image && (
            <View style={styles.imageEditBadge}>
              <Ionicons name="pencil" size={16} color="#FFFFFF" />
            </View>
          )}
        </TouchableOpacity>

        {/* Business Registration */}
        <View style={styles.businessSection}>
          <Text style={styles.sectionTitle}>Business Registration</Text>
          <Text style={styles.sectionSubtitle}>Optional but helps build trust</Text>

          <View style={styles.businessInputRow}>
            <View style={styles.businessInput}>
              <Text style={styles.businessInputLabel}>GST Number</Text>
              <TextInput
                style={styles.businessInputField}
                placeholder="22AAAAA0000A1Z5"
                placeholderTextColor="#D1D5DB"
                value={formData.gst_number}
                onChangeText={(text) => setFormData((prev) => ({ ...prev, gst_number: text.toUpperCase() }))}
                autoCapitalize="characters"
              />
            </View>
            <View style={styles.businessInput}>
              <Text style={styles.businessInputLabel}>License No.</Text>
              <TextInput
                style={styles.businessInputField}
                placeholder="LIC123456"
                placeholderTextColor="#D1D5DB"
                value={formData.license_number}
                onChangeText={(text) => setFormData((prev) => ({ ...prev, license_number: text.toUpperCase() }))}
                autoCapitalize="characters"
              />
            </View>
          </View>

          {['Restaurant', 'Bakery', 'Sweet Shop', 'Dairy', 'Meat Shop', 'Fish & Seafood'].includes(formData.shop_type) && (
            <View style={styles.fssaiInput}>
              <Text style={styles.businessInputLabel}>FSSAI License (Food Business)</Text>
              <TextInput
                style={styles.businessInputField}
                placeholder="14 digit FSSAI number"
                placeholderTextColor="#D1D5DB"
                value={formData.fssai_number}
                onChangeText={(text) => setFormData((prev) => ({ ...prev, fssai_number: text }))}
                keyboardType="numeric"
                maxLength={14}
              />
            </View>
          )}
        </View>

        {/* Description */}
        <View style={styles.descriptionSection}>
          <Text style={styles.sectionTitle}>Shop Description</Text>
          <Text style={styles.descriptionRequired}>
            <Ionicons name="star" size={12} color="#DC2626" /> Required
          </Text>
          
          <TextInput
            style={styles.descriptionInput}
            placeholder="Describe your shop..."
            placeholderTextColor="#9CA3AF"
            multiline
            numberOfLines={5}
            value={formData.description}
            onChangeText={(text) => setFormData((prev) => ({ ...prev, description: text }))}
          />

          <View style={styles.exampleContainer}>
            <View style={styles.exampleHeader}>
              <Ionicons name="bulb" size={16} color="#F59E0B" />
              <Text style={styles.exampleTitle}>Example for {formData.shop_type}:</Text>
            </View>
            <Text style={styles.exampleText}>{descriptionExample}</Text>
            <TouchableOpacity
              style={styles.useExampleButton}
              onPress={() => setFormData((prev) => ({ ...prev, description: descriptionExample }))}
            >
              <Text style={styles.useExampleButtonText}>Use This Example</Text>
            </TouchableOpacity>
          </View>
        </View>

        <View style={styles.navigationButtons}>
          <TouchableOpacity style={styles.backButton} onPress={() => setStep(2)}>
            <Ionicons name="arrow-back" size={20} color="#6366F1" />
            <Text style={styles.backButtonText}>Back</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.registerButton, loading && styles.registerButtonDisabled]}
            onPress={handleRegister}
            disabled={loading}
          >
            <Ionicons name="rocket" size={20} color="#FFFFFF" />
            <Text style={styles.registerButtonText}>
              {loading ? 'Creating Shop...' : 'Launch My Shop'}
            </Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  };

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      {/* Progress Bar */}
      <View style={styles.progressSection}>
        <View style={styles.progressHeader}>
          <Text style={styles.progressTitle}>Register Your Shop</Text>
          <Text style={styles.progressPercent}>{getProgress()}%</Text>
        </View>
        <View style={styles.progressBarBg}>
          <View style={[styles.progressBarFill, { width: `${getProgress()}%` }]} />
        </View>
        <View style={styles.stepsIndicator}>
          {[1, 2, 3].map((s) => (
            <View key={s} style={styles.stepIndicatorItem}>
              <View
                style={[
                  styles.stepDot,
                  s < step && styles.stepDotCompleted,
                  s === step && styles.stepDotActive,
                ]}
              >
                {s < step ? (
                  <Ionicons name="checkmark" size={14} color="#FFFFFF" />
                ) : (
                  <Text style={[styles.stepDotText, s === step && styles.stepDotTextActive]}>{s}</Text>
                )}
              </View>
              <Text style={[styles.stepLabel, s === step && styles.stepLabelActive]}>
                {s === 1 ? 'Basics' : s === 2 ? 'Location' : 'Details'}
              </Text>
            </View>
          ))}
        </View>
      </View>

      <ScrollView style={styles.scrollView} showsVerticalScrollIndicator={false}>
        {step === 1 && renderStep1()}
        {step === 2 && renderStep2()}
        {step === 3 && renderStep3()}
        <View style={{ height: 40 }} />
      </ScrollView>

      {/* Full Screen Map Modal with Draggable Pin */}
      <Modal
        visible={showMapModal}
        animationType="slide"
        onRequestClose={() => setShowMapModal(false)}
      >
        <View style={styles.mapModalContainer}>
          {/* Header */}
          <View style={[styles.mapModalHeader, { paddingTop: insets.top + 10 }]}>
            <TouchableOpacity 
              style={styles.mapModalBackBtn}
              onPress={() => setShowMapModal(false)}
            >
              <Ionicons name="close" size={24} color="#374151" />
            </TouchableOpacity>
            <View style={styles.mapModalTitleContainer}>
              <Text style={styles.mapModalTitle}>Pin Your Location</Text>
              <Text style={styles.mapModalSubtitle}>Tap on map to place marker</Text>
            </View>
            <View style={{ width: 44 }} />
          </View>

          {/* WebView Map */}
          {tempMapLocation && (
            <WebView
              style={styles.fullMap}
              originWhitelist={['*']}
              onMessage={(event) => {
                try {
                  const data = JSON.parse(event.nativeEvent.data);
                  if (data.lat && data.lng) {
                    setTempMapLocation({ lat: data.lat, lng: data.lng });
                  }
                } catch (e) {}
              }}
              source={{
                html: `
                  <!DOCTYPE html>
                  <html>
                  <head>
                    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
                    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
                    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
                    <style>
                      * { margin: 0; padding: 0; box-sizing: border-box; }
                      html, body, #map { width: 100%; height: 100%; }
                      .custom-marker {
                        background: #6366F1;
                        border-radius: 50%;
                        width: 40px;
                        height: 40px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        border: 3px solid white;
                        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                      }
                      .custom-marker svg { fill: white; width: 20px; height: 20px; }
                    </style>
                  </head>
                  <body>
                    <div id="map"></div>
                    <script>
                      var map = L.map('map').setView([${tempMapLocation.lat}, ${tempMapLocation.lng}], 16);
                      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                        attribution: '© OpenStreetMap'
                      }).addTo(map);
                      
                      var markerIcon = L.divIcon({
                        className: 'custom-marker-container',
                        html: '<div class="custom-marker"><svg viewBox="0 0 24 24"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/></svg></div>',
                        iconSize: [40, 40],
                        iconAnchor: [20, 40]
                      });
                      
                      var marker = L.marker([${tempMapLocation.lat}, ${tempMapLocation.lng}], { 
                        icon: markerIcon,
                        draggable: true 
                      }).addTo(map);
                      
                      marker.on('dragend', function(e) {
                        var pos = e.target.getLatLng();
                        window.ReactNativeWebView.postMessage(JSON.stringify({ lat: pos.lat, lng: pos.lng }));
                      });
                      
                      map.on('click', function(e) {
                        marker.setLatLng(e.latlng);
                        window.ReactNativeWebView.postMessage(JSON.stringify({ lat: e.latlng.lat, lng: e.latlng.lng }));
                      });
                    </script>
                  </body>
                  </html>
                `
              }}
            />
          )}

          {/* Instructions */}
          <View style={styles.mapInstructions}>
            <Ionicons name="hand-left" size={20} color="#6366F1" />
            <Text style={styles.mapInstructionText}>
              Tap on map or drag marker to set location
            </Text>
          </View>

          {/* Coordinates Display */}
          {tempMapLocation && (
            <View style={styles.coordinatesDisplay}>
              <Text style={styles.coordinatesLabel}>Selected Coordinates</Text>
              <Text style={styles.coordinatesValue}>
                {tempMapLocation.lat.toFixed(6)}, {tempMapLocation.lng.toFixed(6)}
              </Text>
            </View>
          )}

          {/* Confirm Button */}
          <View style={[styles.mapModalFooter, { paddingBottom: insets.bottom + 16 }]}>
            <TouchableOpacity 
              style={styles.mapModalCancelBtn}
              onPress={() => setShowMapModal(false)}
            >
              <Text style={styles.mapModalCancelText}>Cancel</Text>
            </TouchableOpacity>
            <TouchableOpacity 
              style={styles.mapModalConfirmBtn}
              onPress={confirmMapLocation}
            >
              <Ionicons name="checkmark" size={20} color="#FFFFFF" />
              <Text style={styles.mapModalConfirmText}>Confirm Location</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F9FAFB',
  },
  progressSection: {
    backgroundColor: '#FFFFFF',
    paddingHorizontal: 20,
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  progressHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  progressTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#111827',
  },
  progressPercent: {
    fontSize: 16,
    fontWeight: '700',
    color: '#6366F1',
  },
  progressBarBg: {
    height: 8,
    backgroundColor: '#E5E7EB',
    borderRadius: 4,
    overflow: 'hidden',
  },
  progressBarFill: {
    height: '100%',
    backgroundColor: '#6366F1',
    borderRadius: 4,
  },
  stepsIndicator: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 16,
  },
  stepIndicatorItem: {
    alignItems: 'center',
    flex: 1,
  },
  stepDot: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: '#E5E7EB',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 4,
  },
  stepDotCompleted: {
    backgroundColor: '#22C55E',
  },
  stepDotActive: {
    backgroundColor: '#6366F1',
  },
  stepDotText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#9CA3AF',
  },
  stepDotTextActive: {
    color: '#FFFFFF',
  },
  stepLabel: {
    fontSize: 11,
    color: '#9CA3AF',
    fontWeight: '500',
  },
  stepLabelActive: {
    color: '#6366F1',
    fontWeight: '600',
  },
  scrollView: {
    flex: 1,
  },
  stepContainer: {
    padding: 20,
  },
  stepHeader: {
    alignItems: 'center',
    marginBottom: 24,
  },
  stepBadge: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: '#6366F1',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 12,
  },
  stepTitle: {
    fontSize: 22,
    fontWeight: '700',
    color: '#111827',
  },
  stepSubtitle: {
    fontSize: 14,
    color: '#6B7280',
    marginTop: 4,
  },
  inputGroup: {
    marginBottom: 20,
  },
  label: {
    fontSize: 14,
    fontWeight: '600',
    color: '#374151',
    marginBottom: 8,
  },
  labelHint: {
    fontSize: 12,
    color: '#9CA3AF',
    marginBottom: 12,
  },
  inputWithIcon: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#E5E7EB',
    paddingHorizontal: 14,
    height: 52,
    gap: 10,
  },
  inputField: {
    flex: 1,
    fontSize: 16,
    color: '#111827',
  },
  textArea: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#E5E7EB',
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 16,
    color: '#111827',
    minHeight: 100,
    textAlignVertical: 'top',
  },
  shopTypeGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginHorizontal: -6,
  },
  shopTypeCard: {
    width: '25%',
    padding: 6,
  },
  shopTypeCardSelected: {},
  shopTypeIconContainer: {
    width: '100%',
    aspectRatio: 1,
    backgroundColor: '#EEF2FF',
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 2,
    borderColor: '#E5E7EB',
  },
  shopTypeIconContainerSelected: {
    backgroundColor: '#6366F1',
    borderColor: '#6366F1',
  },
  shopTypeText: {
    fontSize: 11,
    color: '#6B7280',
    textAlign: 'center',
    marginTop: 6,
    fontWeight: '500',
  },
  shopTypeTextSelected: {
    color: '#6366F1',
    fontWeight: '700',
  },
  shopTypeCheck: {
    position: 'absolute',
    top: 10,
    right: 10,
    width: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: '#22C55E',
    justifyContent: 'center',
    alignItems: 'center',
  },
  continueButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#6366F1',
    borderRadius: 12,
    paddingVertical: 16,
    marginTop: 8,
    gap: 8,
  },
  continueButtonDisabled: {
    backgroundColor: '#A5B4FC',
  },
  continueButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  locationButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 16,
    marginTop: 8,
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  locationIconContainer: {
    width: 48,
    height: 48,
    backgroundColor: '#EEF2FF',
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
  },
  locationTextContainer: {
    flex: 1,
    marginLeft: 14,
  },
  locationButtonTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: '#111827',
  },
  locationButtonSubtitle: {
    fontSize: 12,
    color: '#6B7280',
    marginTop: 2,
  },
  operatingHoursSection: {
    marginTop: 24,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#111827',
    marginBottom: 4,
  },
  sectionSubtitle: {
    fontSize: 13,
    color: '#6B7280',
    marginBottom: 16,
  },
  timePickersRow: {
    flexDirection: 'row',
    gap: 12,
  },
  timePickerButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 14,
    padding: 14,
    borderWidth: 2,
    borderColor: '#E5E7EB',
  },
  timePickerIcon: {
    width: 40,
    height: 40,
    backgroundColor: '#FEF3C7',
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
  },
  timePickerContent: {
    flex: 1,
    marginLeft: 10,
  },
  timePickerLabel: {
    fontSize: 11,
    color: '#6B7280',
    fontWeight: '500',
  },
  timePickerValue: {
    fontSize: 15,
    fontWeight: '700',
    color: '#111827',
    marginTop: 2,
  },
  deliveryToggleCard: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 16,
    marginTop: 20,
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  deliveryToggleLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
  },
  deliveryToggleText: {},
  deliveryToggleTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: '#111827',
  },
  deliveryToggleSubtitle: {
    fontSize: 12,
    color: '#6B7280',
    marginTop: 2,
  },
  navigationButtons: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 24,
  },
  backButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#EEF2FF',
    borderRadius: 12,
    paddingVertical: 16,
    paddingHorizontal: 20,
    gap: 6,
  },
  backButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#6366F1',
  },
  // Time Picker Modal Styles
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: '#FFFFFF',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 24,
    paddingBottom: 40,
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#111827',
    textAlign: 'center',
    marginBottom: 20,
  },
  timePickerContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
  },
  pickerColumn: {
    alignItems: 'center',
  },
  pickerLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: '#6B7280',
    marginBottom: 8,
  },
  pickerScroll: {
    height: 150,
    width: 70,
  },
  pickerItem: {
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 10,
    marginVertical: 2,
  },
  pickerItemSelected: {
    backgroundColor: '#6366F1',
  },
  pickerItemText: {
    fontSize: 20,
    fontWeight: '600',
    color: '#374151',
    textAlign: 'center',
  },
  pickerItemTextSelected: {
    color: '#FFFFFF',
  },
  timeSeparator: {
    fontSize: 32,
    fontWeight: '700',
    color: '#374151',
    marginTop: 20,
  },
  selectedTimeDisplay: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#EEF2FF',
    borderRadius: 12,
    padding: 16,
    marginTop: 20,
    gap: 10,
  },
  selectedTimeText: {
    fontSize: 24,
    fontWeight: '700',
    color: '#6366F1',
  },
  modalButtons: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 24,
  },
  modalCancelBtn: {
    flex: 1,
    backgroundColor: '#F3F4F6',
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: 'center',
  },
  modalCancelText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#6B7280',
  },
  modalConfirmBtn: {
    flex: 1,
    backgroundColor: '#6366F1',
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: 'center',
  },
  modalConfirmText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  // Step 3 Styles
  imagePickerLarge: {
    position: 'relative',
    marginBottom: 24,
  },
  shopImageLarge: {
    width: '100%',
    height: 180,
    borderRadius: 16,
  },
  imagePlaceholderLarge: {
    width: '100%',
    height: 180,
    backgroundColor: '#F3F4F6',
    borderRadius: 16,
    borderWidth: 2,
    borderColor: '#E5E7EB',
    borderStyle: 'dashed',
    justifyContent: 'center',
    alignItems: 'center',
  },
  cameraIconContainer: {
    width: 64,
    height: 64,
    backgroundColor: '#EEF2FF',
    borderRadius: 32,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 12,
  },
  imagePlaceholderTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#374151',
  },
  imagePlaceholderSubtitle: {
    fontSize: 13,
    color: '#9CA3AF',
    marginTop: 4,
  },
  imageEditBadge: {
    position: 'absolute',
    bottom: 12,
    right: 12,
    width: 36,
    height: 36,
    backgroundColor: '#6366F1',
    borderRadius: 18,
    justifyContent: 'center',
    alignItems: 'center',
  },
  businessSection: {
    marginBottom: 24,
  },
  businessInputRow: {
    flexDirection: 'row',
    gap: 12,
  },
  businessInput: {
    flex: 1,
  },
  businessInputLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: '#6B7280',
    marginBottom: 6,
  },
  businessInputField: {
    backgroundColor: '#FFFFFF',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#E5E7EB',
    paddingHorizontal: 12,
    paddingVertical: 12,
    fontSize: 14,
    color: '#111827',
  },
  fssaiInput: {
    marginTop: 12,
  },
  descriptionSection: {
    marginBottom: 8,
  },
  descriptionRequired: {
    fontSize: 12,
    color: '#DC2626',
    fontWeight: '600',
    marginBottom: 12,
  },
  descriptionInput: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#E5E7EB',
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 15,
    color: '#111827',
    minHeight: 120,
    textAlignVertical: 'top',
  },
  exampleContainer: {
    backgroundColor: '#FFFBEB',
    borderRadius: 12,
    padding: 14,
    marginTop: 12,
    borderWidth: 1,
    borderColor: '#FDE68A',
  },
  exampleHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 8,
  },
  exampleTitle: {
    fontSize: 13,
    fontWeight: '600',
    color: '#92400E',
  },
  exampleText: {
    fontSize: 13,
    color: '#78350F',
    lineHeight: 20,
  },
  useExampleButton: {
    backgroundColor: '#F59E0B',
    borderRadius: 8,
    paddingVertical: 10,
    marginTop: 12,
    alignItems: 'center',
  },
  useExampleButtonText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  registerButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#22C55E',
    borderRadius: 12,
    paddingVertical: 16,
    gap: 8,
  },
  registerButtonDisabled: {
    backgroundColor: '#86EFAC',
  },
  registerButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  // Map Preview Styles
  mapPreviewContainer: {
    marginTop: 16,
  },
  mapPreviewLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: '#6B7280',
    marginBottom: 8,
  },
  mapPreviewTile: {
    height: 160,
    borderRadius: 16,
    overflow: 'hidden',
    backgroundColor: '#F3F4F6',
    position: 'relative',
  },
  mapPreview: {
    flex: 1,
  },
  mapPlaceholder: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#F9FAFB',
  },
  mapPlaceholderText: {
    fontSize: 14,
    color: '#9CA3AF',
    marginTop: 8,
  },
  mapOverlay: {
    position: 'absolute',
    bottom: 12,
    right: 12,
  },
  mapEditBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#6366F1',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 20,
    gap: 6,
  },
  mapEditText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  mapMarker: {
    width: 40,
    height: 40,
    backgroundColor: '#6366F1',
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 3,
    borderColor: '#FFFFFF',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 4,
    elevation: 5,
  },
  // Full Map Modal Styles
  mapModalContainer: {
    flex: 1,
    backgroundColor: '#FFFFFF',
  },
  mapModalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingBottom: 12,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  mapModalBackBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#F3F4F6',
    justifyContent: 'center',
    alignItems: 'center',
  },
  mapModalTitleContainer: {
    alignItems: 'center',
  },
  mapModalTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#111827',
  },
  mapModalSubtitle: {
    fontSize: 13,
    color: '#6B7280',
    marginTop: 2,
  },
  fullMap: {
    flex: 1,
  },
  draggableMarker: {
    alignItems: 'center',
  },
  markerPinTop: {
    width: 48,
    height: 48,
    backgroundColor: '#6366F1',
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 3,
    borderColor: '#FFFFFF',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 6,
    elevation: 8,
  },
  markerPinBottom: {
    width: 4,
    height: 20,
    backgroundColor: '#6366F1',
    borderBottomLeftRadius: 2,
    borderBottomRightRadius: 2,
    marginTop: -2,
  },
  mapInstructions: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#EEF2FF',
    paddingVertical: 12,
    gap: 8,
  },
  mapInstructionText: {
    fontSize: 14,
    color: '#4F46E5',
    fontWeight: '500',
  },
  coordinatesDisplay: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 12,
    backgroundColor: '#F9FAFB',
  },
  coordinatesLabel: {
    fontSize: 13,
    color: '#6B7280',
  },
  coordinatesValue: {
    fontSize: 13,
    fontWeight: '600',
    color: '#374151',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  mapModalFooter: {
    flexDirection: 'row',
    gap: 12,
    paddingHorizontal: 20,
    paddingTop: 16,
    backgroundColor: '#FFFFFF',
    borderTopWidth: 1,
    borderTopColor: '#E5E7EB',
  },
  mapModalCancelBtn: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#F3F4F6',
    paddingVertical: 16,
    borderRadius: 12,
  },
  mapModalCancelText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#374151',
  },
  mapModalConfirmBtn: {
    flex: 2,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#6366F1',
    paddingVertical: 16,
    borderRadius: 12,
    gap: 8,
  },
  mapModalConfirmText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFFFFF',
  },
});
