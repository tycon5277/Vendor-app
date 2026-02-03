import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  TextInput,
  KeyboardAvoidingView,
  Platform,
  Animated,
  Image,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { chatAPI } from '../../src/utils/api';
import { ChatRoom, Message } from '../../src/types';
import { useAuthStore } from '../../src/store/authStore';
import { format, isToday, isYesterday } from 'date-fns';

export default function ChatsScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ room?: string }>();
  const insets = useSafeAreaInsets();
  const { user } = useAuthStore();
  const [rooms, setRooms] = useState<ChatRoom[]>([]);
  const [selectedRoom, setSelectedRoom] = useState<ChatRoom | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [messageText, setMessageText] = useState('');
  const [sending, setSending] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const flatListRef = useRef<FlatList>(null);
  const fadeAnim = useRef(new Animated.Value(0)).current;

  const loadRooms = async () => {
    try {
      const response = await chatAPI.getRooms();
      setRooms(response.data);
      
      if (params.room) {
        const room = response.data.find((r: ChatRoom) => r.room_id === params.room);
        if (room) {
          setSelectedRoom(room);
          loadMessages(room.room_id);
        }
      }
    } catch (error) {
      console.error('Load rooms error:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadMessages = async (roomId: string) => {
    try {
      const response = await chatAPI.getMessages(roomId);
      setMessages(response.data);
    } catch (error) {
      console.error('Load messages error:', error);
    }
  };

  useEffect(() => {
    loadRooms();
    Animated.timing(fadeAnim, {
      toValue: 1,
      duration: 400,
      useNativeDriver: true,
    }).start();
  }, []);

  useEffect(() => {
    if (selectedRoom) {
      loadMessages(selectedRoom.room_id);
      const interval = setInterval(() => loadMessages(selectedRoom.room_id), 3000);
      return () => clearInterval(interval);
    }
  }, [selectedRoom]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    if (selectedRoom) {
      await loadMessages(selectedRoom.room_id);
    } else {
      await loadRooms();
    }
    setRefreshing(false);
  }, [selectedRoom]);

  const handleSendMessage = async () => {
    if (!messageText.trim() || !selectedRoom) return;

    setSending(true);
    try {
      await chatAPI.sendMessage(selectedRoom.room_id, messageText.trim());
      setMessageText('');
      await loadMessages(selectedRoom.room_id);
      flatListRef.current?.scrollToEnd();
    } catch (error) {
      console.error('Send message error:', error);
    } finally {
      setSending(false);
    }
  };

  const formatMessageDate = (date: Date) => {
    if (isToday(date)) return format(date, 'h:mm a');
    if (isYesterday(date)) return 'Yesterday';
    return format(date, 'MMM d');
  };

  const filteredRooms = rooms.filter(room => 
    room.customer?.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    room.wish_title?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const getAvatarColor = (name: string) => {
    const colors = ['#6366F1', '#EC4899', '#F59E0B', '#22C55E', '#8B5CF6', '#EF4444'];
    const index = name.charCodeAt(0) % colors.length;
    return colors[index];
  };

  const renderRoom = ({ item }: { item: ChatRoom }) => {
    const avatarColor = getAvatarColor(item.customer?.name || 'C');
    const hasUnread = item.unread_count > 0;
    
    return (
      <TouchableOpacity
        style={[styles.roomCard, hasUnread && styles.roomCardUnread]}
        onPress={() => {
          setSelectedRoom(item);
          loadMessages(item.room_id);
        }}
        activeOpacity={0.7}
      >
        <View style={[styles.roomAvatar, { backgroundColor: avatarColor }]}>
          <Text style={styles.roomAvatarText}>
            {(item.customer?.name || 'C')[0].toUpperCase()}
          </Text>
          {item.is_online && <View style={styles.onlineIndicator} />}
        </View>
        
        <View style={styles.roomContent}>
          <View style={styles.roomHeader}>
            <Text style={[styles.roomTitle, hasUnread && styles.roomTitleUnread]} numberOfLines={1}>
              {item.customer?.name || 'Customer'}
            </Text>
            <Text style={styles.roomTime}>
              {formatMessageDate(new Date(item.last_message?.created_at || item.created_at))}
            </Text>
          </View>
          
          {item.wish_title && (
            <View style={styles.wishBadge}>
              <Ionicons name="sparkles" size={12} color="#6366F1" />
              <Text style={styles.wishTitle} numberOfLines={1}>{item.wish_title}</Text>
            </View>
          )}
          
          {item.last_message && (
            <Text style={[styles.lastMessage, hasUnread && styles.lastMessageUnread]} numberOfLines={1}>
              {item.last_message.sender_id === user?.user_id ? 'You: ' : ''}
              {item.last_message.content}
            </Text>
          )}
        </View>
        
        {hasUnread && (
          <View style={styles.unreadBadge}>
            <Text style={styles.unreadCount}>{item.unread_count}</Text>
          </View>
        )}
      </TouchableOpacity>
    );
  };

  const renderMessage = ({ item, index }: { item: Message; index: number }) => {
    const isMe = item.sender_id === user?.user_id;
    const showDate = index === 0 || 
      format(new Date(messages[index - 1].created_at), 'yyyy-MM-dd') !== 
      format(new Date(item.created_at), 'yyyy-MM-dd');
    
    return (
      <>
        {showDate && (
          <View style={styles.dateSeparator}>
            <View style={styles.dateLine} />
            <Text style={styles.dateText}>
              {isToday(new Date(item.created_at)) ? 'Today' :
               isYesterday(new Date(item.created_at)) ? 'Yesterday' :
               format(new Date(item.created_at), 'MMMM d, yyyy')}
            </Text>
            <View style={styles.dateLine} />
          </View>
        )}
        <View style={[styles.messageRow, isMe && styles.messageRowMe]}>
          {!isMe && (
            <View style={[styles.messageAvatar, { backgroundColor: getAvatarColor(selectedRoom?.customer?.name || 'C') }]}>
              <Text style={styles.messageAvatarText}>
                {(selectedRoom?.customer?.name || 'C')[0].toUpperCase()}
              </Text>
            </View>
          )}
          <View style={[
            styles.messageBubble,
            isMe ? styles.messageBubbleMe : styles.messageBubbleOther
          ]}>
            <Text style={[styles.messageText, isMe && styles.messageTextMe]}>
              {item.content}
            </Text>
            <View style={styles.messageFooter}>
              <Text style={[styles.messageTime, isMe && styles.messageTimeMe]}>
                {format(new Date(item.created_at), 'h:mm a')}
              </Text>
              {isMe && (
                <Ionicons 
                  name={item.read ? 'checkmark-done' : 'checkmark'} 
                  size={14} 
                  color={item.read ? '#60A5FA' : 'rgba(255,255,255,0.5)'} 
                  style={{ marginLeft: 4 }}
                />
              )}
            </View>
          </View>
        </View>
      </>
    );
  };

  // Chat Detail View
  if (selectedRoom) {
    return (
      <View style={[styles.container, { paddingTop: insets.top }]}>
        <View style={styles.chatHeader}>
          <TouchableOpacity
            style={styles.backBtn}
            onPress={() => setSelectedRoom(null)}
          >
            <Ionicons name="arrow-back" size={24} color="#374151" />
          </TouchableOpacity>
          
          <TouchableOpacity style={styles.chatHeaderInfo} activeOpacity={0.7}>
            <View style={[styles.chatAvatar, { backgroundColor: getAvatarColor(selectedRoom.customer?.name || 'C') }]}>
              <Text style={styles.chatAvatarText}>
                {(selectedRoom.customer?.name || 'C')[0].toUpperCase()}
              </Text>
            </View>
            <View style={styles.chatHeaderText}>
              <Text style={styles.chatHeaderTitle}>
                {selectedRoom.customer?.name || 'Customer'}
              </Text>
              <Text style={styles.chatHeaderSubtitle}>
                {selectedRoom.is_online ? '● Online' : 'Offline'}
              </Text>
            </View>
          </TouchableOpacity>
          
          <TouchableOpacity style={styles.callBtn}>
            <Ionicons name="call" size={20} color="#22C55E" />
          </TouchableOpacity>
          <TouchableOpacity style={styles.moreBtn}>
            <Ionicons name="ellipsis-vertical" size={20} color="#6B7280" />
          </TouchableOpacity>
        </View>

        {selectedRoom.wish_title && (
          <View style={styles.wishHeader}>
            <Ionicons name="sparkles" size={16} color="#6366F1" />
            <Text style={styles.wishHeaderText}>{selectedRoom.wish_title}</Text>
            <TouchableOpacity>
              <Text style={styles.viewOrderBtn}>View Order →</Text>
            </TouchableOpacity>
          </View>
        )}

        <KeyboardAvoidingView
          style={styles.chatContainer}
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          keyboardVerticalOffset={Platform.OS === 'ios' ? 0 : 20}
        >
          <FlatList
            ref={flatListRef}
            data={messages}
            renderItem={renderMessage}
            keyExtractor={(item) => item.message_id}
            contentContainerStyle={styles.messagesList}
            refreshControl={
              <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
            }
            onContentSizeChange={() => flatListRef.current?.scrollToEnd()}
            ListEmptyComponent={
              <View style={styles.emptyMessages}>
                <View style={styles.emptyIconBg}>
                  <Ionicons name="chatbubble-ellipses-outline" size={40} color="#D1D5DB" />
                </View>
                <Text style={styles.emptyMessagesTitle}>Start the conversation</Text>
                <Text style={styles.emptyMessagesText}>Say hello to {selectedRoom.customer?.name || 'the customer'}</Text>
              </View>
            }
          />

          <View style={[styles.inputContainer, { paddingBottom: Math.max(insets.bottom, 12) }]}>
            <TouchableOpacity style={styles.attachBtn}>
              <Ionicons name="add-circle" size={28} color="#6366F1" />
            </TouchableOpacity>
            <View style={styles.inputWrapper}>
              <TextInput
                style={styles.messageInput}
                placeholder="Type a message..."
                placeholderTextColor="#9CA3AF"
                value={messageText}
                onChangeText={setMessageText}
                multiline
                maxLength={500}
              />
              <TouchableOpacity style={styles.emojiBtn}>
                <Ionicons name="happy-outline" size={24} color="#9CA3AF" />
              </TouchableOpacity>
            </View>
            <TouchableOpacity
              style={[styles.sendBtn, !messageText.trim() && styles.sendBtnDisabled]}
              onPress={handleSendMessage}
              disabled={!messageText.trim() || sending}
            >
              <Ionicons
                name="send"
                size={20}
                color={messageText.trim() ? '#FFFFFF' : '#9CA3AF'}
              />
            </TouchableOpacity>
          </View>
        </KeyboardAvoidingView>
      </View>
    );
  }

  // Room List View
  return (
    <Animated.View style={[styles.container, { paddingTop: insets.top, opacity: fadeAnim }]}>
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>Messages</Text>
          <Text style={styles.subtitle}>{rooms.length} conversations</Text>
        </View>
        <TouchableOpacity style={styles.newChatBtn}>
          <Ionicons name="create-outline" size={24} color="#6366F1" />
        </TouchableOpacity>
      </View>

      {/* Search Bar */}
      <View style={styles.searchContainer}>
        <View style={styles.searchBar}>
          <Ionicons name="search" size={20} color="#9CA3AF" />
          <TextInput
            style={styles.searchInput}
            placeholder="Search conversations..."
            placeholderTextColor="#9CA3AF"
            value={searchQuery}
            onChangeText={setSearchQuery}
          />
          {searchQuery.length > 0 && (
            <TouchableOpacity onPress={() => setSearchQuery('')}>
              <Ionicons name="close-circle" size={20} color="#9CA3AF" />
            </TouchableOpacity>
          )}
        </View>
      </View>

      {/* Filter Chips */}
      <View style={styles.filterRow}>
        <TouchableOpacity style={[styles.filterChip, styles.filterChipActive]}>
          <Text style={[styles.filterText, styles.filterTextActive]}>All</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.filterChip}>
          <Ionicons name="ellipse" size={8} color="#22C55E" />
          <Text style={styles.filterText}>Online</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.filterChip}>
          <Ionicons name="notifications" size={14} color="#6B7280" />
          <Text style={styles.filterText}>Unread</Text>
        </TouchableOpacity>
      </View>

      <FlatList
        data={filteredRooms}
        renderItem={renderRoom}
        keyExtractor={(item) => item.room_id}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={['#6366F1']} />
        }
        showsVerticalScrollIndicator={false}
        ListEmptyComponent={
          <View style={styles.emptyState}>
            <View style={styles.emptyIconBg}>
              <Ionicons name="chatbubbles-outline" size={56} color="#D1D5DB" />
            </View>
            <Text style={styles.emptyTitle}>No conversations yet</Text>
            <Text style={styles.emptySubtitle}>
              When customers message you about their orders, they'll appear here
            </Text>
          </View>
        }
      />
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F8FAFC',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingTop: 8,
    paddingBottom: 16,
  },
  title: {
    fontSize: 28,
    fontWeight: '800',
    color: '#111827',
  },
  subtitle: {
    fontSize: 14,
    color: '#6B7280',
    marginTop: 2,
  },
  newChatBtn: {
    width: 48,
    height: 48,
    backgroundColor: '#EEF2FF',
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
  },
  // Search
  searchContainer: {
    paddingHorizontal: 16,
    marginBottom: 12,
  },
  searchBar: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 12,
    gap: 10,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 1,
  },
  searchInput: {
    flex: 1,
    fontSize: 15,
    color: '#111827',
  },
  // Filters
  filterRow: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    marginBottom: 12,
    gap: 8,
  },
  filterChip: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
    gap: 6,
  },
  filterChipActive: {
    backgroundColor: '#6366F1',
  },
  filterText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#6B7280',
  },
  filterTextActive: {
    color: '#FFFFFF',
  },
  listContent: {
    paddingHorizontal: 16,
    paddingBottom: 100,
  },
  // Room Card
  roomCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 18,
    padding: 14,
    marginBottom: 10,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 6,
    elevation: 1,
  },
  roomCardUnread: {
    backgroundColor: '#FEFCE8',
    borderWidth: 1,
    borderColor: '#FDE68A',
  },
  roomAvatar: {
    width: 52,
    height: 52,
    borderRadius: 26,
    justifyContent: 'center',
    alignItems: 'center',
    position: 'relative',
  },
  roomAvatarText: {
    fontSize: 20,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  onlineIndicator: {
    position: 'absolute',
    bottom: 2,
    right: 2,
    width: 14,
    height: 14,
    backgroundColor: '#22C55E',
    borderRadius: 7,
    borderWidth: 2,
    borderColor: '#FFFFFF',
  },
  roomContent: {
    flex: 1,
    marginLeft: 14,
  },
  roomHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  roomTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#111827',
    flex: 1,
  },
  roomTitleUnread: {
    fontWeight: '700',
  },
  roomTime: {
    fontSize: 12,
    color: '#9CA3AF',
    marginLeft: 8,
  },
  wishBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginTop: 4,
  },
  wishTitle: {
    fontSize: 12,
    fontWeight: '500',
    color: '#6366F1',
  },
  lastMessage: {
    fontSize: 14,
    color: '#6B7280',
    marginTop: 4,
  },
  lastMessageUnread: {
    fontWeight: '600',
    color: '#374151',
  },
  unreadBadge: {
    minWidth: 22,
    height: 22,
    backgroundColor: '#EF4444',
    borderRadius: 11,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 6,
    marginLeft: 8,
  },
  unreadCount: {
    fontSize: 12,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  emptyState: {
    alignItems: 'center',
    paddingVertical: 60,
    paddingHorizontal: 32,
  },
  emptyIconBg: {
    width: 100,
    height: 100,
    backgroundColor: '#F3F4F6',
    borderRadius: 50,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 20,
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#374151',
    marginBottom: 8,
  },
  emptySubtitle: {
    fontSize: 14,
    color: '#9CA3AF',
    textAlign: 'center',
    lineHeight: 22,
  },
  // Chat Detail Styles
  chatHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 10,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  backBtn: {
    width: 40,
    height: 40,
    justifyContent: 'center',
    alignItems: 'center',
  },
  chatHeaderInfo: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    marginLeft: 4,
  },
  chatAvatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
  },
  chatAvatarText: {
    fontSize: 16,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  chatHeaderText: {
    marginLeft: 12,
  },
  chatHeaderTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#111827',
  },
  chatHeaderSubtitle: {
    fontSize: 12,
    color: '#22C55E',
    marginTop: 1,
  },
  callBtn: {
    width: 40,
    height: 40,
    backgroundColor: '#DCFCE7',
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 8,
  },
  moreBtn: {
    width: 40,
    height: 40,
    justifyContent: 'center',
    alignItems: 'center',
  },
  wishHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#EEF2FF',
    paddingHorizontal: 16,
    paddingVertical: 10,
    gap: 8,
  },
  wishHeaderText: {
    flex: 1,
    fontSize: 13,
    fontWeight: '500',
    color: '#6366F1',
  },
  viewOrderBtn: {
    fontSize: 12,
    fontWeight: '600',
    color: '#4F46E5',
  },
  chatContainer: {
    flex: 1,
  },
  messagesList: {
    padding: 16,
    paddingBottom: 8,
  },
  dateSeparator: {
    flexDirection: 'row',
    alignItems: 'center',
    marginVertical: 16,
  },
  dateLine: {
    flex: 1,
    height: 1,
    backgroundColor: '#E5E7EB',
  },
  dateText: {
    fontSize: 12,
    color: '#9CA3AF',
    paddingHorizontal: 12,
  },
  messageRow: {
    flexDirection: 'row',
    marginBottom: 12,
    alignItems: 'flex-end',
  },
  messageRowMe: {
    flexDirection: 'row-reverse',
  },
  messageAvatar: {
    width: 28,
    height: 28,
    borderRadius: 14,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 8,
  },
  messageAvatarText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  messageBubble: {
    maxWidth: '75%',
    borderRadius: 20,
    padding: 12,
    paddingBottom: 8,
  },
  messageBubbleOther: {
    backgroundColor: '#FFFFFF',
    borderBottomLeftRadius: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 1,
  },
  messageBubbleMe: {
    backgroundColor: '#6366F1',
    borderBottomRightRadius: 4,
  },
  messageText: {
    fontSize: 15,
    color: '#111827',
    lineHeight: 22,
  },
  messageTextMe: {
    color: '#FFFFFF',
  },
  messageFooter: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'flex-end',
    marginTop: 4,
  },
  messageTime: {
    fontSize: 11,
    color: '#9CA3AF',
  },
  messageTimeMe: {
    color: 'rgba(255,255,255,0.7)',
  },
  emptyMessages: {
    alignItems: 'center',
    paddingVertical: 60,
  },
  emptyMessagesTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#374151',
    marginTop: 16,
  },
  emptyMessagesText: {
    fontSize: 14,
    color: '#9CA3AF',
    marginTop: 4,
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    paddingHorizontal: 12,
    paddingTop: 12,
    backgroundColor: '#FFFFFF',
    borderTopWidth: 1,
    borderTopColor: '#E5E7EB',
    gap: 8,
  },
  attachBtn: {
    width: 44,
    height: 44,
    justifyContent: 'center',
    alignItems: 'center',
  },
  inputWrapper: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'flex-end',
    backgroundColor: '#F3F4F6',
    borderRadius: 24,
    paddingLeft: 16,
    paddingRight: 8,
    paddingVertical: 4,
  },
  messageInput: {
    flex: 1,
    fontSize: 15,
    color: '#111827',
    maxHeight: 100,
    paddingVertical: 10,
  },
  emojiBtn: {
    width: 36,
    height: 36,
    justifyContent: 'center',
    alignItems: 'center',
  },
  sendBtn: {
    width: 44,
    height: 44,
    backgroundColor: '#6366F1',
    borderRadius: 22,
    justifyContent: 'center',
    alignItems: 'center',
  },
  sendBtnDisabled: {
    backgroundColor: '#E5E7EB',
  },
});
