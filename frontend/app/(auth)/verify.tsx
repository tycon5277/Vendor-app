import React, { useState, useRef } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { authAPI } from '../../src/utils/api';
import { useAuthStore } from '../../src/store/authStore';
import { useTheme, typography, spacing, borderRadius } from '../../src/context/ThemeContext';
import { Button } from '../../src/components/ios';

export default function VerifyScreen() {
  const router = useRouter();
  const { colors, isDark } = useTheme();
  const { phone } = useLocalSearchParams<{ phone: string }>();
  const { setUser, setToken } = useAuthStore();
  const [otp, setOtp] = useState(['', '', '', '', '', '']);
  const [loading, setLoading] = useState(false);
  const inputRefs = useRef<TextInput[]>([]);

  const handleOtpChange = (value: string, index: number) => {
    const newOtp = [...otp];
    newOtp[index] = value;
    setOtp(newOtp);

    if (value && index < 5) {
      inputRefs.current[index + 1]?.focus();
    }
  };

  const handleKeyPress = (e: any, index: number) => {
    if (e.nativeEvent.key === 'Backspace' && !otp[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
  };

  const handleVerify = async () => {
    const otpString = otp.join('');
    if (otpString.length !== 6) {
      Alert.alert('Invalid OTP', 'Please enter 6-digit OTP');
      return;
    }

    setLoading(true);
    try {
      const response = await authAPI.verifyOTP(phone || '', otpString);
      const { user, session_token, is_vendor } = response.data;
      
      setToken(session_token);
      setUser(user);

      if (is_vendor) {
        router.replace('/(main)/(tabs)/home');
      } else {
        router.replace('/(auth)/register');
      }
    } catch (error: any) {
      console.error('Verify OTP Error:', error);
      Alert.alert('Error', error.response?.data?.detail || 'Invalid OTP');
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    try {
      await authAPI.sendOTP(phone || '');
      Alert.alert('Success', 'OTP sent again!');
    } catch (error) {
      Alert.alert('Error', 'Failed to resend OTP');
    }
  };

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background.grouped }]}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.content}
      >
        {/* Back Button */}
        <TouchableOpacity
          testID="back-btn"
          style={styles.backButton}
          onPress={() => router.back()}
        >
          <Ionicons name="chevron-back" size={28} color={colors.primary} />
        </TouchableOpacity>

        {/* Header */}
        <View style={styles.header}>
          <View style={[styles.iconContainer, { backgroundColor: isDark ? colors.background.tertiary : 'rgba(0, 122, 255, 0.1)' }]}>
            <Ionicons name="shield-checkmark" size={44} color={colors.primary} />
          </View>
          <Text style={[styles.title, { color: colors.text.primary }]}>Verify OTP</Text>
          <Text style={[styles.subtitle, { color: colors.text.secondary }]}>
            Enter the 6-digit code sent to{'\n'}
            <Text style={[styles.phone, { color: colors.text.primary }]}>+91 {phone}</Text>
          </Text>
        </View>

        {/* OTP Inputs */}
        <View style={styles.otpContainer}>
          {otp.map((digit, index) => (
            <TextInput
              key={index}
              ref={(ref) => {
                if (ref) inputRefs.current[index] = ref;
              }}
              testID={`otp-input-${index}`}
              style={[
                styles.otpInput,
                {
                  backgroundColor: digit ? (isDark ? colors.background.tertiary : 'rgba(0, 122, 255, 0.1)') : colors.background.secondary,
                  borderColor: digit ? colors.primary : colors.separator,
                  color: colors.text.primary,
                },
              ]}
              value={digit}
              onChangeText={(value) => handleOtpChange(value, index)}
              onKeyPress={(e) => handleKeyPress(e, index)}
              keyboardType="number-pad"
              maxLength={1}
              selectTextOnFocus
            />
          ))}
        </View>

        {/* Verify Button */}
        <Button
          testID="verify-btn"
          title={loading ? 'Verifying...' : 'Verify & Continue'}
          onPress={handleVerify}
          disabled={loading || otp.join('').length !== 6}
          loading={loading}
        />

        {/* Resend Link */}
        <View style={styles.resendContainer}>
          <Text style={[styles.resendText, { color: colors.text.secondary }]}>
            Didn't receive code?{' '}
          </Text>
          <TouchableOpacity testID="resend-btn" onPress={handleResend}>
            <Text style={[styles.resendLink, { color: colors.primary }]}>Resend OTP</Text>
          </TouchableOpacity>
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
  },
  backButton: {
    width: 44,
    height: 44,
    justifyContent: 'center',
    marginTop: spacing.s,
  },
  header: {
    alignItems: 'center',
    marginTop: spacing.xxxl,
    marginBottom: spacing.xxxl,
  },
  iconContainer: {
    width: 88,
    height: 88,
    borderRadius: 44,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: spacing.xxl,
  },
  title: {
    fontSize: typography.title2.fontSize,
    fontWeight: '700',
    marginBottom: spacing.m,
  },
  subtitle: {
    fontSize: typography.callout.fontSize,
    textAlign: 'center',
    lineHeight: 22,
  },
  phone: {
    fontWeight: '600',
  },
  otpContainer: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: spacing.m,
    marginBottom: spacing.xxl,
  },
  otpInput: {
    width: 48,
    height: 56,
    borderRadius: borderRadius.m,
    borderWidth: 2,
    fontSize: 24,
    fontWeight: '600',
    textAlign: 'center',
  },
  resendContainer: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginTop: spacing.xxl,
  },
  resendText: {
    fontSize: typography.subhead.fontSize,
  },
  resendLink: {
    fontSize: typography.subhead.fontSize,
    fontWeight: '600',
  },
});
