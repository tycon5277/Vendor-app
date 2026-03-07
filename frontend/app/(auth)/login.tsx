import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { authAPI } from '../../src/utils/api';
import { useTheme, typography, spacing, borderRadius } from '../../src/context/ThemeContext';
import { Button } from '../../src/components/ios';

export default function LoginScreen() {
  const router = useRouter();
  const { colors, isDark } = useTheme();
  const [phone, setPhone] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSendOTP = async () => {
    if (phone.length < 10) {
      Alert.alert('Invalid Phone', 'Please enter a valid phone number');
      return;
    }

    setLoading(true);
    try {
      const response = await authAPI.sendOTP(phone);
      console.log('OTP Response:', response.data);
      router.push({ pathname: '/(auth)/verify', params: { phone } });
    } catch (error: any) {
      console.error('Send OTP Error:', error);
      Alert.alert('Error', error.response?.data?.detail || 'Failed to send OTP');
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background.grouped }]}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.content}
      >
        {/* Header */}
        <View style={styles.header}>
          <View style={[styles.logoContainer, { backgroundColor: isDark ? colors.background.tertiary : 'rgba(0, 122, 255, 0.1)' }]}>
            <Ionicons name="storefront" size={56} color={colors.primary} />
          </View>
          <Text style={[styles.title, { color: colors.text.primary }]}>QuickWish Vendor</Text>
          <Text style={[styles.subtitle, { color: colors.text.secondary }]}>Manage your shop, orders & earnings</Text>
        </View>

        {/* Form */}
        <View style={[styles.formCard, { backgroundColor: colors.card }]}>
          <Text style={[styles.label, { color: colors.text.secondary }]}>Phone Number</Text>
          <View style={[styles.inputContainer, { backgroundColor: colors.background.secondary }]}>
            <Text style={[styles.countryCode, { color: colors.text.primary, borderRightColor: colors.separator }]}>+91</Text>
            <TextInput
              testID="phone-input"
              style={[styles.input, { color: colors.text.primary }]}
              placeholder="Enter your phone number"
              placeholderTextColor={colors.text.tertiary}
              keyboardType="phone-pad"
              maxLength={10}
              value={phone}
              onChangeText={setPhone}
            />
          </View>

          <Button
            testID="send-otp-btn"
            title={loading ? 'Sending OTP...' : 'Get OTP'}
            onPress={handleSendOTP}
            disabled={loading || phone.length < 10}
            loading={loading}
          />

          <Text style={[styles.hint, { color: colors.text.tertiary }]}>
            Test OTP: 123456
          </Text>
        </View>

        {/* Footer */}
        <View style={styles.footer}>
          <Text style={[styles.footerText, { color: colors.text.tertiary }]}>
            By continuing, you agree to our Terms of Service
          </Text>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  content: {
    flex: 1,
    paddingHorizontal: spacing.l,
    justifyContent: 'center',
  },
  header: {
    alignItems: 'center',
    marginBottom: spacing.xxxl,
  },
  logoContainer: {
    width: 110,
    height: 110,
    borderRadius: 55,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: spacing.xxl,
  },
  title: {
    fontSize: typography.title1.fontSize,
    fontWeight: '700',
    marginBottom: spacing.s,
  },
  subtitle: {
    fontSize: typography.callout.fontSize,
    textAlign: 'center',
  },
  formCard: {
    borderRadius: borderRadius.l,
    padding: spacing.xl,
    marginBottom: spacing.xxl,
  },
  label: {
    fontSize: typography.footnote.fontSize,
    fontWeight: '500',
    textTransform: 'uppercase',
    marginBottom: spacing.s,
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: borderRadius.m,
    marginBottom: spacing.xl,
    overflow: 'hidden',
  },
  countryCode: {
    paddingHorizontal: spacing.l,
    paddingVertical: spacing.l,
    fontSize: typography.body.fontSize,
    fontWeight: '600',
    borderRightWidth: StyleSheet.hairlineWidth,
  },
  input: {
    flex: 1,
    paddingHorizontal: spacing.l,
    paddingVertical: spacing.l,
    fontSize: typography.body.fontSize,
  },
  hint: {
    marginTop: spacing.l,
    textAlign: 'center',
    fontSize: typography.footnote.fontSize,
  },
  footer: {
    alignItems: 'center',
  },
  footerText: {
    fontSize: typography.footnote.fontSize,
    textAlign: 'center',
  },
});
