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

interface Issue {
  issue_id: string;
  order_id: string;
  user_name: string;
  category: string;
  category_label: string;
  sub_category: string;
  description: string;
  photos: string[];
  priority: string;
  status: string;
  request_refund: boolean;
  request_replacement: boolean;
  resolution?: {
    type: string;
    amount: number;
    notes: string;
  };
  created_at: string;
}

export default function VendorIssuesScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [issues, setIssues] = useState<Issue[]>([]);
  const [activeFilter, setActiveFilter] = useState<'all' | 'open' | 'resolved'>('all');
  const [stats, setStats] = useState({ open: 0, resolved: 0, total: 0 });

  const fetchData = async () => {
    try {
      const token = await getToken();
      
      const res = await fetch(`${API_URL}/api/vendor/issues`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await res.json();
      
      setIssues(data.issues || []);
      setStats({
        open: data.open_count || 0,
        resolved: data.resolved_count || 0,
        total: data.total || 0
      });
    } catch (error) {
      console.error('Error fetching issues:', error);
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

  const filteredIssues = issues.filter(issue => {
    if (activeFilter === 'all') return true;
    if (activeFilter === 'open') return issue.status === 'open' || issue.status === 'in_progress';
    if (activeFilter === 'resolved') return issue.status === 'resolved' || issue.status === 'closed';
    return true;
  });

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'high': return '#EF4444';
      case 'medium': return '#F59E0B';
      case 'low': return '#10B981';
      default: return '#6B7280';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'open': return '#EF4444';
      case 'in_progress': return '#F59E0B';
      case 'resolved': return '#10B981';
      case 'closed': return '#6B7280';
      default: return '#6B7280';
    }
  };

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'missing_items': return 'remove-circle';
      case 'wrong_items': return 'swap-horizontal';
      case 'quality_issues': return 'warning';
      case 'packaging': return 'cube';
      case 'delivery': return 'bicycle';
      case 'genie_behavior': return 'person';
      case 'payment': return 'card';
      default: return 'help-circle';
    }
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
        <Text style={styles.headerTitle}>Customer Issues</Text>
        <View style={{ width: 40 }} />
      </View>

      {/* Stats Cards */}
      <View style={styles.statsContainer}>
        <View style={[styles.statCard, { backgroundColor: '#FEF2F2' }]}>
          <Ionicons name="alert-circle" size={24} color="#EF4444" />
          <Text style={[styles.statNumber, { color: '#EF4444' }]}>{stats.open}</Text>
          <Text style={styles.statLabel}>Open</Text>
        </View>
        <View style={[styles.statCard, { backgroundColor: '#ECFDF5' }]}>
          <Ionicons name="checkmark-circle" size={24} color="#10B981" />
          <Text style={[styles.statNumber, { color: '#10B981' }]}>{stats.resolved}</Text>
          <Text style={styles.statLabel}>Resolved</Text>
        </View>
        <View style={[styles.statCard, { backgroundColor: '#EEF2FF' }]}>
          <Ionicons name="list" size={24} color="#6366F1" />
          <Text style={[styles.statNumber, { color: '#6366F1' }]}>{stats.total}</Text>
          <Text style={styles.statLabel}>Total</Text>
        </View>
      </View>

      {/* Filter Tabs */}
      <View style={styles.filterContainer}>
        {(['all', 'open', 'resolved'] as const).map((filter) => (
          <TouchableOpacity
            key={filter}
            style={[styles.filterTab, activeFilter === filter && styles.activeFilterTab]}
            onPress={() => setActiveFilter(filter)}
          >
            <Text style={[styles.filterText, activeFilter === filter && styles.activeFilterText]}>
              {filter.charAt(0).toUpperCase() + filter.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <ScrollView
        style={styles.content}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={['#6366F1']} />
        }
        showsVerticalScrollIndicator={false}
      >
        {filteredIssues.length === 0 ? (
          <View style={styles.emptyState}>
            <Ionicons name="checkmark-circle" size={64} color="#10B981" />
            <Text style={styles.emptyTitle}>No issues here</Text>
            <Text style={styles.emptySubtitle}>
              {activeFilter === 'open' 
                ? 'All customer issues have been resolved'
                : 'No customer issues reported yet'}
            </Text>
          </View>
        ) : (
          filteredIssues.map((issue) => (
            <View key={issue.issue_id} style={styles.issueCard}>
              {/* Issue Header */}
              <View style={styles.issueHeader}>
                <View style={styles.categoryBadge}>
                  <Ionicons name={getCategoryIcon(issue.category) as any} size={16} color="#6366F1" />
                  <Text style={styles.categoryText}>{issue.category_label}</Text>
                </View>
                <View style={[styles.priorityBadge, { backgroundColor: getPriorityColor(issue.priority) + '20' }]}>
                  <View style={[styles.priorityDot, { backgroundColor: getPriorityColor(issue.priority) }]} />
                  <Text style={[styles.priorityText, { color: getPriorityColor(issue.priority) }]}>
                    {issue.priority.toUpperCase()}
                  </Text>
                </View>
              </View>

              {/* Order & Customer Info */}
              <View style={styles.orderInfo}>
                <Text style={styles.orderId}>Order #{issue.order_id.slice(-8)}</Text>
                <Text style={styles.customerName}>by {issue.user_name}</Text>
              </View>

              {/* Description */}
              <Text style={styles.description} numberOfLines={3}>
                {issue.description}
              </Text>

              {/* Photos */}
              {issue.photos?.length > 0 && (
                <ScrollView horizontal style={styles.photosRow} showsHorizontalScrollIndicator={false}>
                  {issue.photos.map((photo, idx) => (
                    <Image key={idx} source={{ uri: photo }} style={styles.photo} />
                  ))}
                </ScrollView>
              )}

              {/* Tags */}
              <View style={styles.tagsRow}>
                {issue.request_refund && (
                  <View style={styles.requestTag}>
                    <Ionicons name="cash" size={12} color="#EF4444" />
                    <Text style={styles.requestTagText}>Refund Requested</Text>
                  </View>
                )}
                {issue.request_replacement && (
                  <View style={styles.requestTag}>
                    <Ionicons name="swap-horizontal" size={12} color="#F59E0B" />
                    <Text style={styles.requestTagText}>Replacement Requested</Text>
                  </View>
                )}
              </View>

              {/* Footer */}
              <View style={styles.issueFooter}>
                <View style={[styles.statusBadge, { backgroundColor: getStatusColor(issue.status) + '20' }]}>
                  <Text style={[styles.statusText, { color: getStatusColor(issue.status) }]}>
                    {issue.status.replace('_', ' ').toUpperCase()}
                  </Text>
                </View>
                <Text style={styles.dateText}>
                  {format(new Date(issue.created_at), 'MMM d, h:mm a')}
                </Text>
              </View>

              {/* Resolution */}
              {issue.resolution && (
                <View style={styles.resolutionBox}>
                  <Ionicons name="checkmark-done" size={16} color="#10B981" />
                  <View style={styles.resolutionContent}>
                    <Text style={styles.resolutionType}>
                      {issue.resolution.type === 'refund' ? `Refunded ₹${issue.resolution.amount}` :
                       issue.resolution.type === 'replacement' ? 'Replacement Sent' :
                       issue.resolution.type === 'credit' ? `Credit: ₹${issue.resolution.amount}` :
                       'Issue Resolved'}
                    </Text>
                    {issue.resolution.notes && (
                      <Text style={styles.resolutionNotes}>{issue.resolution.notes}</Text>
                    )}
                  </View>
                </View>
              )}
            </View>
          ))
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
  statsContainer: {
    flexDirection: 'row',
    padding: 16,
    gap: 12,
    backgroundColor: '#FFFFFF',
  },
  statCard: {
    flex: 1,
    alignItems: 'center',
    padding: 12,
    borderRadius: 12,
  },
  statNumber: {
    fontSize: 24,
    fontWeight: '800',
    marginTop: 4,
  },
  statLabel: {
    fontSize: 12,
    color: '#6B7280',
    marginTop: 2,
  },
  filterContainer: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    paddingBottom: 12,
    backgroundColor: '#FFFFFF',
    gap: 8,
  },
  filterTab: {
    flex: 1,
    paddingVertical: 8,
    borderRadius: 8,
    backgroundColor: '#F3F4F6',
    alignItems: 'center',
  },
  activeFilterTab: {
    backgroundColor: '#6366F1',
  },
  filterText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#6B7280',
  },
  activeFilterText: {
    color: '#FFFFFF',
  },
  content: {
    flex: 1,
    padding: 16,
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
  issueCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
  },
  issueHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  categoryBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#EEF2FF',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
    gap: 6,
  },
  categoryText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#6366F1',
  },
  priorityBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    gap: 4,
  },
  priorityDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  priorityText: {
    fontSize: 10,
    fontWeight: '700',
  },
  orderInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
  },
  orderId: {
    fontSize: 14,
    fontWeight: '600',
    color: '#111827',
  },
  customerName: {
    fontSize: 13,
    color: '#6B7280',
  },
  description: {
    fontSize: 14,
    color: '#374151',
    lineHeight: 20,
    marginBottom: 12,
  },
  photosRow: {
    marginBottom: 12,
  },
  photo: {
    width: 70,
    height: 70,
    borderRadius: 8,
    marginRight: 8,
  },
  tagsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 12,
  },
  requestTag: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FEF2F2',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    gap: 4,
  },
  requestTagText: {
    fontSize: 11,
    fontWeight: '500',
    color: '#EF4444',
  },
  issueFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  statusBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 6,
  },
  statusText: {
    fontSize: 11,
    fontWeight: '700',
  },
  dateText: {
    fontSize: 12,
    color: '#6B7280',
  },
  resolutionBox: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: '#ECFDF5',
    padding: 12,
    borderRadius: 10,
    marginTop: 12,
    gap: 10,
  },
  resolutionContent: {
    flex: 1,
  },
  resolutionType: {
    fontSize: 13,
    fontWeight: '600',
    color: '#10B981',
  },
  resolutionNotes: {
    fontSize: 12,
    color: '#6B7280',
    marginTop: 4,
  },
});
