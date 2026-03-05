import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
  Image,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { format } from 'date-fns';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

interface RatingSummary {
  average_rating: number;
  total_ratings: number;
  rating_distribution: { [key: number]: number };
  criteria_averages: { [key: string]: number };
}

interface Rating {
  rating_id: string;
  order_id: string;
  user_name: string;
  vendor_rating: {
    overall: number;
    criteria_scores: { [key: string]: number };
    review_text?: string;
    photos: string[];
  };
  created_at: string;
}

export default function VendorRatingsScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [summary, setSummary] = useState<RatingSummary | null>(null);
  const [ratings, setRatings] = useState<Rating[]>([]);
  const [activeTab, setActiveTab] = useState<'overview' | 'reviews'>('overview');

  const fetchData = async () => {
    try {
      const token = await getToken();
      
      // Fetch summary
      const summaryRes = await fetch(`${API_URL}/api/vendor/ratings/summary`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const summaryData = await summaryRes.json();
      setSummary(summaryData);
      
      // Fetch ratings
      const ratingsRes = await fetch(`${API_URL}/api/vendor/ratings?limit=50`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const ratingsData = await ratingsRes.json();
      setRatings(ratingsData.ratings || []);
    } catch (error) {
      console.error('Error fetching ratings:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const getToken = async () => {
    const AsyncStorage = require('@react-native-async-storage/async-storage').default;
    return await AsyncStorage.getItem('token');
  };

  useEffect(() => {
    fetchData();
  }, []);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    fetchData();
  }, []);

  const renderStars = (rating: number, size: number = 16) => {
    const stars = [];
    for (let i = 1; i <= 5; i++) {
      stars.push(
        <Ionicons
          key={i}
          name={i <= rating ? 'star' : i - 0.5 <= rating ? 'star-half' : 'star-outline'}
          size={size}
          color="#F59E0B"
        />
      );
    }
    return <View style={styles.starsContainer}>{stars}</View>;
  };

  const getCriteriaLabel = (key: string) => {
    const labels: { [key: string]: string } = {
      food_quality: 'Food Quality',
      taste: 'Taste',
      packaging: 'Packaging',
      portion_size: 'Portion Size',
      value_for_money: 'Value for Money',
      product_freshness: 'Freshness',
      accuracy: 'Accuracy',
      expiry_dates: 'Expiry Dates',
      freshness: 'Freshness',
      quality: 'Quality',
      hygiene: 'Hygiene',
      quantity_accuracy: 'Quantity',
      condition: 'Condition',
      product_quality: 'Product Quality',
    };
    return labels[key] || key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  };

  if (loading) {
    return (
      <View style={[styles.container, styles.loadingContainer]}>
        <ActivityIndicator size="large" color="#6366F1" />
      </View>
    );
  }

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={24} color="#111827" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Ratings & Reviews</Text>
        <View style={{ width: 40 }} />
      </View>

      {/* Tab Selector */}
      <View style={styles.tabContainer}>
        <TouchableOpacity
          style={[styles.tab, activeTab === 'overview' && styles.activeTab]}
          onPress={() => setActiveTab('overview')}
        >
          <Text style={[styles.tabText, activeTab === 'overview' && styles.activeTabText]}>
            Overview
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tab, activeTab === 'reviews' && styles.activeTab]}
          onPress={() => setActiveTab('reviews')}
        >
          <Text style={[styles.tabText, activeTab === 'reviews' && styles.activeTabText]}>
            Reviews ({summary?.total_ratings || 0})
          </Text>
        </TouchableOpacity>
      </View>

      <ScrollView
        style={styles.content}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={['#6366F1']} />
        }
        showsVerticalScrollIndicator={false}
      >
        {activeTab === 'overview' ? (
          <>
            {/* Rating Overview Card */}
            <View style={styles.overviewCard}>
              <View style={styles.ratingBig}>
                <Text style={styles.ratingNumber}>{summary?.average_rating?.toFixed(1) || '0.0'}</Text>
                {renderStars(summary?.average_rating || 0, 24)}
                <Text style={styles.totalRatings}>
                  Based on {summary?.total_ratings || 0} ratings
                </Text>
              </View>

              {/* Rating Distribution */}
              <View style={styles.distributionContainer}>
                {[5, 4, 3, 2, 1].map((star) => {
                  const count = summary?.rating_distribution?.[star] || 0;
                  const percentage = summary?.total_ratings 
                    ? (count / summary.total_ratings) * 100 
                    : 0;
                  
                  return (
                    <View key={star} style={styles.distributionRow}>
                      <View style={styles.starLabel}>
                        <Text style={styles.starNumber}>{star}</Text>
                        <Ionicons name="star" size={14} color="#F59E0B" />
                      </View>
                      <View style={styles.progressBarBg}>
                        <View style={[styles.progressBarFill, { width: `${percentage}%` }]} />
                      </View>
                      <Text style={styles.countText}>{count}</Text>
                    </View>
                  );
                })}
              </View>
            </View>

            {/* Criteria Breakdown */}
            {summary?.criteria_averages && Object.keys(summary.criteria_averages).length > 0 && (
              <View style={styles.criteriaCard}>
                <Text style={styles.sectionTitle}>Rating Breakdown</Text>
                {Object.entries(summary.criteria_averages).map(([key, value]) => (
                  <View key={key} style={styles.criteriaRow}>
                    <Text style={styles.criteriaLabel}>{getCriteriaLabel(key)}</Text>
                    <View style={styles.criteriaRating}>
                      {renderStars(value, 14)}
                      <Text style={styles.criteriaValue}>{value.toFixed(1)}</Text>
                    </View>
                  </View>
                ))}
              </View>
            )}

            {/* Quick Stats */}
            <View style={styles.statsRow}>
              <View style={styles.statCard}>
                <Ionicons name="trending-up" size={28} color="#10B981" />
                <Text style={styles.statValue}>
                  {summary?.average_rating && summary.average_rating >= 4 ? 'Great' : 
                   summary?.average_rating && summary.average_rating >= 3 ? 'Good' : 'Needs Work'}
                </Text>
                <Text style={styles.statLabel}>Performance</Text>
              </View>
              <View style={styles.statCard}>
                <Ionicons name="chatbubble-ellipses" size={28} color="#6366F1" />
                <Text style={styles.statValue}>{ratings.filter(r => r.vendor_rating?.review_text).length}</Text>
                <Text style={styles.statLabel}>Written Reviews</Text>
              </View>
            </View>
          </>
        ) : (
          <>
            {/* Reviews List */}
            {ratings.length === 0 ? (
              <View style={styles.emptyState}>
                <Ionicons name="star-outline" size={64} color="#D1D5DB" />
                <Text style={styles.emptyTitle}>No reviews yet</Text>
                <Text style={styles.emptySubtitle}>
                  Customer reviews will appear here after deliveries
                </Text>
              </View>
            ) : (
              ratings.map((rating) => (
                <View key={rating.rating_id} style={styles.reviewCard}>
                  <View style={styles.reviewHeader}>
                    <View style={styles.reviewerInfo}>
                      <View style={styles.reviewerAvatar}>
                        <Text style={styles.reviewerInitial}>
                          {rating.user_name?.[0]?.toUpperCase() || 'U'}
                        </Text>
                      </View>
                      <View>
                        <Text style={styles.reviewerName}>{rating.user_name || 'Customer'}</Text>
                        <Text style={styles.reviewDate}>
                          {format(new Date(rating.created_at), 'MMM d, yyyy')}
                        </Text>
                      </View>
                    </View>
                    {renderStars(rating.vendor_rating?.overall || 0, 16)}
                  </View>
                  
                  {rating.vendor_rating?.review_text && (
                    <Text style={styles.reviewText}>{rating.vendor_rating.review_text}</Text>
                  )}
                  
                  {rating.vendor_rating?.criteria_scores && (
                    <View style={styles.criteriaChips}>
                      {Object.entries(rating.vendor_rating.criteria_scores).slice(0, 3).map(([key, value]) => (
                        <View key={key} style={styles.criteriaChip}>
                          <Text style={styles.criteriaChipText}>
                            {getCriteriaLabel(key)}: {value}/5
                          </Text>
                        </View>
                      ))}
                    </View>
                  )}
                  
                  {rating.vendor_rating?.photos?.length > 0 && (
                    <ScrollView horizontal style={styles.photosRow} showsHorizontalScrollIndicator={false}>
                      {rating.vendor_rating.photos.map((photo, idx) => (
                        <Image key={idx} source={{ uri: photo }} style={styles.reviewPhoto} />
                      ))}
                    </ScrollView>
                  )}
                </View>
              ))
            )}
          </>
        )}
        
        <View style={{ height: 40 }} />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F9FAFB',
  },
  loadingContainer: {
    justifyContent: 'center',
    alignItems: 'center',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  backButton: {
    padding: 8,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#111827',
  },
  tabContainer: {
    flexDirection: 'row',
    backgroundColor: '#FFFFFF',
    paddingHorizontal: 16,
    paddingBottom: 12,
    gap: 8,
  },
  tab: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 10,
    backgroundColor: '#F3F4F6',
    alignItems: 'center',
  },
  activeTab: {
    backgroundColor: '#6366F1',
  },
  tabText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#6B7280',
  },
  activeTabText: {
    color: '#FFFFFF',
  },
  content: {
    flex: 1,
    padding: 16,
  },
  overviewCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 20,
    marginBottom: 16,
  },
  ratingBig: {
    alignItems: 'center',
    paddingBottom: 20,
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
    marginBottom: 16,
  },
  ratingNumber: {
    fontSize: 48,
    fontWeight: '800',
    color: '#111827',
  },
  starsContainer: {
    flexDirection: 'row',
    gap: 2,
    marginTop: 8,
  },
  totalRatings: {
    fontSize: 14,
    color: '#6B7280',
    marginTop: 8,
  },
  distributionContainer: {
    gap: 8,
  },
  distributionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  starLabel: {
    flexDirection: 'row',
    alignItems: 'center',
    width: 30,
    gap: 2,
  },
  starNumber: {
    fontSize: 14,
    fontWeight: '600',
    color: '#374151',
  },
  progressBarBg: {
    flex: 1,
    height: 8,
    backgroundColor: '#E5E7EB',
    borderRadius: 4,
    overflow: 'hidden',
  },
  progressBarFill: {
    height: '100%',
    backgroundColor: '#F59E0B',
    borderRadius: 4,
  },
  countText: {
    fontSize: 14,
    color: '#6B7280',
    width: 30,
    textAlign: 'right',
  },
  criteriaCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 20,
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#111827',
    marginBottom: 16,
  },
  criteriaRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#F3F4F6',
  },
  criteriaLabel: {
    fontSize: 14,
    color: '#374151',
  },
  criteriaRating: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  criteriaValue: {
    fontSize: 14,
    fontWeight: '600',
    color: '#111827',
    width: 30,
  },
  statsRow: {
    flexDirection: 'row',
    gap: 12,
  },
  statCard: {
    flex: 1,
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 16,
    alignItems: 'center',
  },
  statValue: {
    fontSize: 20,
    fontWeight: '700',
    color: '#111827',
    marginTop: 8,
  },
  statLabel: {
    fontSize: 12,
    color: '#6B7280',
    marginTop: 4,
  },
  emptyState: {
    alignItems: 'center',
    paddingVertical: 60,
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#374151',
    marginTop: 16,
  },
  emptySubtitle: {
    fontSize: 14,
    color: '#6B7280',
    marginTop: 8,
    textAlign: 'center',
  },
  reviewCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
  },
  reviewHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  reviewerInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  reviewerAvatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#EEF2FF',
    justifyContent: 'center',
    alignItems: 'center',
  },
  reviewerInitial: {
    fontSize: 16,
    fontWeight: '700',
    color: '#6366F1',
  },
  reviewerName: {
    fontSize: 14,
    fontWeight: '600',
    color: '#111827',
  },
  reviewDate: {
    fontSize: 12,
    color: '#6B7280',
    marginTop: 2,
  },
  reviewText: {
    fontSize: 14,
    color: '#374151',
    lineHeight: 20,
    marginBottom: 12,
  },
  criteriaChips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  criteriaChip: {
    backgroundColor: '#F3F4F6',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
  },
  criteriaChipText: {
    fontSize: 12,
    color: '#374151',
  },
  photosRow: {
    marginTop: 12,
  },
  reviewPhoto: {
    width: 80,
    height: 80,
    borderRadius: 8,
    marginRight: 8,
  },
});
