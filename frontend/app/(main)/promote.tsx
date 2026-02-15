import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  Image,
  TextInput,
  Modal,
  Dimensions,
  ActivityIndicator,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useAuthStore } from '../../src/store/authStore';
import { useAlert } from '../../src/context/AlertContext';
import Constants from 'expo-constants';

const { width } = Dimensions.get('window');
const BACKEND_URL = Constants.expoConfig?.extra?.EXPO_PUBLIC_BACKEND_URL || 
  process.env.EXPO_PUBLIC_BACKEND_URL || 
  'https://vendor-wisher-sync.preview.emergentagent.com';

interface PromotionStats {
  active_promotions: number;
  total_reach: number;
  total_clicks: number;
  total_spent: number;
  posts_count: number;
  total_likes: number;
  total_comments: number;
  followers: number;
}

interface Post {
  post_id: string;
  content: string;
  images: string[];
  likes: number;
  comments: number;
  created_at: string;
  is_promoted: boolean;
}

interface Promotion {
  promotion_id: string;
  type: string;
  budget: number;
  spent: number;
  impressions: number;
  clicks: number;
  start_date: string;
  end_date: string;
  status: string;
}

export default function PromoteScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { token } = useAuthStore();
  const { showAlert } = useAlert();
  
  const [refreshing, setRefreshing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<PromotionStats | null>(null);
  const [posts, setPosts] = useState<Post[]>([]);
  const [promotions, setPromotions] = useState<Promotion[]>([]);
  
  // Modal states
  const [showCreatePostModal, setShowCreatePostModal] = useState(false);
  const [showCreatePromoModal, setShowCreatePromoModal] = useState(false);
  const [postContent, setPostContent] = useState('');
  const [selectedPromoType, setSelectedPromoType] = useState('featured_listing');
  const [promoDuration, setPromoDuration] = useState(7);
  const [creating, setCreating] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const headers = { Authorization: `Bearer ${token}` };
      
      // Fetch stats
      const statsRes = await fetch(`${BACKEND_URL}/api/vendor/promotions/stats`, { headers });
      if (statsRes.ok) {
        setStats(await statsRes.json());
      }
      
      // Fetch posts
      const postsRes = await fetch(`${BACKEND_URL}/api/vendor/posts`, { headers });
      if (postsRes.ok) {
        setPosts(await postsRes.json());
      }
      
      // Fetch promotions
      const promosRes = await fetch(`${BACKEND_URL}/api/vendor/promotions`, { headers });
      if (promosRes.ok) {
        setPromotions(await promosRes.json());
      }
    } catch (error) {
      console.error('Error fetching promotion data:', error);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchData();
    setRefreshing(false);
  };

  const createPost = async () => {
    if (!postContent.trim()) {
      showAlert({ type: 'error', title: 'Error', message: 'Please enter post content' });
      return;
    }
    
    setCreating(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/vendor/posts`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          content: postContent,
          images: [],
          tagged_products: [],
          is_promoted: false,
        }),
      });
      
      if (res.ok) {
        showAlert({ type: 'success', title: 'Success', message: 'Post created!' });
        setPostContent('');
        setShowCreatePostModal(false);
        fetchData();
      } else {
        throw new Error('Failed to create post');
      }
    } catch (error) {
      showAlert({ type: 'error', title: 'Error', message: 'Failed to create post' });
    } finally {
      setCreating(false);
    }
  };

  const createPromotion = async () => {
    setCreating(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/vendor/promotions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          type: selectedPromoType,
          duration_days: promoDuration,
        }),
      });
      
      if (res.ok) {
        const data = await res.json();
        showAlert({ 
          type: 'success', 
          title: 'Promotion Created', 
          message: `Your ${selectedPromoType.replace('_', ' ')} is now active! Cost: ₹${data.cost}` 
        });
        setShowCreatePromoModal(false);
        fetchData();
      } else {
        throw new Error('Failed to create promotion');
      }
    } catch (error) {
      showAlert({ type: 'error', title: 'Error', message: 'Failed to create promotion' });
    } finally {
      setCreating(false);
    }
  };

  const getPromoTypeInfo = (type: string) => {
    const info: Record<string, { icon: string; color: string; price: number; desc: string }> = {
      featured_listing: { 
        icon: 'star', 
        color: '#F59E0B', 
        price: 99, 
        desc: 'Appear at top of Local Hub search results' 
      },
      visibility_boost: { 
        icon: 'eye', 
        color: '#3B82F6', 
        price: 149, 
        desc: 'Reach customers beyond your normal delivery area' 
      },
      explore_promotion: { 
        icon: 'compass', 
        color: '#EC4899', 
        price: 199, 
        desc: 'Get featured in Explore tab across the city' 
      },
    };
    return info[type] || { icon: 'help', color: '#6B7280', price: 0, desc: '' };
  };

  const formatNumber = (num: number) => {
    if (num >= 1000) return `${(num / 1000).toFixed(1)}k`;
    return num.toString();
  };

  if (loading) {
    return (
      <View style={[styles.container, styles.centered]}>
        <ActivityIndicator size="large" color="#6366F1" />
      </View>
    );
  }

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={24} color="#111827" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Promote Your Shop</Text>
        <View style={{ width: 40 }} />
      </View>

      <ScrollView
        style={styles.scrollView}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={['#6366F1']} />
        }
      >
        {/* Stats Overview */}
        <View style={styles.statsCard}>
          <View style={styles.statsHeader}>
            <Text style={styles.statsTitle}>Your Reach</Text>
            <View style={styles.liveIndicator}>
              <View style={styles.liveDot} />
              <Text style={styles.liveText}>Live</Text>
            </View>
          </View>
          
          <View style={styles.statsGrid}>
            <View style={styles.statItem}>
              <Ionicons name="eye" size={24} color="#6366F1" />
              <Text style={styles.statValue}>{formatNumber(stats?.total_reach || 0)}</Text>
              <Text style={styles.statLabel}>Impressions</Text>
            </View>
            <View style={styles.statItem}>
              <Ionicons name="hand-left" size={24} color="#22C55E" />
              <Text style={styles.statValue}>{formatNumber(stats?.total_clicks || 0)}</Text>
              <Text style={styles.statLabel}>Clicks</Text>
            </View>
            <View style={styles.statItem}>
              <Ionicons name="people" size={24} color="#F59E0B" />
              <Text style={styles.statValue}>{formatNumber(stats?.followers || 0)}</Text>
              <Text style={styles.statLabel}>Followers</Text>
            </View>
            <View style={styles.statItem}>
              <Ionicons name="heart" size={24} color="#EC4899" />
              <Text style={styles.statValue}>{formatNumber(stats?.total_likes || 0)}</Text>
              <Text style={styles.statLabel}>Likes</Text>
            </View>
          </View>
        </View>

        {/* Quick Share */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Quick Share</Text>
          <Text style={styles.sectionSubtitle}>Share your shop link on social media</Text>
          
          <View style={styles.shareRow}>
            <TouchableOpacity style={[styles.shareBtn, { backgroundColor: '#25D366' }]}>
              <Ionicons name="logo-whatsapp" size={28} color="#fff" />
              <Text style={styles.shareBtnText}>WhatsApp</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[styles.shareBtn, { backgroundColor: '#1877F2' }]}>
              <Ionicons name="logo-facebook" size={28} color="#fff" />
              <Text style={styles.shareBtnText}>Facebook</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[styles.shareBtn, { backgroundColor: '#E4405F' }]}>
              <Ionicons name="logo-instagram" size={28} color="#fff" />
              <Text style={styles.shareBtnText}>Instagram</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Active Promotions */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Active Promotions</Text>
            <TouchableOpacity onPress={() => setShowCreatePromoModal(true)}>
              <Text style={styles.addText}>+ Add</Text>
            </TouchableOpacity>
          </View>
          
          {promotions.filter(p => p.status === 'active').length === 0 ? (
            <View style={styles.emptyCard}>
              <Ionicons name="megaphone-outline" size={48} color="#D1D5DB" />
              <Text style={styles.emptyText}>No active promotions</Text>
              <Text style={styles.emptySubtext}>Create a promotion to reach more customers</Text>
            </View>
          ) : (
            promotions.filter(p => p.status === 'active').map((promo) => {
              const info = getPromoTypeInfo(promo.type);
              return (
                <View key={promo.promotion_id} style={styles.promoCard}>
                  <View style={[styles.promoIcon, { backgroundColor: info.color + '20' }]}>
                    <Ionicons name={info.icon as any} size={24} color={info.color} />
                  </View>
                  <View style={styles.promoContent}>
                    <Text style={styles.promoType}>{promo.type.replace('_', ' ')}</Text>
                    <View style={styles.promoStats}>
                      <Text style={styles.promoStat}>{promo.impressions} views</Text>
                      <Text style={styles.promoStatDivider}>•</Text>
                      <Text style={styles.promoStat}>{promo.clicks} clicks</Text>
                    </View>
                  </View>
                  <View style={styles.promoStatus}>
                    <Text style={styles.promoStatusText}>Active</Text>
                  </View>
                </View>
              );
            })
          )}
        </View>

        {/* Promotion Options */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Promotion Options</Text>
          <Text style={styles.sectionSubtitle}>Boost your visibility and reach</Text>
          
          {['featured_listing', 'visibility_boost', 'explore_promotion'].map((type) => {
            const info = getPromoTypeInfo(type);
            return (
              <TouchableOpacity 
                key={type} 
                style={styles.optionCard}
                onPress={() => {
                  setSelectedPromoType(type);
                  setShowCreatePromoModal(true);
                }}
              >
                <View style={[styles.optionIcon, { backgroundColor: info.color + '20' }]}>
                  <Ionicons name={info.icon as any} size={28} color={info.color} />
                </View>
                <View style={styles.optionContent}>
                  <Text style={styles.optionTitle}>{type.replace(/_/g, ' ')}</Text>
                  <Text style={styles.optionDesc}>{info.desc}</Text>
                  <Text style={[styles.optionPrice, { color: info.color }]}>Starting ₹{info.price}/day</Text>
                </View>
                <Ionicons name="chevron-forward" size={24} color="#D1D5DB" />
              </TouchableOpacity>
            );
          })}
        </View>

        {/* Shop Posts */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Your Posts</Text>
            <TouchableOpacity onPress={() => setShowCreatePostModal(true)}>
              <Text style={styles.addText}>+ Create Post</Text>
            </TouchableOpacity>
          </View>
          <Text style={styles.sectionSubtitle}>Posts appear in Explore tab for all users</Text>
          
          {posts.length === 0 ? (
            <View style={styles.emptyCard}>
              <Ionicons name="create-outline" size={48} color="#D1D5DB" />
              <Text style={styles.emptyText}>No posts yet</Text>
              <Text style={styles.emptySubtext}>Share updates to engage with customers</Text>
              <TouchableOpacity 
                style={styles.createPostBtn}
                onPress={() => setShowCreatePostModal(true)}
              >
                <Ionicons name="add" size={20} color="#fff" />
                <Text style={styles.createPostBtnText}>Create Your First Post</Text>
              </TouchableOpacity>
            </View>
          ) : (
            posts.slice(0, 3).map((post) => (
              <View key={post.post_id} style={styles.postCard}>
                <Text style={styles.postContent} numberOfLines={3}>{post.content}</Text>
                <View style={styles.postStats}>
                  <View style={styles.postStatItem}>
                    <Ionicons name="heart" size={16} color="#EC4899" />
                    <Text style={styles.postStatText}>{post.likes}</Text>
                  </View>
                  <View style={styles.postStatItem}>
                    <Ionicons name="chatbubble" size={16} color="#6366F1" />
                    <Text style={styles.postStatText}>{post.comments}</Text>
                  </View>
                  {post.is_promoted && (
                    <View style={styles.promotedBadge}>
                      <Ionicons name="rocket" size={12} color="#F59E0B" />
                      <Text style={styles.promotedText}>Promoted</Text>
                    </View>
                  )}
                </View>
              </View>
            ))
          )}
        </View>

        {/* Free Tools */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Free Promotion Tools</Text>
          
          <TouchableOpacity style={styles.freeToolCard}>
            <View style={[styles.freeToolIcon, { backgroundColor: '#DCFCE7' }]}>
              <Ionicons name="qr-code" size={24} color="#22C55E" />
            </View>
            <View style={styles.freeToolContent}>
              <Text style={styles.freeToolTitle}>Shop QR Code</Text>
              <Text style={styles.freeToolDesc}>Print and display in your shop</Text>
            </View>
            <Ionicons name="chevron-forward" size={20} color="#D1D5DB" />
          </TouchableOpacity>
          
          <TouchableOpacity style={styles.freeToolCard}>
            <View style={[styles.freeToolIcon, { backgroundColor: '#FEF3C7' }]}>
              <Ionicons name="star" size={24} color="#F59E0B" />
            </View>
            <View style={styles.freeToolContent}>
              <Text style={styles.freeToolTitle}>Ask for Reviews</Text>
              <Text style={styles.freeToolDesc}>Remind customers to rate your shop</Text>
            </View>
            <Ionicons name="chevron-forward" size={20} color="#D1D5DB" />
          </TouchableOpacity>
        </View>

        <View style={{ height: 100 }} />
      </ScrollView>

      {/* Create Post Modal */}
      <Modal
        visible={showCreatePostModal}
        animationType="slide"
        presentationStyle="pageSheet"
      >
        <View style={[styles.modalContainer, { paddingTop: insets.top }]}>
          <View style={styles.modalHeader}>
            <TouchableOpacity onPress={() => setShowCreatePostModal(false)}>
              <Ionicons name="close" size={28} color="#111827" />
            </TouchableOpacity>
            <Text style={styles.modalTitle}>Create Post</Text>
            <TouchableOpacity 
              onPress={createPost}
              disabled={creating || !postContent.trim()}
            >
              <Text style={[
                styles.modalAction,
                (!postContent.trim() || creating) && styles.modalActionDisabled
              ]}>
                {creating ? 'Posting...' : 'Post'}
              </Text>
            </TouchableOpacity>
          </View>
          
          <View style={styles.modalContent}>
            <TextInput
              style={styles.postInput}
              placeholder="What's new at your shop? Share updates, offers, new products..."
              placeholderTextColor="#9CA3AF"
              multiline
              value={postContent}
              onChangeText={setPostContent}
              maxLength={500}
            />
            <Text style={styles.charCount}>{postContent.length}/500</Text>
            
            <View style={styles.postActions}>
              <TouchableOpacity style={styles.postActionBtn}>
                <Ionicons name="image" size={24} color="#6366F1" />
                <Text style={styles.postActionText}>Add Photos</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.postActionBtn}>
                <Ionicons name="pricetag" size={24} color="#22C55E" />
                <Text style={styles.postActionText}>Tag Products</Text>
              </TouchableOpacity>
            </View>
            
            <View style={styles.infoCard}>
              <Ionicons name="information-circle" size={20} color="#6366F1" />
              <Text style={styles.infoText}>
                Your post will appear in the Explore tab where customers across the city can discover your shop.
              </Text>
            </View>
          </View>
        </View>
      </Modal>

      {/* Create Promotion Modal */}
      <Modal
        visible={showCreatePromoModal}
        animationType="slide"
        presentationStyle="pageSheet"
      >
        <View style={[styles.modalContainer, { paddingTop: insets.top }]}>
          <View style={styles.modalHeader}>
            <TouchableOpacity onPress={() => setShowCreatePromoModal(false)}>
              <Ionicons name="close" size={28} color="#111827" />
            </TouchableOpacity>
            <Text style={styles.modalTitle}>Create Promotion</Text>
            <View style={{ width: 28 }} />
          </View>
          
          <ScrollView style={styles.modalContent}>
            {/* Promotion Type Selection */}
            <Text style={styles.inputLabel}>Promotion Type</Text>
            {['featured_listing', 'visibility_boost', 'explore_promotion'].map((type) => {
              const info = getPromoTypeInfo(type);
              const isSelected = selectedPromoType === type;
              return (
                <TouchableOpacity 
                  key={type}
                  style={[styles.promoTypeOption, isSelected && styles.promoTypeSelected]}
                  onPress={() => setSelectedPromoType(type)}
                >
                  <View style={[styles.promoTypeIcon, { backgroundColor: info.color + '20' }]}>
                    <Ionicons name={info.icon as any} size={24} color={info.color} />
                  </View>
                  <View style={styles.promoTypeContent}>
                    <Text style={styles.promoTypeName}>{type.replace(/_/g, ' ')}</Text>
                    <Text style={styles.promoTypeDesc}>{info.desc}</Text>
                    <Text style={[styles.promoTypePrice, { color: info.color }]}>₹{info.price}/day</Text>
                  </View>
                  <View style={[styles.radioOuter, isSelected && { borderColor: info.color }]}>
                    {isSelected && <View style={[styles.radioInner, { backgroundColor: info.color }]} />}
                  </View>
                </TouchableOpacity>
              );
            })}
            
            {/* Duration Selection */}
            <Text style={[styles.inputLabel, { marginTop: 24 }]}>Duration</Text>
            <View style={styles.durationRow}>
              {[1, 7, 14, 30].map((days) => {
                const isSelected = promoDuration === days;
                const info = getPromoTypeInfo(selectedPromoType);
                const totalCost = info.price * days;
                const savings = days > 1 ? Math.round(info.price * days * 0.1) : 0;
                return (
                  <TouchableOpacity 
                    key={days}
                    style={[styles.durationOption, isSelected && styles.durationSelected]}
                    onPress={() => setPromoDuration(days)}
                  >
                    <Text style={[styles.durationDays, isSelected && styles.durationDaysSelected]}>
                      {days}
                    </Text>
                    <Text style={styles.durationLabel}>day{days > 1 ? 's' : ''}</Text>
                    <Text style={[styles.durationPrice, isSelected && styles.durationPriceSelected]}>
                      ₹{totalCost}
                    </Text>
                    {savings > 0 && (
                      <Text style={styles.durationSavings}>Save ₹{savings}</Text>
                    )}
                  </TouchableOpacity>
                );
              })}
            </View>
            
            {/* Cost Summary */}
            <View style={styles.costSummary}>
              <View style={styles.costRow}>
                <Text style={styles.costLabel}>Duration</Text>
                <Text style={styles.costValue}>{promoDuration} day{promoDuration > 1 ? 's' : ''}</Text>
              </View>
              <View style={styles.costRow}>
                <Text style={styles.costLabel}>Price per day</Text>
                <Text style={styles.costValue}>₹{getPromoTypeInfo(selectedPromoType).price}</Text>
              </View>
              <View style={[styles.costRow, styles.costTotal]}>
                <Text style={styles.costTotalLabel}>Total</Text>
                <Text style={styles.costTotalValue}>
                  ₹{getPromoTypeInfo(selectedPromoType).price * promoDuration}
                </Text>
              </View>
            </View>
            
            <TouchableOpacity 
              style={[styles.createPromoBtn, creating && styles.createPromoBtnDisabled]}
              onPress={createPromotion}
              disabled={creating}
            >
              {creating ? (
                <ActivityIndicator size="small" color="#fff" />
              ) : (
                <>
                  <Ionicons name="rocket" size={20} color="#fff" />
                  <Text style={styles.createPromoBtnText}>Start Promotion</Text>
                </>
              )}
            </TouchableOpacity>
            
            <View style={{ height: 40 }} />
          </ScrollView>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F8FAFC',
  },
  centered: {
    justifyContent: 'center',
    alignItems: 'center',
  },
  scrollView: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  backBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#F3F4F6',
    justifyContent: 'center',
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#111827',
  },
  // Stats Card
  statsCard: {
    backgroundColor: '#6366F1',
    margin: 16,
    borderRadius: 20,
    padding: 20,
  },
  statsHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  statsTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#fff',
  },
  liveIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255,255,255,0.2)',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  liveDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#22C55E',
    marginRight: 6,
  },
  liveText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#fff',
  },
  statsGrid: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  statItem: {
    alignItems: 'center',
    backgroundColor: 'rgba(255,255,255,0.15)',
    paddingVertical: 12,
    paddingHorizontal: 8,
    borderRadius: 12,
    minWidth: (width - 80) / 4,
  },
  statValue: {
    fontSize: 20,
    fontWeight: '800',
    color: '#fff',
    marginTop: 4,
  },
  statLabel: {
    fontSize: 10,
    color: 'rgba(255,255,255,0.8)',
    marginTop: 2,
  },
  // Sections
  section: {
    paddingHorizontal: 16,
    marginBottom: 24,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#111827',
  },
  sectionSubtitle: {
    fontSize: 13,
    color: '#6B7280',
    marginTop: 4,
    marginBottom: 12,
  },
  addText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#6366F1',
  },
  // Share Row
  shareRow: {
    flexDirection: 'row',
    gap: 12,
  },
  shareBtn: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: 16,
    borderRadius: 16,
  },
  shareBtnText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#fff',
    marginTop: 6,
  },
  // Empty Card
  emptyCard: {
    backgroundColor: '#fff',
    borderRadius: 16,
    padding: 32,
    alignItems: 'center',
  },
  emptyText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#6B7280',
    marginTop: 12,
  },
  emptySubtext: {
    fontSize: 13,
    color: '#9CA3AF',
    marginTop: 4,
    textAlign: 'center',
  },
  // Promo Card
  promoCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 12,
    marginTop: 8,
  },
  promoIcon: {
    width: 48,
    height: 48,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
  },
  promoContent: {
    flex: 1,
    marginLeft: 12,
  },
  promoType: {
    fontSize: 14,
    fontWeight: '600',
    color: '#111827',
    textTransform: 'capitalize',
  },
  promoStats: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 4,
  },
  promoStat: {
    fontSize: 12,
    color: '#6B7280',
  },
  promoStatDivider: {
    fontSize: 12,
    color: '#D1D5DB',
    marginHorizontal: 6,
  },
  promoStatus: {
    backgroundColor: '#DCFCE7',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
  },
  promoStatusText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#22C55E',
  },
  // Option Card
  optionCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#fff',
    borderRadius: 16,
    padding: 16,
    marginTop: 8,
  },
  optionIcon: {
    width: 56,
    height: 56,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
  },
  optionContent: {
    flex: 1,
    marginLeft: 14,
  },
  optionTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: '#111827',
    textTransform: 'capitalize',
  },
  optionDesc: {
    fontSize: 12,
    color: '#6B7280',
    marginTop: 2,
  },
  optionPrice: {
    fontSize: 13,
    fontWeight: '700',
    marginTop: 4,
  },
  // Post Card
  postCard: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 14,
    marginTop: 8,
  },
  postContent: {
    fontSize: 14,
    color: '#374151',
    lineHeight: 20,
  },
  postStats: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 10,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: '#F3F4F6',
    gap: 16,
  },
  postStatItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  postStatText: {
    fontSize: 13,
    color: '#6B7280',
  },
  promotedBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FEF3C7',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 8,
    marginLeft: 'auto',
    gap: 4,
  },
  promotedText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#F59E0B',
  },
  createPostBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#6366F1',
    paddingVertical: 12,
    paddingHorizontal: 20,
    borderRadius: 12,
    marginTop: 16,
    gap: 8,
  },
  createPostBtnText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#fff',
  },
  // Free Tool Card
  freeToolCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 14,
    marginTop: 8,
  },
  freeToolIcon: {
    width: 44,
    height: 44,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
  },
  freeToolContent: {
    flex: 1,
    marginLeft: 12,
  },
  freeToolTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#111827',
  },
  freeToolDesc: {
    fontSize: 12,
    color: '#6B7280',
    marginTop: 2,
  },
  // Modal
  modalContainer: {
    flex: 1,
    backgroundColor: '#fff',
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#111827',
  },
  modalAction: {
    fontSize: 16,
    fontWeight: '600',
    color: '#6366F1',
  },
  modalActionDisabled: {
    color: '#D1D5DB',
  },
  modalContent: {
    flex: 1,
    padding: 16,
  },
  postInput: {
    fontSize: 16,
    color: '#111827',
    minHeight: 120,
    textAlignVertical: 'top',
  },
  charCount: {
    fontSize: 12,
    color: '#9CA3AF',
    textAlign: 'right',
    marginTop: 8,
  },
  postActions: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 20,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: '#E5E7EB',
  },
  postActionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F3F4F6',
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 10,
    gap: 8,
  },
  postActionText: {
    fontSize: 14,
    fontWeight: '500',
    color: '#374151',
  },
  infoCard: {
    flexDirection: 'row',
    backgroundColor: '#EEF2FF',
    borderRadius: 12,
    padding: 14,
    marginTop: 20,
    gap: 10,
  },
  infoText: {
    flex: 1,
    fontSize: 13,
    color: '#4F46E5',
    lineHeight: 18,
  },
  // Promo Type Selection
  inputLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: '#374151',
    marginBottom: 12,
  },
  promoTypeOption: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F9FAFB',
    borderRadius: 16,
    padding: 14,
    marginBottom: 10,
    borderWidth: 2,
    borderColor: 'transparent',
  },
  promoTypeSelected: {
    backgroundColor: '#fff',
    borderColor: '#6366F1',
  },
  promoTypeIcon: {
    width: 48,
    height: 48,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
  },
  promoTypeContent: {
    flex: 1,
    marginLeft: 12,
  },
  promoTypeName: {
    fontSize: 15,
    fontWeight: '600',
    color: '#111827',
    textTransform: 'capitalize',
  },
  promoTypeDesc: {
    fontSize: 12,
    color: '#6B7280',
    marginTop: 2,
  },
  promoTypePrice: {
    fontSize: 13,
    fontWeight: '700',
    marginTop: 4,
  },
  radioOuter: {
    width: 24,
    height: 24,
    borderRadius: 12,
    borderWidth: 2,
    borderColor: '#D1D5DB',
    justifyContent: 'center',
    alignItems: 'center',
  },
  radioInner: {
    width: 12,
    height: 12,
    borderRadius: 6,
  },
  // Duration
  durationRow: {
    flexDirection: 'row',
    gap: 8,
  },
  durationOption: {
    flex: 1,
    alignItems: 'center',
    backgroundColor: '#F9FAFB',
    borderRadius: 12,
    paddingVertical: 14,
    borderWidth: 2,
    borderColor: 'transparent',
  },
  durationSelected: {
    backgroundColor: '#EEF2FF',
    borderColor: '#6366F1',
  },
  durationDays: {
    fontSize: 24,
    fontWeight: '800',
    color: '#374151',
  },
  durationDaysSelected: {
    color: '#6366F1',
  },
  durationLabel: {
    fontSize: 11,
    color: '#6B7280',
  },
  durationPrice: {
    fontSize: 13,
    fontWeight: '700',
    color: '#374151',
    marginTop: 6,
  },
  durationPriceSelected: {
    color: '#6366F1',
  },
  durationSavings: {
    fontSize: 10,
    fontWeight: '600',
    color: '#22C55E',
    marginTop: 2,
  },
  // Cost Summary
  costSummary: {
    backgroundColor: '#F9FAFB',
    borderRadius: 16,
    padding: 16,
    marginTop: 24,
  },
  costRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  costLabel: {
    fontSize: 14,
    color: '#6B7280',
  },
  costValue: {
    fontSize: 14,
    fontWeight: '500',
    color: '#374151',
  },
  costTotal: {
    marginTop: 8,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#E5E7EB',
    marginBottom: 0,
  },
  costTotalLabel: {
    fontSize: 16,
    fontWeight: '700',
    color: '#111827',
  },
  costTotalValue: {
    fontSize: 20,
    fontWeight: '800',
    color: '#6366F1',
  },
  createPromoBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#6366F1',
    paddingVertical: 16,
    borderRadius: 14,
    marginTop: 24,
    gap: 8,
  },
  createPromoBtnDisabled: {
    backgroundColor: '#A5B4FC',
  },
  createPromoBtnText: {
    fontSize: 16,
    fontWeight: '700',
    color: '#fff',
  },
});
