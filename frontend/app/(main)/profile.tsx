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
  Dimensions,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import QRCode from 'react-native-qrcode-svg';
import { useAuthStore } from '../../src/store/authStore';
import { vendorAPI } from '../../src/utils/api';
import { Analytics } from '../../src/types';

const { width } = Dimensions.get('window');

export default function ProfileScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { user, logout } = useAuthStore();
  const [showQR, setShowQR] = useState(false);
  const [qrData, setQRData] = useState<any>(null);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const fadeAnim = useRef(new Animated.Value(0)).current;
  const slideAnim = useRef(new Animated.Value(30)).current;

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
    Animated.parallel([
      Animated.timing(fadeAnim, {
        toValue: 1,
        duration: 500,
        useNativeDriver: true,
      }),
      Animated.timing(slideAnim, {
        toValue: 0,
        duration: 500,
        useNativeDriver: true,
      }),
    ]).start();
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
  
  // Calculate achievements
  const totalOrders = analytics?.total_orders || 0;
  const achievements = [
    { id: 1, name: 'First Sale', icon: 'star', unlocked: totalOrders >= 1 },
    { id: 2, name: '10 Orders', icon: 'ribbon', unlocked: totalOrders >= 10 },
    { id: 3, name: '50 Orders', icon: 'trophy', unlocked: totalOrders >= 50 },
    { id: 4, name: '100 Orders', icon: 'medal', unlocked: totalOrders >= 100 },
  ];

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <ScrollView style={styles.scrollView} showsVerticalScrollIndicator={false}>
        <Animated.View style={{ opacity: fadeAnim, transform: [{ translateY: slideAnim }] }}>
          {/* Header */}
          <View style={styles.header}>
            <Text style={styles.title}>Profile</Text>
            <TouchableOpacity style={styles.settingsBtn}>
              <Ionicons name="settings-outline" size={24} color="#374151" />
            </TouchableOpacity>
          </View>

          {/* Profile Card */}
          <View style={styles.profileCard}>
            <View style={styles.profileHeader}>
              <View style={styles.profileImageContainer}>
                {user?.vendor_shop_image ? (
                  <Image source={{ uri: user.vendor_shop_image }} style={styles.profileImage} />
                ) : (
                  <View style={styles.profileImagePlaceholder}>
                    <Ionicons name="storefront" size={40} color="#FFFFFF" />
                  </View>
                )}
                <View style={[styles.statusDot, isShopOpen ? styles.statusDotOnline : styles.statusDotOffline]} />
              </View>
              
              <View style={styles.profileInfo}>
                <Text style={styles.shopName}>{user?.vendor_shop_name || 'Your Shop'}</Text>
                <Text style={styles.shopType}>{user?.vendor_shop_type}</Text>
                
                <View style={styles.profileMeta}>
                  <View style={styles.ratingBadge}>
                    <Ionicons name="star" size={14} color="#F59E0B" />
                    <Text style={styles.ratingText}>{user?.partner_rating?.toFixed(1) || '5.0'}</Text>
                  </View>
                  <View style={[
                    styles.statusBadge,
                    isShopOpen ? styles.statusBadgeOnline : styles.statusBadgeOffline
                  ]}>
                    <View style={[
                      styles.statusIndicator,
                      isShopOpen ? styles.statusIndicatorOnline : styles.statusIndicatorOffline
                    ]} />
                    <Text style={[
                      styles.statusText,
                      isShopOpen ? styles.statusTextOnline : styles.statusTextOffline
                    ]}>
                      {isShopOpen ? 'Online' : 'Offline'}
                    </Text>
                  </View>
                </View>
              </View>
            </View>
            
            <TouchableOpacity style={styles.editProfileBtn}>
              <Ionicons name="create-outline" size={18} color="#6366F1" />
              <Text style={styles.editProfileText}>Edit Profile</Text>
            </TouchableOpacity>
          </View>

          {/* Achievements */}
          <View style={styles.achievementsCard}>
            <View style={styles.sectionHeader}>
              <Text style={styles.sectionTitle}>Achievements</Text>
              <Text style={styles.sectionSubtitle}>{achievements.filter(a => a.unlocked).length}/4 unlocked</Text>
            </View>
            <View style={styles.achievementsRow}>
              {achievements.map((achievement) => (
                <View key={achievement.id} style={styles.achievementItem}>
                  <View style={[
                    styles.achievementIcon,
                    achievement.unlocked ? styles.achievementIconUnlocked : styles.achievementIconLocked
                  ]}>
                    <Ionicons
                      name={achievement.icon as any}
                      size={24}
                      color={achievement.unlocked ? '#FFFFFF' : '#D1D5DB'}
                    />
                  </View>
                  <Text style={[
                    styles.achievementName,
                    !achievement.unlocked && styles.achievementNameLocked
                  ]}>{achievement.name}</Text>
                </View>
              ))}
            </View>
          </View>

          {/* Stats Grid */}
          <View style={styles.statsCard}>
            <Text style={styles.sectionTitle}>Performance</Text>
            <View style={styles.statsGrid}>
              <View style={styles.statItem}>
                <View style={[styles.statIconBg, { backgroundColor: '#DCFCE7' }]}>
                  <Ionicons name="wallet" size={22} color="#22C55E" />
                </View>
                <Text style={styles.statValue}>₹{(analytics?.total_earnings || 0).toLocaleString()}</Text>
                <Text style={styles.statLabel}>Total Earnings</Text>
              </View>
              <View style={styles.statItem}>
                <View style={[styles.statIconBg, { backgroundColor: '#EEF2FF' }]}>
                  <Ionicons name="bag-check" size={22} color="#6366F1" />
                </View>
                <Text style={styles.statValue}>{analytics?.total_orders || 0}</Text>
                <Text style={styles.statLabel}>Total Orders</Text>
              </View>
              <View style={styles.statItem}>
                <View style={[styles.statIconBg, { backgroundColor: '#FEF3C7' }]}>
                  <Ionicons name="cube" size={22} color="#F59E0B" />
                </View>
                <Text style={styles.statValue}>{analytics?.products?.total || 0}</Text>
                <Text style={styles.statLabel}>Products</Text>
              </View>
              <View style={styles.statItem}>
                <View style={[styles.statIconBg, { backgroundColor: '#FCE7F3' }]}>
                  <Ionicons name="trending-up" size={22} color="#EC4899" />
                </View>
                <Text style={styles.statValue}>₹{(analytics?.month?.earnings || 0).toLocaleString()}</Text>
                <Text style={styles.statLabel}>This Month</Text>
              </View>
            </View>
          </View>

          {/* QR Code Section */}
          <TouchableOpacity style={styles.qrCard} onPress={() => setShowQR(!showQR)} activeOpacity={0.8}>
            <View style={styles.qrHeader}>
              <View style={styles.qrHeaderLeft}>
                <View style={styles.qrIconBg}>
                  <Ionicons name="qr-code" size={24} color="#6366F1" />
                </View>
                <View style={styles.qrHeaderText}>
                  <Text style={styles.qrTitle}>Shop QR Code</Text>
                  <Text style={styles.qrSubtitle}>Share with customers to visit your shop</Text>
                </View>
              </View>
              <Ionicons name={showQR ? 'chevron-up' : 'chevron-down'} size={24} color="#9CA3AF" />
            </View>
            {showQR && qrData && (
              <View style={styles.qrContainer}>
                <View style={styles.qrBox}>
                  <QRCode
                    value={qrData.qr_url || `quickwish://vendor/${user?.user_id}`}
                    size={180}
                    backgroundColor="#FFFFFF"
                    color="#111827"
                  />
                </View>
                <View style={styles.qrActions}>
                  <TouchableOpacity style={styles.qrActionBtn}>
                    <Ionicons name="download-outline" size={20} color="#6366F1" />
                    <Text style={styles.qrActionText}>Save</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={styles.qrActionBtn}>
                    <Ionicons name="share-outline" size={20} color="#6366F1" />
                    <Text style={styles.qrActionText}>Share</Text>
                  </TouchableOpacity>
                </View>
              </View>
            )}
          </TouchableOpacity>

          {/* Shop Details */}
          <View style={styles.detailsCard}>
            <Text style={styles.sectionTitle}>Shop Details</Text>
            
            <View style={styles.detailRow}>
              <View style={styles.detailIconBg}>
                <Ionicons name="location" size={20} color="#6366F1" />
              </View>
              <View style={styles.detailContent}>
                <Text style={styles.detailLabel}>Address</Text>
                <Text style={styles.detailValue}>{user?.vendor_shop_address || 'Not set'}</Text>
              </View>
              <TouchableOpacity>
                <Ionicons name="chevron-forward" size={20} color="#D1D5DB" />
              </TouchableOpacity>
            </View>

            <View style={styles.detailRow}>
              <View style={styles.detailIconBg}>
                <Ionicons name="time" size={20} color="#6366F1" />
              </View>
              <View style={styles.detailContent}>
                <Text style={styles.detailLabel}>Opening Hours</Text>
                <Text style={styles.detailValue}>{user?.vendor_opening_hours || 'Not set'}</Text>
              </View>
              <TouchableOpacity>
                <Ionicons name="chevron-forward" size={20} color="#D1D5DB" />
              </TouchableOpacity>
            </View>

            <View style={styles.detailRow}>
              <View style={styles.detailIconBg}>
                <Ionicons name="call" size={20} color="#6366F1" />
              </View>
              <View style={styles.detailContent}>
                <Text style={styles.detailLabel}>Phone</Text>
                <Text style={styles.detailValue}>{user?.phone || 'Not set'}</Text>
              </View>
              <TouchableOpacity>
                <Ionicons name="chevron-forward" size={20} color="#D1D5DB" />
              </TouchableOpacity>
            </View>

            <View style={[styles.detailRow, { borderBottomWidth: 0 }]}>
              <View style={styles.detailIconBg}>
                <Ionicons name="bicycle" size={20} color="#6366F1" />
              </View>
              <View style={styles.detailContent}>
                <Text style={styles.detailLabel}>Own Delivery</Text>
                <Text style={styles.detailValue}>{user?.vendor_can_deliver ? 'Yes' : 'No'}</Text>
              </View>
              <TouchableOpacity>
                <Ionicons name="chevron-forward" size={20} color="#D1D5DB" />
              </TouchableOpacity>
            </View>
          </View>

          {/* Menu Items */}
          <View style={styles.menuCard}>
            <TouchableOpacity style={styles.menuItem}>
              <View style={[styles.menuIconBg, { backgroundColor: '#EEF2FF' }]}>
                <Ionicons name="notifications" size={20} color="#6366F1" />
              </View>
              <Text style={styles.menuText}>Notifications</Text>
              <View style={styles.menuBadge}>
                <Text style={styles.menuBadgeText}>3</Text>
              </View>
              <Ionicons name="chevron-forward" size={20} color="#D1D5DB" />
            </TouchableOpacity>

            <TouchableOpacity style={styles.menuItem}>
              <View style={[styles.menuIconBg, { backgroundColor: '#DCFCE7' }]}>
                <Ionicons name="card" size={20} color="#22C55E" />
              </View>
              <Text style={styles.menuText}>Payment Settings</Text>
              <Ionicons name="chevron-forward" size={20} color="#D1D5DB" />
            </TouchableOpacity>

            <TouchableOpacity style={styles.menuItem}>
              <View style={[styles.menuIconBg, { backgroundColor: '#FEF3C7' }]}>
                <Ionicons name="help-circle" size={20} color="#F59E0B" />
              </View>
              <Text style={styles.menuText}>Help & Support</Text>
              <Ionicons name="chevron-forward" size={20} color="#D1D5DB" />
            </TouchableOpacity>

            <TouchableOpacity style={[styles.menuItem, { borderBottomWidth: 0 }]}>
              <View style={[styles.menuIconBg, { backgroundColor: '#F3F4F6' }]}>
                <Ionicons name="document-text" size={20} color="#6B7280" />
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
        </Animated.View>
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
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 16,
  },
  title: {
    fontSize: 28,
    fontWeight: '800',
    color: '#111827',
  },
  settingsBtn: {
    width: 44,
    height: 44,
    backgroundColor: '#FFFFFF',
    borderRadius: 22,
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  // Profile Card
  profileCard: {
    backgroundColor: '#FFFFFF',
    marginHorizontal: 16,
    padding: 20,
    borderRadius: 24,
    shadowColor: '#6366F1',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 12,
    elevation: 4,
  },
  profileHeader: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  profileImageContainer: {
    position: 'relative',
  },
  profileImage: {
    width: 80,
    height: 80,
    borderRadius: 24,
  },
  profileImagePlaceholder: {
    width: 80,
    height: 80,
    borderRadius: 24,
    backgroundColor: '#6366F1',
    justifyContent: 'center',
    alignItems: 'center',
  },
  statusDot: {
    position: 'absolute',
    bottom: 2,
    right: 2,
    width: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 3,
    borderColor: '#FFFFFF',
  },
  statusDotOnline: {
    backgroundColor: '#22C55E',
  },
  statusDotOffline: {
    backgroundColor: '#9CA3AF',
  },
  profileInfo: {
    flex: 1,
    marginLeft: 16,
  },
  shopName: {
    fontSize: 20,
    fontWeight: '700',
    color: '#111827',
  },
  shopType: {
    fontSize: 14,
    color: '#6B7280',
    marginTop: 2,
  },
  profileMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 10,
    gap: 10,
  },
  ratingBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FEF3C7',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
    gap: 4,
  },
  ratingText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#D97706',
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    gap: 6,
  },
  statusBadgeOnline: {
    backgroundColor: '#DCFCE7',
  },
  statusBadgeOffline: {
    backgroundColor: '#F3F4F6',
  },
  statusIndicator: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  statusIndicatorOnline: {
    backgroundColor: '#22C55E',
  },
  statusIndicatorOffline: {
    backgroundColor: '#9CA3AF',
  },
  statusText: {
    fontSize: 12,
    fontWeight: '600',
  },
  statusTextOnline: {
    color: '#22C55E',
  },
  statusTextOffline: {
    color: '#6B7280',
  },
  editProfileBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#EEF2FF',
    marginTop: 16,
    paddingVertical: 12,
    borderRadius: 12,
    gap: 8,
  },
  editProfileText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#6366F1',
  },
  // Achievements
  achievementsCard: {
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
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#111827',
  },
  sectionSubtitle: {
    fontSize: 13,
    color: '#6B7280',
  },
  achievementsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  achievementItem: {
    alignItems: 'center',
    width: (width - 72) / 4,
  },
  achievementIcon: {
    width: 52,
    height: 52,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 8,
  },
  achievementIconUnlocked: {
    backgroundColor: '#6366F1',
  },
  achievementIconLocked: {
    backgroundColor: '#F3F4F6',
  },
  achievementName: {
    fontSize: 11,
    fontWeight: '600',
    color: '#374151',
    textAlign: 'center',
  },
  achievementNameLocked: {
    color: '#9CA3AF',
  },
  // Stats
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
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginTop: 8,
  },
  statItem: {
    width: '50%',
    paddingVertical: 12,
    paddingHorizontal: 4,
  },
  statIconBg: {
    width: 44,
    height: 44,
    borderRadius: 14,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 10,
  },
  statValue: {
    fontSize: 22,
    fontWeight: '700',
    color: '#111827',
  },
  statLabel: {
    fontSize: 13,
    color: '#6B7280',
    marginTop: 2,
  },
  // QR Card
  qrCard: {
    backgroundColor: '#FFFFFF',
    marginHorizontal: 16,
    marginTop: 16,
    padding: 18,
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
    flex: 1,
  },
  qrIconBg: {
    width: 48,
    height: 48,
    backgroundColor: '#EEF2FF',
    borderRadius: 14,
    justifyContent: 'center',
    alignItems: 'center',
  },
  qrHeaderText: {
    flex: 1,
    marginLeft: 14,
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
    paddingTop: 24,
    marginTop: 18,
    borderTopWidth: 1,
    borderTopColor: '#E5E7EB',
  },
  qrBox: {
    padding: 20,
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    borderWidth: 2,
    borderColor: '#E5E7EB',
  },
  qrActions: {
    flexDirection: 'row',
    marginTop: 20,
    gap: 16,
  },
  qrActionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#EEF2FF',
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 10,
    gap: 8,
  },
  qrActionText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#6366F1',
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
    alignItems: 'center',
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#F3F4F6',
  },
  detailIconBg: {
    width: 40,
    height: 40,
    backgroundColor: '#EEF2FF',
    borderRadius: 12,
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
    width: 40,
    height: 40,
    borderRadius: 12,
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
  menuBadge: {
    backgroundColor: '#EF4444',
    minWidth: 22,
    height: 22,
    borderRadius: 11,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 8,
    paddingHorizontal: 6,
  },
  menuBadgeText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#FFFFFF',
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
    borderRadius: 16,
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
