import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
  Image,
  Animated,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import QRCode from 'react-native-qrcode-svg';
import { useAuthStore } from '../../../src/store/authStore';
import { vendorAPI } from '../../../src/utils/api';
import { Analytics } from '../../../src/types';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useTheme, typography, spacing, borderRadius } from '../../../src/context/ThemeContext';
import { ListItem, ListSection, Badge } from '../../../src/components/ios';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

export default function ProfileScreen() {
  const router = useRouter();
  const { colors, isDark } = useTheme();
  const { user, logout } = useAuthStore();
  const [showQR, setShowQR] = useState(false);
  const [qrData, setQRData] = useState<any>(null);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [unreadNotifCount, setUnreadNotifCount] = useState(0);
  const fadeAnim = useRef(new Animated.Value(0)).current;

  const loadData = async () => {
    try {
      const [analyticsRes, qrRes] = await Promise.all([
        vendorAPI.getAnalytics(),
        vendorAPI.getQRData(),
      ]);
      setAnalytics(analyticsRes.data);
      setQRData(qrRes.data);
    } catch (error) {
      console.error('Load profile data error:', error);
    }
  };

  const fetchUnreadCount = async () => {
    try {
      const token = await AsyncStorage.getItem('token');
      if (!token) return;
      const res = await fetch(`${API_URL}/api/vendor/notifications/unread-count`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setUnreadNotifCount(data.unread_count || 0);
      }
    } catch (e) {
      console.error('Fetch unread count error:', e);
    }
  };

  useEffect(() => {
    loadData();
    fetchUnreadCount();
    const interval = setInterval(fetchUnreadCount, 30000);
    Animated.timing(fadeAnim, { toValue: 1, duration: 400, useNativeDriver: true }).start();
    return () => clearInterval(interval);
  }, []);

  const handleLogout = () => {
    if (typeof window !== 'undefined' && window.confirm) {
      if (window.confirm('Are you sure you want to logout?')) {
        logout().then(() => router.replace('/(auth)/login'));
      }
    } else {
      Alert.alert('Logout', 'Are you sure you want to logout?', [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Logout', style: 'destructive', onPress: async () => { await logout(); router.replace('/(auth)/login'); } },
      ]);
    }
  };

  const isShopOpen = user?.partner_status === 'available';
  const totalOrders = analytics?.total_orders || 0;

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background.grouped }]} edges={['top']}>
      <ScrollView style={styles.scrollView} showsVerticalScrollIndicator={false}>
        <Animated.View style={{ opacity: fadeAnim }}>
          {/* Header */}
          <View style={styles.header}>
            <Text style={[styles.title, { color: colors.text.primary }]}>Profile</Text>
            <TouchableOpacity style={styles.settingsBtn} testID="settings-btn">
              <Ionicons name="settings-outline" size={24} color={colors.text.secondary} />
            </TouchableOpacity>
          </View>

          {/* Profile Card */}
          <View style={[styles.profileCard, { backgroundColor: colors.card }]}>
            <View style={styles.profileHeader}>
              <View style={styles.profileImageContainer}>
                {user?.vendor_shop_image ? (
                  <Image source={{ uri: user.vendor_shop_image }} style={styles.profileImage} />
                ) : (
                  <View style={[styles.profileImagePlaceholder, { backgroundColor: colors.primary }]}>
                    <Ionicons name="storefront" size={36} color="#FFFFFF" />
                  </View>
                )}
                <View style={[styles.statusDot, { backgroundColor: isShopOpen ? colors.success : colors.text.tertiary }]} />
              </View>
              
              <View style={styles.profileInfo}>
                <Text style={[styles.shopName, { color: colors.text.primary }]}>
                  {user?.vendor_shop_name || 'Your Shop'}
                </Text>
                <Text style={[styles.shopType, { color: colors.text.secondary }]}>{user?.vendor_shop_type}</Text>
                
                <View style={styles.profileMeta}>
                  <View style={[styles.ratingBadge, { backgroundColor: isDark ? colors.background.tertiary : '#FEF3C7' }]}>
                    <Ionicons name="star" size={14} color={colors.warning} />
                    <Text style={[styles.ratingText, { color: colors.warning }]}>
                      {user?.partner_rating?.toFixed(1) || '5.0'}
                    </Text>
                  </View>
                  <Badge text={isShopOpen ? 'Online' : 'Offline'} variant={isShopOpen ? 'success' : 'neutral'} />
                </View>
              </View>
            </View>
            
            <TouchableOpacity style={[styles.editProfileBtn, { backgroundColor: colors.background.secondary }]}>
              <Ionicons name="create-outline" size={18} color={colors.primary} />
              <Text style={[styles.editProfileText, { color: colors.primary }]}>Edit Profile</Text>
            </TouchableOpacity>
          </View>

          {/* Stats Card */}
          <View style={[styles.statsCard, { backgroundColor: colors.primary }]}>
            <View style={styles.statItem}>
              <Text style={styles.statValue}>₹{(analytics?.total_earnings || 0).toLocaleString()}</Text>
              <Text style={styles.statLabel}>Total Earnings</Text>
            </View>
            <View style={styles.statDivider} />
            <View style={styles.statItem}>
              <Text style={styles.statValue}>{analytics?.total_orders || 0}</Text>
              <Text style={styles.statLabel}>Orders</Text>
            </View>
            <View style={styles.statDivider} />
            <View style={styles.statItem}>
              <Text style={styles.statValue}>{analytics?.rating?.toFixed(1) || '5.0'}</Text>
              <Text style={styles.statLabel}>Rating</Text>
            </View>
          </View>

          {/* QR Code Section */}
          <ListSection>
            <TouchableOpacity 
              style={[styles.qrRow, { backgroundColor: colors.card }]} 
              onPress={() => setShowQR(!showQR)}
            >
              <View style={[styles.qrIconBg, { backgroundColor: isDark ? colors.background.tertiary : 'rgba(0, 122, 255, 0.1)' }]}>
                <Ionicons name="qr-code" size={22} color={colors.primary} />
              </View>
              <View style={styles.qrContent}>
                <Text style={[styles.qrTitle, { color: colors.text.primary }]}>Shop QR Code</Text>
                <Text style={[styles.qrSubtitle, { color: colors.text.secondary }]}>Share with customers</Text>
              </View>
              <Ionicons name={showQR ? 'chevron-up' : 'chevron-down'} size={22} color={colors.text.tertiary} />
            </TouchableOpacity>
            {showQR && qrData && (
              <View style={[styles.qrContainer, { backgroundColor: colors.card, borderTopColor: colors.separator }]}>
                <View style={styles.qrBox}>
                  <QRCode
                    value={qrData.qr_url || `quickwish://vendor/${user?.user_id}`}
                    size={160}
                    backgroundColor="#FFFFFF"
                    color="#000000"
                  />
                </View>
              </View>
            )}
          </ListSection>

          {/* Shop Details */}
          <ListSection title="SHOP DETAILS">
            <ListItem
              title="Address"
              subtitle={user?.vendor_shop_address || 'Not set'}
              leftIcon="location"
              leftIconColor={colors.primary}
              showChevron
            />
            <ListItem
              title="Opening Hours"
              subtitle={user?.vendor_opening_hours || 'Not set'}
              leftIcon="time"
              leftIconColor={colors.primary}
              showChevron
            />
            <ListItem
              title="Phone"
              subtitle={user?.phone || 'Not set'}
              leftIcon="call"
              leftIconColor={colors.primary}
              showChevron
              bottomBorder={false}
            />
          </ListSection>

          {/* Ratings & Issues */}
          <ListSection title="FEEDBACK">
            <ListItem
              title="Ratings & Reviews"
              leftIcon="star"
              leftIconColor={colors.warning}
              showChevron
              onPress={() => router.push('/(main)/vendor-ratings')}
              testID="vendor-ratings-link"
            />
            <ListItem
              title="Customer Issues"
              leftIcon="alert-circle"
              leftIconColor={colors.danger}
              showChevron
              bottomBorder={false}
              onPress={() => router.push('/(main)/vendor-issues')}
              testID="vendor-issues-link"
            />
          </ListSection>

          {/* Menu Items */}
          <ListSection title="SETTINGS">
            <ListItem
              title="Notifications"
              leftIcon="notifications"
              leftIconColor={colors.primary}
              showChevron
              onPress={() => router.push('/(main)/vendor-notifications')}
              testID="vendor-notifications-link"
              rightContent={unreadNotifCount > 0 ? (
                <View style={styles.notifBadge}>
                  <Badge text={unreadNotifCount > 99 ? '99+' : String(unreadNotifCount)} variant="danger" />
                </View>
              ) : undefined}
            />
            <ListItem
              title="Payment Settings"
              leftIcon="card"
              leftIconColor={colors.success}
              showChevron
            />
            <ListItem
              title="Help & Support"
              leftIcon="help-circle"
              leftIconColor={colors.warning}
              showChevron
            />
            <ListItem
              title="Terms & Privacy"
              leftIcon="document-text"
              leftIconColor={colors.text.secondary}
              showChevron
              bottomBorder={false}
            />
          </ListSection>

          {/* Logout */}
          <ListSection>
            <ListItem
              title="Logout"
              leftIcon="log-out-outline"
              leftIconColor={colors.danger}
              destructive
              onPress={handleLogout}
              bottomBorder={false}
              testID="logout-btn"
            />
          </ListSection>

          <Text style={[styles.version, { color: colors.text.tertiary }]}>QuickWish Vendor v1.0.0</Text>

          <View style={{ height: 100 }} />
        </Animated.View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  scrollView: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: spacing.l,
    paddingVertical: spacing.m,
  },
  title: {
    fontSize: typography.largeTitle.fontSize,
    fontWeight: '700',
  },
  settingsBtn: {
    width: 44,
    height: 44,
    justifyContent: 'center',
    alignItems: 'center',
  },
  profileCard: {
    marginHorizontal: spacing.l,
    padding: spacing.l,
    borderRadius: borderRadius.l,
  },
  profileHeader: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  profileImageContainer: {
    position: 'relative',
  },
  profileImage: {
    width: 72,
    height: 72,
    borderRadius: 36,
  },
  profileImagePlaceholder: {
    width: 72,
    height: 72,
    borderRadius: 36,
    justifyContent: 'center',
    alignItems: 'center',
  },
  statusDot: {
    position: 'absolute',
    bottom: 2,
    right: 2,
    width: 16,
    height: 16,
    borderRadius: 8,
    borderWidth: 3,
    borderColor: '#FFFFFF',
  },
  profileInfo: {
    flex: 1,
    marginLeft: spacing.l,
  },
  shopName: {
    fontSize: typography.title3.fontSize,
    fontWeight: '600',
  },
  shopType: {
    fontSize: typography.subhead.fontSize,
    marginTop: 2,
    textTransform: 'capitalize',
  },
  profileMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: spacing.s,
    gap: spacing.s,
  },
  ratingBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.s,
    paddingVertical: 4,
    borderRadius: borderRadius.s,
    gap: 4,
  },
  ratingText: {
    fontSize: typography.footnote.fontSize,
    fontWeight: '600',
  },
  editProfileBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: spacing.m,
    borderRadius: borderRadius.m,
    marginTop: spacing.l,
    gap: spacing.s,
  },
  editProfileText: {
    fontSize: typography.subhead.fontSize,
    fontWeight: '600',
  },
  statsCard: {
    flexDirection: 'row',
    marginHorizontal: spacing.l,
    marginTop: spacing.l,
    padding: spacing.l,
    borderRadius: borderRadius.l,
  },
  statItem: {
    flex: 1,
    alignItems: 'center',
  },
  statValue: {
    fontSize: typography.title3.fontSize,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  statLabel: {
    fontSize: typography.caption1.fontSize,
    color: 'rgba(255,255,255,0.7)',
    marginTop: 4,
  },
  statDivider: {
    width: 1,
    backgroundColor: 'rgba(255,255,255,0.2)',
    marginVertical: spacing.xs,
  },
  qrRow: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: spacing.m,
  },
  qrIconBg: {
    width: 40,
    height: 40,
    borderRadius: borderRadius.s,
    justifyContent: 'center',
    alignItems: 'center',
  },
  qrContent: {
    flex: 1,
    marginLeft: spacing.m,
  },
  qrTitle: {
    fontSize: typography.body.fontSize,
  },
  qrSubtitle: {
    fontSize: typography.footnote.fontSize,
    marginTop: 2,
  },
  qrContainer: {
    alignItems: 'center',
    padding: spacing.l,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  qrBox: {
    padding: spacing.l,
    backgroundColor: '#FFFFFF',
    borderRadius: borderRadius.m,
  },
  notifBadge: {
    marginRight: spacing.s,
  },
  version: {
    textAlign: 'center',
    fontSize: typography.footnote.fontSize,
    marginTop: spacing.xxl,
  },
});
