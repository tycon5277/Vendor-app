import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Linking,
  Platform,
  Modal,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAuthStore } from '../store/authStore';
import { useTheme, spacing, borderRadius } from '../context/ThemeContext';

const SUPPORT_EMAIL = 'support@quickwish.app';
const SUPPORT_PHONE = '+91-9999999999';

export const SuspensionOverlay: React.FC = () => {
  const { user, isSuspended } = useAuthStore();
  const { colors } = useTheme();

  // Don't render if not suspended
  if (!isSuspended && !user?.vendor_suspended) {
    return null;
  }

  const handleContactSupport = () => {
    // Open email client
    const subject = encodeURIComponent('Account Suspension Appeal');
    const body = encodeURIComponent(
      `Hi Support Team,\n\nMy vendor account has been suspended.\n\nShop Name: ${user?.vendor_shop_name || 'N/A'}\nPhone: ${user?.phone || 'N/A'}\nUser ID: ${user?.user_id || 'N/A'}\n\nReason given: ${user?.vendor_suspension_reason || 'Not specified'}\n\nI would like to appeal this decision.\n\nRegards`
    );
    Linking.openURL(`mailto:${SUPPORT_EMAIL}?subject=${subject}&body=${body}`);
  };

  const handleCallSupport = () => {
    Linking.openURL(`tel:${SUPPORT_PHONE}`);
  };

  return (
    <Modal
      visible={true}
      transparent={true}
      animationType="fade"
      statusBarTranslucent={true}
    >
      <View style={styles.overlay}>
        <View style={[styles.container, { backgroundColor: colors.card }]}>
          {/* Warning Icon */}
          <View style={styles.iconContainer}>
            <Ionicons name="ban" size={64} color="#EF4444" />
          </View>

          {/* Title */}
          <Text style={[styles.title, { color: colors.text.primary }]}>
            Account Suspended
          </Text>

          {/* Shop Name */}
          <Text style={[styles.shopName, { color: colors.text.secondary }]}>
            {user?.vendor_shop_name}
          </Text>

          {/* Reason */}
          <View style={[styles.reasonBox, { backgroundColor: 'rgba(239, 68, 68, 0.1)' }]}>
            <Text style={styles.reasonLabel}>Reason:</Text>
            <Text style={[styles.reasonText, { color: colors.text.primary }]}>
              {user?.vendor_suspension_reason || 'Policy violation. Please contact support for details.'}
            </Text>
          </View>

          {/* Message */}
          <Text style={[styles.message, { color: colors.text.secondary }]}>
            Your shop is currently offline and cannot receive orders. 
            Please contact our support team immediately to resolve this issue.
          </Text>

          {/* Contact Buttons */}
          <View style={styles.buttonContainer}>
            <TouchableOpacity
              style={[styles.primaryButton, { backgroundColor: '#EF4444' }]}
              onPress={handleContactSupport}
              activeOpacity={0.8}
            >
              <Ionicons name="mail" size={20} color="#FFFFFF" />
              <Text style={styles.primaryButtonText}>Email Support</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.secondaryButton, { borderColor: colors.border }]}
              onPress={handleCallSupport}
              activeOpacity={0.8}
            >
              <Ionicons name="call" size={20} color={colors.primary} />
              <Text style={[styles.secondaryButtonText, { color: colors.primary }]}>
                Call Support
              </Text>
            </TouchableOpacity>
          </View>

          {/* Support Info */}
          <View style={styles.supportInfo}>
            <Text style={[styles.supportInfoText, { color: colors.text.tertiary }]}>
              Support Hours: Mon-Sat, 9 AM - 6 PM
            </Text>
            <Text style={[styles.supportInfoText, { color: colors.text.tertiary }]}>
              {SUPPORT_EMAIL}
            </Text>
          </View>
        </View>
      </View>
    </Modal>
  );
};

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.85)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.l,
  },
  container: {
    width: '100%',
    maxWidth: 400,
    borderRadius: borderRadius.xl,
    padding: spacing.xl,
    alignItems: 'center',
  },
  iconContainer: {
    width: 100,
    height: 100,
    borderRadius: 50,
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: spacing.l,
  },
  title: {
    fontSize: 24,
    fontWeight: '700',
    marginBottom: spacing.xs,
    textAlign: 'center',
  },
  shopName: {
    fontSize: 16,
    marginBottom: spacing.l,
    textAlign: 'center',
  },
  reasonBox: {
    width: '100%',
    padding: spacing.m,
    borderRadius: borderRadius.m,
    marginBottom: spacing.l,
    borderLeftWidth: 4,
    borderLeftColor: '#EF4444',
  },
  reasonLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: '#EF4444',
    marginBottom: 4,
    textTransform: 'uppercase',
  },
  reasonText: {
    fontSize: 14,
    lineHeight: 20,
  },
  message: {
    fontSize: 14,
    lineHeight: 22,
    textAlign: 'center',
    marginBottom: spacing.xl,
  },
  buttonContainer: {
    width: '100%',
    gap: spacing.m,
  },
  primaryButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.m,
    borderRadius: borderRadius.m,
    gap: spacing.s,
  },
  primaryButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
  secondaryButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.m,
    borderRadius: borderRadius.m,
    borderWidth: 1.5,
    gap: spacing.s,
  },
  secondaryButtonText: {
    fontSize: 16,
    fontWeight: '600',
  },
  supportInfo: {
    marginTop: spacing.xl,
    alignItems: 'center',
  },
  supportInfoText: {
    fontSize: 12,
    marginTop: 4,
  },
});

export default SuspensionOverlay;
