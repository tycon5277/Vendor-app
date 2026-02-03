import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Alert,
  Switch,
  Image,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import * as Location from 'expo-location';
import { vendorAPI } from '../../src/utils/api';
import { useAuthStore } from '../../src/store/authStore';

const PRESET_SHOP_TYPES = [
  'Grocery', 'Restaurant', 'Pharmacy', 'Electronics', 'Fashion',
  'Bakery', 'Farm Produce', 'Fish & Seafood', 'Nursery & Plants',
  'Hardware', 'Stationery', 'Supermarket', 'Sweet Shop', 'Dairy', 'Other'
];

export default function RegisterScreen() {
  const router = useRouter();
  const { setUser, user } = useAuthStore();
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState(1);

  const [formData, setFormData] = useState({
    name: user?.name || '',
    shop_name: '',
    shop_type: '',
    custom_shop_type: '',
    shop_address: '',
    shop_location: null as { lat: number; lng: number } | null,
    can_deliver: false,
    categories: [] as string[],
    opening_hours: '9:00 AM - 9:00 PM',
    description: '',
    shop_image: null as string | null,
  });

  const getCurrentLocation = async () => {
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Permission Denied', 'Location permission is required');
        return;
      }

      const location = await Location.getCurrentPositionAsync({});
      setFormData(prev => ({
        ...prev,
        shop_location: {
          lat: location.coords.latitude,
          lng: location.coords.longitude,
        }
      }));
      Alert.alert('Success', 'Location captured!');
    } catch (error) {
      Alert.alert('Error', 'Failed to get location');
    }
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
        setFormData(prev => ({
          ...prev,
          shop_image: `data:image/jpeg;base64,${result.assets[0].base64}`
        }));
      }
    } catch (error) {
      Alert.alert('Error', 'Failed to pick image');
    }
  };

  const handleRegister = async () => {
    if (!formData.name || !formData.shop_name || !formData.shop_type || !formData.shop_address) {
      Alert.alert('Missing Information', 'Please fill all required fields');
      return;
    }

    setLoading(true);
    try {
      const response = await vendorAPI.register(formData);
      setUser(response.data.user);
      Alert.alert('Success', 'Shop registered successfully!', [
        { text: 'OK', onPress: () => router.replace('/(main)/home') }
      ]);
    } catch (error: any) {
      console.error('Register Error:', error);
      Alert.alert('Error', error.response?.data?.detail || 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  const renderStep1 = () => (
    <View style={styles.stepContainer}>
      <Text style={styles.stepTitle}>Owner Details</Text>
      
      <Text style={styles.label}>Your Name *</Text>
      <TextInput
        style={styles.input}
        placeholder="Enter your full name"
        placeholderTextColor="#9CA3AF"
        value={formData.name}
        onChangeText={(text) => setFormData(prev => ({ ...prev, name: text }))}
      />

      <Text style={styles.label}>Shop Name *</Text>
      <TextInput
        style={styles.input}
        placeholder="Enter your shop name"
        placeholderTextColor="#9CA3AF"
        value={formData.shop_name}
        onChangeText={(text) => setFormData(prev => ({ ...prev, shop_name: text }))}
      />

      <Text style={styles.label}>Shop Type *</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chipScroll}>
        {PRESET_SHOP_TYPES.map((type) => (
          <TouchableOpacity
            key={type}
            style={[
              styles.chip,
              formData.shop_type === type && styles.chipSelected
            ]}
            onPress={() => setFormData(prev => ({ ...prev, shop_type: type }))}
          >
            <Text style={[
              styles.chipText,
              formData.shop_type === type && styles.chipTextSelected
            ]}>
              {type}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {formData.shop_type === 'Other' && (
        <TextInput
          style={[styles.input, { marginTop: 12 }]}
          placeholder="Enter custom shop type"
          placeholderTextColor="#9CA3AF"
          value={formData.custom_shop_type}
          onChangeText={(text) => setFormData(prev => ({ ...prev, custom_shop_type: text }))}
        />
      )}

      <TouchableOpacity
        style={styles.nextButton}
        onPress={() => {
          if (formData.name && formData.shop_name && formData.shop_type) {
            setStep(2);
          } else {
            Alert.alert('Missing Information', 'Please fill all required fields');
          }
        }}
      >
        <Text style={styles.nextButtonText}>Continue</Text>
        <Ionicons name="arrow-forward" size={20} color="#FFF" />
      </TouchableOpacity>
    </View>
  );

  const renderStep2 = () => (
    <View style={styles.stepContainer}>
      <Text style={styles.stepTitle}>Shop Location</Text>

      <Text style={styles.label}>Shop Address *</Text>
      <TextInput
        style={[styles.input, styles.textArea]}
        placeholder="Enter complete shop address"
        placeholderTextColor="#9CA3AF"
        multiline
        numberOfLines={3}
        value={formData.shop_address}
        onChangeText={(text) => setFormData(prev => ({ ...prev, shop_address: text }))}
      />

      <TouchableOpacity style={styles.locationButton} onPress={getCurrentLocation}>
        <Ionicons name="location" size={24} color="#6366F1" />
        <Text style={styles.locationButtonText}>
          {formData.shop_location ? 'Location Captured ✓' : 'Get Current Location'}
        </Text>
      </TouchableOpacity>

      <Text style={styles.label}>Opening Hours</Text>
      <TextInput
        style={styles.input}
        placeholder="e.g., 9:00 AM - 9:00 PM"
        placeholderTextColor="#9CA3AF"
        value={formData.opening_hours}
        onChangeText={(text) => setFormData(prev => ({ ...prev, opening_hours: text }))}
      />

      <View style={styles.switchRow}>
        <Text style={styles.switchLabel}>We do our own delivery</Text>
        <Switch
          value={formData.can_deliver}
          onValueChange={(value) => setFormData(prev => ({ ...prev, can_deliver: value }))}
          trackColor={{ false: '#E5E7EB', true: '#A5B4FC' }}
          thumbColor={formData.can_deliver ? '#6366F1' : '#9CA3AF'}
        />
      </View>

      <View style={styles.buttonRow}>
        <TouchableOpacity style={styles.backStepButton} onPress={() => setStep(1)}>
          <Ionicons name="arrow-back" size={20} color="#6366F1" />
          <Text style={styles.backStepText}>Back</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.nextButton}
          onPress={() => {
            if (formData.shop_address) {
              setStep(3);
            } else {
              Alert.alert('Missing Information', 'Please enter shop address');
            }
          }}
        >
          <Text style={styles.nextButtonText}>Continue</Text>
          <Ionicons name="arrow-forward" size={20} color="#FFF" />
        </TouchableOpacity>
      </View>
    </View>
  );

  const renderStep3 = () => (
    <View style={styles.stepContainer}>
      <Text style={styles.stepTitle}>Shop Photo & Description</Text>

      <TouchableOpacity style={styles.imagePickerContainer} onPress={pickImage}>
        {formData.shop_image ? (
          <Image source={{ uri: formData.shop_image }} style={styles.shopImage} />
        ) : (
          <View style={styles.imagePlaceholder}>
            <Ionicons name="camera" size={48} color="#9CA3AF" />
            <Text style={styles.imagePlaceholderText}>Add Shop Photo</Text>
          </View>
        )}
      </TouchableOpacity>

      <Text style={styles.label}>Description (Optional)</Text>
      <TextInput
        style={[styles.input, styles.textArea]}
        placeholder="Tell customers about your shop..."
        placeholderTextColor="#9CA3AF"
        multiline
        numberOfLines={4}
        value={formData.description}
        onChangeText={(text) => setFormData(prev => ({ ...prev, description: text }))}
      />

      <View style={styles.buttonRow}>
        <TouchableOpacity style={styles.backStepButton} onPress={() => setStep(2)}>
          <Ionicons name="arrow-back" size={20} color="#6366F1" />
          <Text style={styles.backStepText}>Back</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.nextButton, loading && styles.buttonDisabled]}
          onPress={handleRegister}
          disabled={loading}
        >
          <Text style={styles.nextButtonText}>
            {loading ? 'Registering...' : 'Complete Registration'}
          </Text>
        </TouchableOpacity>
      </View>
    </View>
  );

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView style={styles.scrollView} showsVerticalScrollIndicator={false}>
        <View style={styles.header}>
          <View style={styles.progressContainer}>
            {[1, 2, 3].map((s) => (
              <View
                key={s}
                style={[
                  styles.progressDot,
                  s <= step && styles.progressDotActive
                ]}
              />
            ))}
          </View>
          <Text style={styles.headerTitle}>Register Your Shop</Text>
          <Text style={styles.headerSubtitle}>Step {step} of 3</Text>
        </View>

        {step === 1 && renderStep1()}
        {step === 2 && renderStep2()}
        {step === 3 && renderStep3()}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F9FAFB',
  },
  scrollView: {
    flex: 1,
  },
  header: {
    paddingHorizontal: 24,
    paddingTop: 20,
    paddingBottom: 16,
  },
  progressContainer: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 8,
    marginBottom: 20,
  },
  progressDot: {
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: '#E5E7EB',
  },
  progressDotActive: {
    backgroundColor: '#6366F1',
  },
  headerTitle: {
    fontSize: 24,
    fontWeight: '700',
    color: '#111827',
    textAlign: 'center',
  },
  headerSubtitle: {
    fontSize: 14,
    color: '#6B7280',
    textAlign: 'center',
    marginTop: 4,
  },
  stepContainer: {
    paddingHorizontal: 24,
    paddingBottom: 40,
  },
  stepTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#374151',
    marginBottom: 20,
  },
  label: {
    fontSize: 14,
    fontWeight: '600',
    color: '#374151',
    marginBottom: 8,
    marginTop: 16,
  },
  input: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#E5E7EB',
    paddingHorizontal: 16,
    paddingVertical: 14,
    fontSize: 16,
    color: '#111827',
  },
  textArea: {
    minHeight: 100,
    textAlignVertical: 'top',
  },
  chipScroll: {
    marginTop: 8,
  },
  chip: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 20,
    backgroundColor: '#F3F4F6',
    marginRight: 8,
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  chipSelected: {
    backgroundColor: '#6366F1',
    borderColor: '#6366F1',
  },
  chipText: {
    fontSize: 14,
    color: '#4B5563',
  },
  chipTextSelected: {
    color: '#FFFFFF',
    fontWeight: '600',
  },
  locationButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#EEF2FF',
    borderRadius: 12,
    paddingVertical: 14,
    marginTop: 16,
    gap: 8,
  },
  locationButtonText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#6366F1',
  },
  switchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    padding: 16,
    marginTop: 20,
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  switchLabel: {
    fontSize: 15,
    color: '#374151',
    fontWeight: '500',
  },
  nextButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#6366F1',
    borderRadius: 12,
    paddingVertical: 16,
    marginTop: 24,
    gap: 8,
    flex: 1,
  },
  nextButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  buttonDisabled: {
    backgroundColor: '#A5B4FC',
  },
  buttonRow: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 24,
  },
  backStepButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#EEF2FF',
    borderRadius: 12,
    paddingVertical: 16,
    paddingHorizontal: 20,
    gap: 6,
  },
  backStepText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#6366F1',
  },
  imagePickerContainer: {
    marginTop: 8,
  },
  imagePlaceholder: {
    backgroundColor: '#F3F4F6',
    borderRadius: 16,
    borderWidth: 2,
    borderColor: '#E5E7EB',
    borderStyle: 'dashed',
    height: 180,
    justifyContent: 'center',
    alignItems: 'center',
  },
  imagePlaceholderText: {
    marginTop: 8,
    fontSize: 14,
    color: '#9CA3AF',
  },
  shopImage: {
    width: '100%',
    height: 180,
    borderRadius: 16,
  },
});
