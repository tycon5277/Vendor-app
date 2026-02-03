import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
  Image,
  Switch,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import QRCode from 'react-native-qrcode-svg';
import { useAuthStore } from '../../src/store/authStore';
import { vendorAPI } from '../../src/utils/api';
import { Analytics } from '../../src/types';

export default function ProfileScreen() {
  const router = useRouter();
  const { user, setUser, logout } = useAuthStore();
  const [showQR, setShowQR] = useState(false);
  const [qrData, setQRData] = useState<any>(null);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [shopOpen, setShopOpen] = useState(user?.partner_status === 'available');

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

  const toggleShopStatus = async () => {
    const newStatus = shopOpen ? 'offline' : 'available';
    try {
      await vendorAPI.updateStatus(newStatus);
      setShopOpen(!shopOpen);
      if (user) {
        setUser({ ...user, partner_status: newStatus });
      }
    } catch (error) {
      Alert.alert('Error', 'Failed to update shop status');
    }
  };

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

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView style={styles.scrollView} showsVerticalScrollIndicator={false}>
        <View style={styles.header}>
          <Text style={styles.title}>Profile</Text>
        </View>

        {/* Shop Card */}
        <View style={styles.shopCard}>
          <View style={styles.shopImageContainer}>
            {user?.vendor_shop_image ? (
              <Image source={{ uri: user.vendor_shop_image }} style={styles.shopImage} />
            ) : (
              <View style={styles.shopImagePlaceholder}>
                <Ionicons name="storefront" size={40} color="#6366F1" />
              </View>
            )}
          </View>
          <View style={styles.shopInfo}>
            <Text style={styles.shopName}>{user?.vendor_shop_name || 'Your Shop'}</Text>
            <Text style={styles.shopType}>{user?.vendor_shop_type}</Text>
            <View style={styles.ratingRow}>
              <Ionicons name="star" size={16} color="#F59E0B" />
              <Text style={styles.ratingText}>{user?.partner_rating?.toFixed(1) || '5.0'}</Text>
            </View>
          </View>
          <View style={styles.statusToggle}>
            <Text style={styles.statusLabel}>{shopOpen ? 'OPEN' : 'CLOSED'}</Text>
            <Switch
              value={shopOpen}
              onValueChange={toggleShopStatus}
              trackColor={{ false: '#E5E7EB', true: '#86EFAC' }}
              thumbColor={shopOpen ? '#22C55E' : '#9CA3AF'}
            />
          </View>
        </View>

        {/* Stats Summary */}
        <View style={styles.statsCard}>
          <Text style={styles.sectionTitle}>Performance Summary</Text>
          <View style={styles.statsGrid}>
            <View style={styles.statItem}>
              <Text style={styles.statValue}>₹{analytics?.total_earnings?.toLocaleString() || 0}</Text>
              <Text style={styles.statLabel}>Total Earnings</Text>
            </View>
            <View style={styles.statItem}>
              <Text style={styles.statValue}>{analytics?.total_orders || 0}</Text>
              <Text style={styles.statLabel}>Total Orders</Text>
            </View>
            <View style={styles.statItem}>
              <Text style={styles.statValue}>{analytics?.products?.total || 0}</Text>
              <Text style={styles.statLabel}>Products</Text>
            </View>
            <View style={styles.statItem}>
              <Text style={styles.statValue}>₹{analytics?.month?.earnings?.toLocaleString() || 0}</Text>
              <Text style={styles.statLabel}>This Month</Text>
            </View>
          </View>
        </View>

        {/* QR Code Section */}
        <TouchableOpacity style={styles.qrCard} onPress={() => setShowQR(!showQR)}>
          <View style={styles.qrHeader}>
            <View style={styles.qrHeaderLeft}>
              <Ionicons name="qr-code" size={24} color="#6366F1" />
              <View style={styles.qrHeaderText}>
                <Text style={styles.qrTitle}>Shop QR Code</Text>
                <Text style={styles.qrSubtitle}>Customers can scan to visit your shop</Text>
              </View>
            </View>
            <Ionicons name={showQR ? 'chevron-up' : 'chevron-down'} size={24} color="#9CA3AF" />
          </View>
          {showQR && qrData && (
            <View style={styles.qrContainer}>
              <QRCode
                value={qrData.qr_url || `quickwish://vendor/${user?.user_id}`}
                size={180}
                backgroundColor="#FFFFFF"
              />
              <Text style={styles.qrHint}>Share this QR with customers</Text>
            </View>
          )}
        </TouchableOpacity>

        {/* Shop Details */}
        <View style={styles.detailsCard}>
          <Text style={styles.sectionTitle}>Shop Details</Text>
          
          <View style={styles.detailRow}>
            <Ionicons name="location-outline" size={22} color="#6B7280" />
            <View style={styles.detailContent}>
              <Text style={styles.detailLabel}>Address</Text>
              <Text style={styles.detailValue}>{user?.vendor_shop_address || 'Not set'}</Text>
            </View>
          </View>

          <View style={styles.detailRow}>
            <Ionicons name="time-outline" size={22} color="#6B7280" />
            <View style={styles.detailContent}>
              <Text style={styles.detailLabel}>Opening Hours</Text>
              <Text style={styles.detailValue}>{user?.vendor_opening_hours || 'Not set'}</Text>
            </View>
          </View>

          <View style={styles.detailRow}>
            <Ionicons name="call-outline" size={22} color="#6B7280" />
            <View style={styles.detailContent}>
              <Text style={styles.detailLabel}>Phone</Text>
              <Text style={styles.detailValue}>{user?.phone || 'Not set'}</Text>
            </View>
          </View>

          <View style={styles.detailRow}>
            <Ionicons name="bicycle-outline" size={22} color="#6B7280" />
            <View style={styles.detailContent}>
              <Text style={styles.detailLabel}>Own Delivery</Text>
              <Text style={styles.detailValue}>{user?.vendor_can_deliver ? 'Yes' : 'No'}</Text>
            </View>
          </View>
        </View>

        {/* Menu Items */}
        <View style={styles.menuCard}>
          <TouchableOpacity style={styles.menuItem}>
            <Ionicons name="create-outline" size={22} color="#6B7280" />
            <Text style={styles.menuText}>Edit Shop Profile</Text>
            <Ionicons name="chevron-forward" size={20} color="#D1D5DB" />
          </TouchableOpacity>

          <TouchableOpacity style={styles.menuItem}>
            <Ionicons name="notifications-outline" size={22} color="#6B7280" />
            <Text style={styles.menuText}>Notification Settings</Text>
            <Ionicons name="chevron-forward" size={20} color="#D1D5DB" />
          </TouchableOpacity>

          <TouchableOpacity style={styles.menuItem}>
            <Ionicons name="help-circle-outline" size={22} color="#6B7280" />
            <Text style={styles.menuText}>Help & Support</Text>
            <Ionicons name="chevron-forward" size={20} color="#D1D5DB" />
          </TouchableOpacity>

          <TouchableOpacity style={styles.menuItem}>
            <Ionicons name="document-text-outline" size={22} color="#6B7280" />
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
    paddingHorizontal: 20,
    paddingVertical: 16,
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    color: '#111827',
  },
  shopCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    marginHorizontal: 16,
    padding: 16,
    borderRadius: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 2,
  },
  shopImageContainer: {
    width: 64,
    height: 64,
    borderRadius: 12,
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
    marginLeft: 14,
  },
  shopName: {
    fontSize: 17,
    fontWeight: '700',
    color: '#111827',
  },
  shopType: {
    fontSize: 13,
    color: '#6B7280',
    marginTop: 2,
  },
  ratingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 4,
    gap: 4,
  },
  ratingText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#374151',
  },
  statusToggle: {
    alignItems: 'center',
  },
  statusLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: '#6B7280',
    marginBottom: 4,
  },
  statsCard: {
    backgroundColor: '#FFFFFF',
    marginHorizontal: 16,
    marginTop: 16,
    padding: 16,
    borderRadius: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 2,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: '600',
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
  qrCard: {
    backgroundColor: '#FFFFFF',
    marginHorizontal: 16,
    marginTop: 16,
    padding: 16,
    borderRadius: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
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
  qrHint: {
    marginTop: 16,
    fontSize: 13,
    color: '#9CA3AF',
  },
  detailsCard: {
    backgroundColor: '#FFFFFF',
    marginHorizontal: 16,
    marginTop: 16,
    padding: 16,
    borderRadius: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 2,
  },
  detailRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#F3F4F6',
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
    marginTop: 2,
  },
  menuCard: {
    backgroundColor: '#FFFFFF',
    marginHorizontal: 16,
    marginTop: 16,
    borderRadius: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
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
  menuText: {
    flex: 1,
    fontSize: 15,
    color: '#374151',
    marginLeft: 14,
  },
  logoutBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FEE2E2',
    marginHorizontal: 16,
    marginTop: 24,
    padding: 16,
    borderRadius: 12,
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
