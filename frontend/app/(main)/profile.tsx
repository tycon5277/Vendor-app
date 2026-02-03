import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
  Image,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import QRCode from 'react-native-qrcode-svg';
import { useAuthStore } from '../../src/store/authStore';
import { vendorAPI } from '../../src/utils/api';
import { Analytics } from '../../src/types';

export default function ProfileScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { user, logout } = useAuthStore();
  const [showQR, setShowQR] = useState(false);
  const [qrData, setQRData] = useState<any>(null);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);

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

  useEffect(() => {
    loadData();
  }, []);

  const handleLogout = () => {
    Alert.alert(
      'Logout',
      'Are you sure you want to logout?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Logout',
          style: 'destructive',
          onPress: async () => {
            await logout();
            router.replace('/(auth)/login');
          },
        },
      ]
    );
  };

  const isShopOpen = user?.partner_status === 'available';

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <ScrollView style={styles.scrollView} showsVerticalScrollIndicator={false}>
        <View style={styles.header}>
          <Text style={styles.title}>Profile</Text>
        </View>

        {/* Shop Card with Status Display */}
        <View style={styles.shopCard}>
          <View style={styles.shopImageContainer}>
            {user?.vendor_shop_image ? (
              <Image source={{ uri: user.vendor_shop_image }} style={styles.shopImage} />
            ) : (
              <View style={styles.shopImagePlaceholder}>
                <Ionicons name="storefront" size={36} color="#6366F1" />
              </View>
            )}
          </View>
          <View style={styles.shopInfo}>
            <Text style={styles.shopName}>{user?.vendor_shop_name || 'Your Shop'}</Text>
            <Text style={styles.shopType}>{user?.vendor_shop_type}</Text>
            <View style={styles.shopMeta}>
              <View style={styles.ratingRow}>
                <Ionicons name="star" size={14} color="#F59E0B" />
                <Text style={styles.ratingText}>{user?.partner_rating?.toFixed(1) || '5.0'}</Text>
              </View>
              {/* Status Display (No Button) */}
              <View style={[styles.statusBadge, isShopOpen ? styles.statusBadgeOpen : styles.statusBadgeClosed]}>
                <View style={[styles.statusDot, isShopOpen ? styles.statusDotOpen : styles.statusDotClosed]} />
                <Text style={[styles.statusText, isShopOpen ? styles.statusTextOpen : styles.statusTextClosed]}>
                  {isShopOpen ? 'Online' : 'Offline'}
                </Text>
              </View>
            </View>
          </View>
        </View>

        {/* Stats Summary */}
        <View style={styles.statsCard}>
          <Text style={styles.sectionTitle}>Performance Summary</Text>
          <View style={styles.statsGrid}>
            <View style={styles.statItem}>
              <View style={[styles.statIconBg, { backgroundColor: '#DCFCE7' }]}>
                <Ionicons name="cash" size={18} color="#22C55E" />
              </View>
              <Text style={styles.statValue}>₹{analytics?.total_earnings?.toLocaleString() || 0}</Text>
              <Text style={styles.statLabel}>Total Earnings</Text>
            </View>
            <View style={styles.statItem}>
              <View style={[styles.statIconBg, { backgroundColor: '#EEF2FF' }]}>
                <Ionicons name="bag-check" size={18} color="#6366F1" />
              </View>
              <Text style={styles.statValue}>{analytics?.total_orders || 0}</Text>
              <Text style={styles.statLabel}>Total Orders</Text>
            </View>
            <View style={styles.statItem}>
              <View style={[styles.statIconBg, { backgroundColor: '#FEF3C7' }]}>
                <Ionicons name="cube" size={18} color="#F59E0B" />
              </View>
              <Text style={styles.statValue}>{analytics?.products?.total || 0}</Text>
              <Text style={styles.statLabel}>Products</Text>
            </View>
            <View style={styles.statItem}>
              <View style={[styles.statIconBg, { backgroundColor: '#FCE7F3' }]}>
                <Ionicons name="calendar" size={18} color="#EC4899" />
              </View>
              <Text style={styles.statValue}>₹{analytics?.month?.earnings?.toLocaleString() || 0}</Text>
              <Text style={styles.statLabel}>This Month</Text>
            </View>
          </View>
        </View>

        {/* QR Code Section */}
        <TouchableOpacity style={styles.qrCard} onPress={() => setShowQR(!showQR)}>
          <View style={styles.qrHeader}>
            <View style={styles.qrHeaderLeft}>
              <View style={styles.qrIconBg}>
                <Ionicons name="qr-code" size={22} color="#6366F1" />
              </View>
              <View style={styles.qrHeaderText}>
                <Text style={styles.qrTitle}>Shop QR Code</Text>
                <Text style={styles.qrSubtitle}>Customers can scan to visit your shop</Text>
              </View>
            </View>
            <Ionicons name={showQR ? 'chevron-up' : 'chevron-down'} size={24} color="#9CA3AF" />
          </View>
          {showQR && qrData && (
            <View style={styles.qrContainer}>
              <View style={styles.qrBox}>
                <QRCode
                  value={qrData.qr_url || `quickwish://vendor/${user?.user_id}`}
                  size={160}
                  backgroundColor="#FFFFFF"
                />
              </View>
              <Text style={styles.qrHint}>Share this QR with customers</Text>
            </View>
          )}
        </TouchableOpacity>

        {/* Shop Details */}
        <View style={styles.detailsCard}>
          <Text style={styles.sectionTitle}>Shop Details</Text>
          
          <View style={styles.detailRow}>
            <View style={styles.detailIconBg}>
              <Ionicons name="location" size={18} color="#6366F1" />
            </View>
            <View style={styles.detailContent}>
              <Text style={styles.detailLabel}>Address</Text>
              <Text style={styles.detailValue}>{user?.vendor_shop_address || 'Not set'}</Text>
            </View>
          </View>

          <View style={styles.detailRow}>
            <View style={styles.detailIconBg}>
              <Ionicons name="time" size={18} color="#6366F1" />
            </View>
            <View style={styles.detailContent}>
              <Text style={styles.detailLabel}>Opening Hours</Text>
              <Text style={styles.detailValue}>{user?.vendor_opening_hours || 'Not set'}</Text>
            </View>
          </View>

          <View style={styles.detailRow}>
            <View style={styles.detailIconBg}>
              <Ionicons name="call" size={18} color="#6366F1" />
            </View>
            <View style={styles.detailContent}>
              <Text style={styles.detailLabel}>Phone</Text>
              <Text style={styles.detailValue}>{user?.phone || 'Not set'}</Text>
            </View>
          </View>

          <View style={[styles.detailRow, { borderBottomWidth: 0 }]}>
            <View style={styles.detailIconBg}>
              <Ionicons name="bicycle" size={18} color="#6366F1" />
            </View>
            <View style={styles.detailContent}>
              <Text style={styles.detailLabel}>Own Delivery</Text>
              <Text style={styles.detailValue}>{user?.vendor_can_deliver ? 'Yes' : 'No'}</Text>
            </View>
          </View>
        </View>

        {/* Menu Items */}
        <View style={styles.menuCard}>
          <TouchableOpacity style={styles.menuItem}>
            <View style={[styles.menuIconBg, { backgroundColor: '#EEF2FF' }]}>
              <Ionicons name="create" size={18} color="#6366F1" />
            </View>
            <Text style={styles.menuText}>Edit Shop Profile</Text>
            <Ionicons name="chevron-forward" size={20} color="#D1D5DB" />
          </TouchableOpacity>

          <TouchableOpacity style={styles.menuItem}>
            <View style={[styles.menuIconBg, { backgroundColor: '#FEF3C7' }]}>
              <Ionicons name="notifications" size={18} color="#F59E0B" />
            </View>
            <Text style={styles.menuText}>Notification Settings</Text>
            <Ionicons name="chevron-forward" size={20} color="#D1D5DB" />
          </TouchableOpacity>

          <TouchableOpacity style={styles.menuItem}>
            <View style={[styles.menuIconBg, { backgroundColor: '#DCFCE7' }]}>
              <Ionicons name="help-circle" size={18} color="#22C55E" />
            </View>
            <Text style={styles.menuText}>Help & Support</Text>
            <Ionicons name="chevron-forward" size={20} color="#D1D5DB" />
          </TouchableOpacity>

          <TouchableOpacity style={[styles.menuItem, { borderBottomWidth: 0 }]}>
            <View style={[styles.menuIconBg, { backgroundColor: '#F3F4F6' }]}>
              <Ionicons name="document-text" size={18} color="#6B7280" />
            </View>
            <Text style={styles.menuText}>Terms & Privacy</Text>
            <Ionicons name="chevron-forward" size={20} color="#D1D5DB" />
          </TouchableOpacity>
        </View>

        {/* Logout Button */}
        <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
          <Ionicons name="log-out-outline" size={22} color="#DC2626" />
          <Text style={styles.logoutText}>Logout</Text>
        </TouchableOpacity>

        <Text style={styles.version}>QuickWish Vendor v1.0.0</Text>

        <View style={{ height: 100 }} />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F8FAFC',
  },
  scrollView: {
    flex: 1,
  },
  header: {
    paddingHorizontal: 20,
    paddingVertical: 16,
  },
  title: {
    fontSize: 28,
    fontWeight: '800',
    color: '#111827',
  },
  // Shop Card
  shopCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    marginHorizontal: 16,
    padding: 16,
    borderRadius: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.06,
    shadowRadius: 12,
    elevation: 3,
  },
  shopImageContainer: {
    width: 72,
    height: 72,
    borderRadius: 18,
    overflow: 'hidden',
  },
  shopImage: {
    width: '100%',
    height: '100%',
  },
  shopImagePlaceholder: {
    width: '100%',
    height: '100%',
    backgroundColor: '#EEF2FF',
    justifyContent: 'center',
    alignItems: 'center',
  },
  shopInfo: {
    flex: 1,
    marginLeft: 16,
  },
  shopName: {
    fontSize: 18,
    fontWeight: '700',
    color: '#111827',
  },
  shopType: {
    fontSize: 13,
    color: '#6B7280',
    marginTop: 2,
  },
  shopMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
    gap: 12,
  },
  ratingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  ratingText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#374151',
  },
  // Status Badge (Display Only)
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 20,
    gap: 6,
  },
  statusBadgeOpen: {
    backgroundColor: '#DCFCE7',
  },
  statusBadgeClosed: {
    backgroundColor: '#F3F4F6',
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  statusDotOpen: {
    backgroundColor: '#22C55E',
  },
  statusDotClosed: {
    backgroundColor: '#9CA3AF',
  },
  statusText: {
    fontSize: 12,
    fontWeight: '600',
  },
  statusTextOpen: {
    color: '#22C55E',
  },
  statusTextClosed: {
    color: '#6B7280',
  },
  // Stats Card
  statsCard: {
    backgroundColor: '#FFFFFF',
    marginHorizontal: 16,
    marginTop: 16,
    padding: 20,
    borderRadius: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 8,
    elevation: 2,
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: '#6B7280',
    marginBottom: 16,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  statItem: {
    width: '50%',
    paddingVertical: 12,
    paddingHorizontal: 4,
  },
  statIconBg: {
    width: 36,
    height: 36,
    borderRadius: 10,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 8,
  },
  statValue: {
    fontSize: 20,
    fontWeight: '700',
    color: '#111827',
  },
  statLabel: {
    fontSize: 12,
    color: '#6B7280',
    marginTop: 2,
  },
  // QR Card
  qrCard: {
    backgroundColor: '#FFFFFF',
    marginHorizontal: 16,
    marginTop: 16,
    padding: 16,
    borderRadius: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 8,
    elevation: 2,
  },
  qrHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  qrHeaderLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  qrIconBg: {
    width: 44,
    height: 44,
    backgroundColor: '#EEF2FF',
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
  },
  qrHeaderText: {
    flex: 1,
  },
  qrTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#111827',
  },
  qrSubtitle: {
    fontSize: 13,
    color: '#6B7280',
    marginTop: 2,
  },
  qrContainer: {
    alignItems: 'center',
    paddingVertical: 24,
    marginTop: 16,
    borderTopWidth: 1,
    borderTopColor: '#E5E7EB',
  },
  qrBox: {
    padding: 16,
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    borderWidth: 2,
    borderColor: '#E5E7EB',
  },
  qrHint: {
    marginTop: 16,
    fontSize: 13,
    color: '#9CA3AF',
  },
  // Details Card
  detailsCard: {
    backgroundColor: '#FFFFFF',
    marginHorizontal: 16,
    marginTop: 16,
    padding: 20,
    borderRadius: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 8,
    elevation: 2,
  },
  detailRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#F3F4F6',
  },
  detailIconBg: {
    width: 36,
    height: 36,
    backgroundColor: '#EEF2FF',
    borderRadius: 10,
    justifyContent: 'center',
    alignItems: 'center',
  },
  detailContent: {
    flex: 1,
    marginLeft: 14,
  },
  detailLabel: {
    fontSize: 12,
    color: '#9CA3AF',
  },
  detailValue: {
    fontSize: 15,
    color: '#111827',
    fontWeight: '500',
    marginTop: 2,
  },
  // Menu Card
  menuCard: {
    backgroundColor: '#FFFFFF',
    marginHorizontal: 16,
    marginTop: 16,
    borderRadius: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 8,
    elevation: 2,
    overflow: 'hidden',
  },
  menuItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#F3F4F6',
  },
  menuIconBg: {
    width: 36,
    height: 36,
    borderRadius: 10,
    justifyContent: 'center',
    alignItems: 'center',
  },
  menuText: {
    flex: 1,
    fontSize: 15,
    color: '#374151',
    fontWeight: '500',
    marginLeft: 14,
  },
  // Logout
  logoutBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FEE2E2',
    marginHorizontal: 16,
    marginTop: 24,
    padding: 16,
    borderRadius: 14,
    gap: 8,
  },
  logoutText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#DC2626',
  },
  version: {
    textAlign: 'center',
    fontSize: 12,
    color: '#9CA3AF',
    marginTop: 24,
  },
});
